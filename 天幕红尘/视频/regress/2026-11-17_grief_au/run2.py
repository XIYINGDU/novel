#!/usr/bin/env python3
"""第二轮（xiying 2026-11-17 批准）：同一台温热 G4 上
  1) 动作幅度测试 Scout：press@8216、strike@8217，与第一轮的 strike@8216、AU s2@8217 交叉对照
  2) HD 1280×720：AU s2（与第一轮 Scout 完全相同的提示词和种子）→ 替换成片 21b
"""
import importlib.util, json, re, threading, time, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("r1", HERE / "run.py")
r1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(r1)
s2v9, s2v10 = r1.s2v9, r1.s2v10
HD = HERE / "hd"; HD.mkdir(exist_ok=True)

base_jobs, _ = r1.jobs()
A_s1, A_s2 = base_jobs[0], base_jobs[1]
p1_strike = A_s1[7]
p1_press = p1_strike.replace("strikes twice weakly against", "presses softly against")
assert p1_press != p1_strike
SCOUT = [
    ("21b_AU_press_s1", "i2v", r1.KEY, None, r1.NF, 8216, r1.NEG_BASE, p1_press),
    ("21b_AU_strike_s2", "i2v", r1.KEY, None, r1.NF, 8217, r1.NEG_BASE, p1_strike),
]
HDJ = [("21b_AU_s2_hd",) + tuple(A_s2[1:])]


def main():
    (HERE / "plan2.json").write_text(json.dumps([{"id": j[0], "seed": j[5], "prompt": j[7]} for j in SCOUT + HDJ],
                                                ensure_ascii=False, indent=1))
    todo_s = [j for j in SCOUT if not (r1.OUT / f"clip_{j[0]}.mp4").exists()]
    todo_h = [j for j in HDJ if not (HD / f"clip_{j[0]}.mp4").exists()]
    if not todo_s and not todo_h:
        print("[skip] all done"); return
    stop = threading.Event()
    try:
        w = s2v9.run_bridge("wake", "--gpu", "G4"); print(w, flush=True)
        if "WAKE_ERROR" in w:
            raise RuntimeError(w)
        base = re.findall(r"https://[a-zA-Z0-9.-]+\.gradio\.live", w)[-1].rstrip("/")
        threading.Thread(target=s2v9.keepalive_loop, args=(stop,), daemon=True).start()
        cf = s2v9.ensure_wan22_and_comfyui(base)
        vhs = s2v9.has_vhs_node(cf)
        cid, cache = uuid.uuid4().hex, {}
        for j in todo_s:
            s2v10.submit_and_download(cf, base, cid, vhs, cache, j, 832, 480, r1.OUT, "rg2")
        for j in todo_h:
            s2v10.submit_and_download(cf, base, cid, vhs, cache, j, 1280, 720, HD, "rg2hd")
        print("[DONE]", flush=True)
    finally:
        stop.set()
        for k in range(4):
            o = s2v9.run_bridge("stop_all"); print(o, flush=True)
            if '"ok": true' in o and '"burn_rate_hourly": 0.0' in o:
                break
            time.sleep(3 * (k + 1))
        print(s2v9.run_bridge("auth_status"), flush=True)


if __name__ == "__main__":
    main()
