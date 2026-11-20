#!/usr/bin/env python3
"""多台 Colab G4 并行出片的共享池（规则 P-COLAB-DUAL-G4）。

用法：
    from colab_pool import ColabPool
    with ColabPool(n=2, setup=my_setup) as pool:          # 并行开机；setup(worker) 在每台上准备环境
        results, failed = pool.run(jobs, my_job_fn)        # 共享队列：哪台空闲哪台取下一个任务
    # 退出 with 时（含异常）逐台释放本池机器，无法核实时抛出异常

- 开机走 loop/tools/colab_bridge_multi.py 的 `wake --session wN`，每台一个独立会话。
- 部分机器没开成（账号当前上限 3 台，或卡源不足）就用开成的继续；一台都没有才报错。
- 某台跑任务失败：任务退回队列换别的机器重试一次；这台连续失败 2 次就下线。
- n=1 时行为与旧的单机流程一致。
- 自我迭代：退出时自动把这次运行（任务数、失败、墙钟、机时、估算 CU）写进 loop/ledger/runs.jsonl。
- 花钱闸门：max_cu=X 时有看门狗，估算花费超过 X 即关闭本池；auto=True（无人批准的自动回归）
  开机前先查 loop/budget.yaml 额度，超额直接拒绝。
"""
from __future__ import annotations

import json
import math
import queue
import re
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
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


def bridge(*args: str, timeout: float = 900) -> str:
    res = subprocess.run([BRIDGE_PY, BRIDGE, *args], capture_output=True, text=True, timeout=timeout)
    return (res.stdout + res.stderr).strip()


def _reply(*args, timeout: int) -> dict:
    lines = bridge(*args, timeout=timeout).splitlines()
    result = json.loads(lines[-1]) if lines else {}
    if not isinstance(result, dict) or result.get("ok") is not True:
        reason = result.get("error") if isinstance(result, dict) else None
        raise RuntimeError(f"{args[0]} 失败：{reason or '无有效响应'}")
    return result


def status() -> dict:
    result = _reply("auth_status", timeout=60)
    sessions = result.get("sessions")
    if (result.get("logged_in") is not True or not isinstance(sessions, list)
            or result.get("active_assignments") != len(sessions)
            or any(not isinstance(s, dict) or not s.get("name") or not s.get("endpoint") for s in sessions)):
        raise RuntimeError("无法取得完整的 Colab 会话清单")
    return result


