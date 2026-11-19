#!/usr/bin/env python3
"""多台 Colab G4 并行出片的共享池（规则 P-COLAB-DUAL-G4）。

用法：
    from colab_pool import ColabPool
    with ColabPool(n=2, setup=my_setup) as pool:          # 并行开机；setup(worker) 在每台上准备环境
        results, failed = pool.run(jobs, my_job_fn)        # 共享队列：哪台空闲哪台取下一个任务
    # 退出 with 时（含异常）一定 stop_all 并核实 burn_rate_hourly == 0.0

- 开机走 loop/tools/colab_bridge_multi.py 的 `wake --session wN`，每台一个独立会话。
- 部分机器没开成（账号当前上限 3 台，或卡源不足）就用开成的继续；一台都没有才报错。
- 某台跑任务失败：任务退回队列换别的机器重试一次；这台连续失败 2 次就下线。
- n=1 时行为与旧的单机流程一致。
- 自我迭代：退出时自动把这次运行（任务数、失败、墙钟、机时、估算 CU）写进 loop/ledger/runs.jsonl。
- 花钱闸门：max_cu=X 时有看门狗，估算花费超过 X 立即 stop_all；auto=True（无人批准的自动回归）
  开机前先查 loop/budget.yaml 额度，超额直接拒绝。
"""
from __future__ import annotations

import json
import queue
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

BRIDGE_PY = "/Users/duxiying/.local/share/uv/tools/google-colab-cli/bin/python"
BRIDGE = str(Path(__file__).resolve().parents[2] / "loop" / "tools" / "colab_bridge_multi.py")
MAX_N = 3  # 2026-11-17 实测上限
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "loop" / "tools"))
import hooks  # noqa: E402  loop 自动记账
_print_lock = threading.Lock()


def log(*a):
    with _print_lock:
        print(*a, flush=True)


def bridge(*args: str, timeout: int = 900) -> str:
    res = subprocess.run([BRIDGE_PY, BRIDGE, *args], capture_output=True, text=True, timeout=timeout)
    return (res.stdout + res.stderr).strip()


def status() -> dict:
    out = bridge("auth_status", timeout=60).splitlines()
    return json.loads(out[-1]) if out else {}


@dataclass
class Worker:
    name: str
    base_gradio: str
    ctx: dict = field(default_factory=dict)  # setup() 放进来的东西：cf_url、client_id、上传缓存……
    fails: int = 0
    done: int = 0
    t_wake: float = 0.0
    t_stop: float = 0.0

    def log(self, *a):
        log(f"[{self.name}]", *a)


