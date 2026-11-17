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
"""
from __future__ import annotations

import json
import queue
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

BRIDGE_PY = "/Users/duxiying/.local/share/uv/tools/google-colab-cli/bin/python"
BRIDGE = str(Path(__file__).resolve().parents[2] / "loop" / "tools" / "colab_bridge_multi.py")
MAX_N = 3  # 2026-11-17 实测上限
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

    def log(self, *a):
        log(f"[{self.name}]", *a)


class ColabPool:
    def __init__(self, n: int = 2, gpu: str = "G4", setup: Callable[[Worker], None] | None = None,
                 stagger_s: float = 3.0, keepalive_s: float = 70.0):
        self.n = max(1, min(int(n), MAX_N))
        if n > MAX_N:
            log(f"[pool] 请求 {n} 台，超过实测上限 {MAX_N}，按 {MAX_N} 台开")
        self.gpu, self.setup, self.stagger_s, self.keepalive_s = gpu, setup, stagger_s, keepalive_s
        self.workers: list[Worker] = []
        self._stop_ka = threading.Event()

    # ---------- 生命周期 ----------
    def __enter__(self):
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
                return
            out[name] = urls[-1].rstrip("/")
            log(f"[pool] {name} 就绪 {out[name]}")
        except Exception as e:
            log(f"[pool] {name} 开机异常：{e}")

    def _wake_all(self):
        log(f"[pool] 并行开 {self.n} 台 {self.gpu} ...")
        got: dict[str, str] = {}
        ts = []
        for i in range(self.n):
            t = threading.Thread(target=self._wake_one, args=(f"w{i + 1}", got))
            t.start()
            ts.append(t)
            time.sleep(self.stagger_s)
        for t in ts:
            t.join()
        self.workers = [Worker(k, got[k]) for k in sorted(got)]
        if not self.workers:
            raise RuntimeError("一台 GPU 都没开成")
        st = status()
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

        ts = [threading.Thread(target=run, args=(w,)) for w in self.workers]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.workers = [w for w in self.workers if w in ok]
        if not self.workers:
            raise RuntimeError("所有机器环境准备都失败")

    def _keepalive(self):
        while not self._stop_ka.wait(self.keepalive_s):
            try:
                out = bridge("keepalive", timeout=120).splitlines()
                log(f"  [keepalive] {out[-1] if out else ''}")
            except Exception as e:
                log(f"  [keepalive err] {e}")

    def _shutdown(self):
        self._stop_ka.set()
        log("[pool] 释放全部 GPU（stop_all）...")
        for attempt in range(4):
            try:
                out = bridge("stop_all", timeout=300)
                log(out.splitlines()[-1] if out else "")
                st = status()
                if st.get("burn_rate_hourly") == 0.0 and st.get("active_assignments") == 0:
                    log(f"[pool] 已核实：burn 0.0，余额 {st.get('paid_balance')}")
                    return
            except Exception as e:
                log(f"[pool] stop_all 异常：{e}")
            time.sleep(3.0 * (attempt + 1))
        log("[pool] ⚠ stop_all 未能核实归零！请立刻手动运行 stop_all 并检查 auth_status")

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
        per = ", ".join(f"{w.name}:{w.done}" for w in self.workers)
        log(f"[pool] {len(results)}/{len(jobs)} 完成，{len(failed)} 失败，用时 {time.time() - t0:.0f}s（{per}）")
        return results, failed