@dataclass
class Worker:
    name: str
    base_gradio: str
    ctx: dict = field(default_factory=dict)  # setup() 放进来的东西：cf_url、client_id、上传缓存……
    fails: int = 0
    done: int = 0
    t_wake: float = 0.0
    t_stop: float = 0.0
    endpoint: str | None = None

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
        if self.max_cu is not None and (not math.isfinite(self.max_cu) or self.max_cu <= 0):
            raise ValueError("max_cu 必须是正的有限额度")
        self.t0 = time.time()
        self.n_jobs = self.n_failed = 0
        self.over_budget = False
        self._release_lock = threading.Lock()
        self._released = False
        self.tag = f"{re.sub(r'[^a-z0-9]', '', stage.lower())[:6]}{uuid.uuid4().hex}-"
        self._requested: list[Worker] = []

    # ---------- 生命周期 ----------
    def __enter__(self):
        if self.auto:
            ok, msg = hooks.budget_check(self.max_cu)
            log(f"[pool] 自动运行额度检查：{msg}")
            if not ok:
                raise RuntimeError(f"超出自动额度，需 xiying 批准：{msg}")
        try:
            self._wake_all()
            if self.max_cu is not None and self.cu_est() >= self.max_cu:
                self.over_budget = True
                raise RuntimeError("开机已达 CU 预算")
            threading.Thread(target=self._keepalive, daemon=True).start()
            self._setup_all()
            if self.over_budget:
                raise RuntimeError("环境准备期间已达 CU 预算")
        except BaseException:
            self._finish()
            raise
        return self

    def __exit__(self, *exc):
        self._finish()
        return False

    def _wake_one(self, worker: Worker):
        name = worker.name
        worker.t_wake = time.time()
        try:
            # wake 包含分配以后的启动/部署时间，预算检查不能只覆盖 setup 和任务。
            timeout = 900
            if self.max_cu is not None:
                timeout = min(timeout, self.max_cu * 3600 / (self.n * self.rate))
            txt = bridge("wake", "--gpu", self.gpu, "--session", name, timeout=timeout)
            urls = re.findall(r"https://[a-zA-Z0-9.-]+\.gradio\.live", txt)
            if "WAKE_ERROR" in txt or not urls:
                tail = [l for l in txt.splitlines() if "WAKE_ERROR" in l] or txt.splitlines()[-3:]
                log(f"[pool] {name} 开机失败：{' | '.join(tail)[:300]}")
                self._stop_quiet(worker)
                return
            worker.base_gradio = urls[-1].rstrip("/")
            log(f"[pool] {name} 就绪 {worker.base_gradio}")
        except Exception as e:
            log(f"[pool] {name} 开机异常：{e}")
            self._stop_quiet(worker)

    def _stop_quiet(self, worker: Worker):
        try:
            result = _reply("stop", "--session", worker.name, timeout=180)
            if result.get("stopped") != worker.name:
                raise RuntimeError("响应中的会话名不符")
            worker.endpoint = result.get("endpoint") or worker.endpoint
            worker.t_stop = time.time()
        except Exception as e:
            log(f"[pool] {worker.name} 关机请求未确认：{e}")

    def _wake_all(self):
        log(f"[pool] 并行开 {self.n} 台 {self.gpu} ...")
        # 先等所有已经发出的开机操作收尾，再进入关机流程。
        with ThreadPoolExecutor(max_workers=self.n) as executor:
            for i in range(self.n):
                w = Worker(f"{self.tag}w{i + 1}", "")
                self._requested.append(w)
                executor.submit(self._wake_one, w)
                if i + 1 < self.n:
                    time.sleep(self.stagger_s)
        self.workers = [w for w in self._requested if w.base_gradio]
        if not self.workers:
            raise RuntimeError("一台 GPU 都没开成")
        st = status()
        live = {x["name"]: x for x in st["sessions"]}
        for w in self._requested:
            if w.name in live:
                w.endpoint = live[w.name].get("endpoint")
            if not w.base_gradio and w.name in live:
                self._stop_quiet(w)
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
                self._stop_quiet(w)

        ts = [threading.Thread(target=run, args=(w,)) for w in self.workers]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.workers = [w for w in self.workers if w in ok]
        if not self.workers:
            raise RuntimeError("所有机器环境准备都失败")

    def _allocated(self) -> list[Worker]:
        return [w for w in self._requested if w.base_gradio or w.endpoint or w.t_stop]

    def cu_est(self) -> float:
        now = time.time()
        return sum((w.t_stop or now) - w.t_wake for w in self._allocated()) / 3600 * self.rate

    def _keepalive(self):
        while not self._stop_ka.wait(self.keepalive_s):
            if self.max_cu is not None and self.cu_est() > self.max_cu:
                self.over_budget = True
                log(f"[pool] ⚠ 估算花费 {self.cu_est():.2f} CU 超过上限 {self.max_cu}，看门狗强制关机")
                try:
                    self._release()
                except Exception as e:
                    log(f"[pool] 看门狗关机未核实，退出时继续处理：{e}")
                return
            try:
                out = bridge("keepalive", timeout=120).splitlines()
                log(f"  [keepalive] {out[-1] if out else ''}")
            except Exception as e:
                log(f"  [keepalive err] {e}")

    def _finish(self):
        # 只有退出上下文的线程记账，此时任务成功/失败计数已汇总。
        try:
            self._release()
        finally:
            self._record(note="" if self._released else "本池关机未核实，机时估到最后一次检查")

    def _release(self):
        self._stop_ka.set()
        # 看门狗和 __exit__ 均可先到；只有拿到锁并核实状态后才能返回。
        with self._release_lock:
            if self._released:
                return
            pending = list(self._requested)
            for attempt in range(4):
                for w in pending:
                    self._stop_quiet(w)
                try:
                    st = status()
                    live = {s["name"]: s["endpoint"] for s in st["sessions"]}
                    endpoints = {s["endpoint"] for s in st["sessions"]}
                    pending = [w for w in self._requested if w.name in live or w.endpoint in endpoints]
                    for w in pending:
                        w.endpoint = live.get(w.name) or w.endpoint
                        w.t_stop = 0.0
                    # 桥接服务给没有本地映射的实例统一命名为 colab-vm。
                    # 未获关闭回执的本池实例也可能在其中，须再次按本池名字核实。
                    if "colab-vm" in live:
                        pending.extend(w for w in self._requested if not w.endpoint and not w.t_stop and w not in pending)
                    if not pending:
                        self._released = True
                        for w in self._allocated():
                            w.t_stop = w.t_stop or time.time()
                        log(f"[pool] 已核实：本池机器全部释放，当前 burn {st.get('burn_rate_hourly')}")
                        return
                    detail = f"仍需核实 {[w.name for w in pending]}"
                except Exception as e:
                    detail = str(e)
                    pending = [w for w in self._requested if not w.t_stop]
                log(f"[pool] 第 {attempt + 1} 次关机核验：{detail}")
                if attempt < 3:
                    time.sleep(3 * (attempt + 1))
            names = [w.name for w in self._requested]
            raise RuntimeError(f"无法核实本池 {names} 已释放：{detail}")

    def _record(self, note: str = ""):
        try:
            now = time.time()
            allocated = self._allocated()
            mh = sum((w.t_stop or now) - w.t_wake for w in allocated) / 3600
            if self.over_budget:
                note = (note + "；" if note else "") + "看门狗超额关机"
            hooks.record_run(self.seg, self.stage, len(allocated), self.n_jobs, self.n_failed,
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
                if self._stop_ka.is_set():  # 看门狗正关机：剩余任务不再派发
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