class ColabPool:
    def __init__(self, n: int = 2, gpu: str = "G4", setup: Callable[[Worker], None] | None = None,
                 stagger_s: float = 3.0, keepalive_s: float = 70.0, seg: str = "?", stage: str = "?",
                 max_cu: float | None = None, auto: bool = False):
        self.n = max(1, min(int(n), MAX_N))
        if n > MAX_N:
            log(f"[pool] 请求 {n} 台，超过实测上限 {MAX_N}，按 {MAX_N} 台开")
        self.gpu, self.setup, self.stagger_s, self.keepalive_s = gpu, setup, stagger_s, keepalive_s
        self.workers: list[Worker] = []
        self._stop_ka = threading.Event()
        self.seg, self.stage, self.auto = seg, stage, auto
        self.rate = float(hooks.load_budget().get("cu_per_g4_hour", 10.05))
        self.max_cu = max_cu if max_cu is not None else (hooks.load_budget()["auto_cu_per_run"] if auto else None)
        self.t0 = time.time()
        self._all_woken: list[Worker] = []
        self.n_jobs = self.n_failed = 0
        self.over_budget = False
        self._shut = False
        import uuid
        self.tag = f"{re.sub(r'[^a-z0-9]', '', stage.lower())[:6]}{uuid.uuid4().hex[:3]}-"  # 会话名前缀：多个池并行互不抢机器

    # ---------- 生命周期 ----------
    def __enter__(self):
        if self.auto:
            ok, msg = hooks.budget_check(self.max_cu)
            log(f"[pool] 自动运行额度检查：{msg}")
            if not ok:
                raise RuntimeError(f"超出自动额度，需 xiying 批准：{msg}")
        try:
            self._wake_all()
            threading.Thread(target=self._keepalive, daemon=True).start()
            self._setup_all()
        except BaseException:
            self._shutdown()
            raise
        return self

    def __exit__(self, *exc):
        self._shutdown()
        return False

    def _wake_one(self, name: str, out: dict):
        try:
            txt = bridge("wake", "--gpu", self.gpu, "--session", name)
            urls = re.findall(r"https://[a-zA-Z0-9.-]+\.gradio\.live", txt)
            if "WAKE_ERROR" in txt or not urls:
                tail = [l for l in txt.splitlines() if "WAKE_ERROR" in l] or txt.splitlines()[-3:]
                log(f"[pool] {name} 开机失败：{' | '.join(tail)[:300]}")
                self._stop_quiet(name)  # 「失败」的机器可能稍后照样开起来并计费（p3 2026-11-18 漏关 1 小时+）
                return
            out[name] = urls[-1].rstrip("/")
            log(f"[pool] {name} 就绪 {out[name]}")
        except Exception as e:
            log(f"[pool] {name} 开机异常：{e}")
            self._stop_quiet(name)

    def _stop_quiet(self, name: str):
        try:
            bridge("stop", "--session", name, timeout=180)
        except Exception as e:
            log(f"[pool] {name} 补关异常（收尾时按前缀再查）：{e}")

    def _mine_now(self) -> list[str]:
        """本池所有会话：开成的 + 当前在跑且名字带本池前缀的（包括报开机失败、其实开起来了的）。"""
        names = {w.name for w in self._all_woken}
        try:
            names |= {x["name"] for x in status().get("sessions", []) if str(x.get("name", "")).startswith(self.tag)}
        except Exception as e:
            log(f"[pool] 查会话异常：{e}")
        return sorted(names)

    def _wake_all(self):
        log(f"[pool] 并行开 {self.n} 台 {self.gpu} ...")
        got: dict[str, str] = {}
        ts = []
        for i in range(self.n):
            t = threading.Thread(target=self._wake_one, args=(f"{self.tag}w{i + 1}", got))
            t.start()
            ts.append(t)
            time.sleep(self.stagger_s)
        for t in ts:
            t.join()
        self.workers = [Worker(k, got[k], t_wake=time.time()) for k in sorted(got)]
        self._all_woken = list(self.workers)
        if not self.workers:
            raise RuntimeError("一台 GPU 都没开成")
        st = status()
        for x in st.get("sessions", []):
            nm = str(x.get("name", ""))
            if nm.startswith(self.tag) and nm not in got:
                log(f"[pool] ⚠ {nm} 报失败却在跑，立即关掉")
                self._stop_quiet(nm)
        log(f"[pool] 开成 {len(self.workers)}/{self.n} 台，burn {st.get('burn_rate_hourly')} CU/h")

    def _setup_all(self):
        if not self.setup:
            return
        ok: list[Worker] = []

        def run(w: Worker):
            try:
                self.setup(w)
                ok.append(w)
            except Exception as e:
                w.log(f"环境准备失败，下线：{e}")
                bridge("stop", "--session", w.name, timeout=120)
                w.t_stop = time.time()

        ts = [threading.Thread(target=run, args=(w,)) for w in self.workers]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.workers = [w for w in self.workers if w in ok]
        if not self.workers:
            raise RuntimeError("所有机器环境准备都失败")

    def cu_est(self) -> float:
        now = time.time()
        return sum(((w.t_stop or now) - w.t_wake) for w in self._all_woken) / 3600 * self.rate

    def _keepalive(self):
        while not self._stop_ka.wait(self.keepalive_s):
            if self.max_cu is not None and self.cu_est() > self.max_cu:
                self.over_budget = True
                log(f"[pool] ⚠ 估算花费 {self.cu_est():.2f} CU 超过上限 {self.max_cu}，看门狗强制关机")
                self._shutdown()
                return
            try:
                out = bridge("keepalive", timeout=120).splitlines()
                log(f"  [keepalive] {out[-1] if out else ''}")
            except Exception as e:
                log(f"  [keepalive err] {e}")

    def _shutdown(self):
        if self._shut:
            return
        self._shut = True
        self._stop_ka.set()
        t_end = time.time()
        for w in self._all_woken:
            w.t_stop = w.t_stop or t_end
        mine = self._mine_now()
        ghosts = [n for n in mine if n not in {w.name for w in self._all_woken}]
        if ghosts:
            log(f"[pool] ⚠ 发现报开机失败但实际在跑的机器 {ghosts}（时长未入账），一并关掉")
        log(f"[pool] 释放本池机器 {mine} ...")
        for attempt in range(4):
            try:
                for name in mine:
                    bridge("stop", "--session", name, timeout=180)
                st = status()
                left = [x["name"] for x in st.get("sessions", []) if x.get("name") in mine
                        or str(x.get("name", "")).startswith(self.tag)]
                if not left:
                    others = len(st.get("sessions", []))
                    extra = f"（另有 {others} 台属于别的任务，未动）" if others else ""
                    log(f"[pool] 已核实：本池机器全部释放，当前 burn {st.get('burn_rate_hourly')}，余额 {st.get('paid_balance')}{extra}")
                    self._record()
                    return
                log(f"[pool] 仍在运行：{left}，重试")
            except Exception as e:
                log(f"[pool] 关机异常：{e}")
            time.sleep(3.0 * (attempt + 1))
        log("[pool] ⚠ 逐台关机未核实，兜底 stop_all（会连带关掉其他任务的机器）")
        try:
            log(bridge("stop_all", timeout=300).splitlines()[-1])
        except Exception as e:
            log(f"[pool] stop_all 异常：{e}")
        st = status()
        if st.get("burn_rate_hourly") != 0.0:
            log("[pool] ⚠ 仍未归零！请立刻手动 stop_all 并检查 auth_status")
        self._record(note="逐台关机未核实，已兜底 stop_all")

    def _record(self, note: str = ""):
        try:
            mh = sum(w.t_stop - w.t_wake for w in self._all_woken) / 3600
            if self.over_budget:
                note = (note + "；" if note else "") + "看门狗超额关机"
            hooks.record_run(self.seg, self.stage, len(self._all_woken), self.n_jobs, self.n_failed,
                             time.time() - self.t0, mh, mh * self.rate, auto=self.auto, note=note)
        except Exception as e:
            log(f"[pool] 记账失败（不影响关机）：{e}")

    # ---------- 派活 ----------
    def run(self, jobs: list[Any], fn: Callable[[Worker, Any], Any], key: Callable[[Any], str] = lambda j: str(j[0])):
        """共享队列并行跑 jobs。返回 (results{key: 返回值}, failed{key: 错误})，结果顺序不保证。"""
        q: queue.Queue = queue.Queue()
        for j in jobs:
            q.put((j, 0))
        results: dict[str, Any] = {}
        failed: dict[str, str] = {}
        lock = threading.Lock()
        alive = {w.name for w in self.workers}
        t0 = time.time()

        def loop(w: Worker):
            while True:
                try:
                    job, tries = q.get_nowait()
                except queue.Empty:
                    return
                if self._shut:  # 看门狗已关机：剩余任务不再派发
                    with lock:
                        failed[key(job)] = "已关机（超额度）"
                    continue
                k = key(job)
                try:
                    r = fn(w, job)
                    with lock:
                        results[k] = r
                    w.done += 1
                    w.fails = 0
                except Exception as e:
                    w.fails += 1
                    w.log(f"任务 {k} 失败（第 {tries + 1} 次）：{e}")
                    with lock:
                        if tries == 0 and len(alive) > 0:
                            q.put((job, 1))
                        else:
                            failed[k] = str(e)
                    if w.fails >= 2:
                        with lock:
                            alive.discard(w.name)
                            last = not alive
                        w.log("连续失败 2 次，下线")
                        if last:  # 最后一台也下线：剩余任务全部记失败
                            while True:
                                try:
                                    jj, _ = q.get_nowait()
                                except queue.Empty:
                                    break
                                with lock:
                                    failed[key(jj)] = "无可用机器"
                        return

        ts = [threading.Thread(target=loop, args=(w,)) for w in self.workers]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.n_jobs += len(jobs)
        self.n_failed += len(failed)
        per = ", ".join(f"{w.name}:{w.done}" for w in self.workers)
        log(f"[pool] {len(results)}/{len(jobs)} 完成，{len(failed)} 失败，用时 {time.time() - t0:.0f}s（{per}）")
        return results, failed
