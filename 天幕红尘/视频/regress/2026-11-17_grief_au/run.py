#!/usr/bin/env python3
"""回归 V-GRIEF-AU-PROMPT：只测 21b，一次 Wan G4，Scout 832×480。

变量只有提示词：关键帧(still_21b_start.png)、种子(8216/8217)、帧数(65)都与原 scout 一致。
prompt 追加和 neg 追加由 loop.py compile 从规则库生成（不手写）。
不碰 ep01_p2/ 的任何文件（stageC 启动会删 hd_plan.json，所以这里不调用它，只 import 辅助函数）。

  python3 视频/regress/2026-11-17_grief_au/run.py
"""
import json, re, subprocess, sys, threading, time, uuid
from pathlib import Path

VID = Path("/Users/duxiying/Documents/novel/天幕红尘/视频")
TM = VID.parent
HERE = Path(__file__).resolve().parent
OUT = HERE / "scout"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(VID / "v09_fixes"))
sys.path.insert(0, str(VID / "v10_fixes"))
import stage2_clips_v09 as s2v9  # noqa: E402
import stage2_scout_hd_v10 as s2v10  # noqa: E402

KEY = VID / "ep01_p2/stills/still_21b_start.png"
NF = 65
NEG_BASE = (  # 与 stageC_scout_hd_p2.py 的 21b 完全一致
    "色调艳丽，过曝，静态，细节模糊不清，字幕，文字水印，整体发灰，最差质量，低质量，JPEG压缩残留，"
    "extra fingers, six fingers, fused fingers, deformed hands, missing fingers, extra limbs, third hand, "
    "modern smartphone, iPhone, wireless phone, rubbery face, morphing face, smiling, laughing, cheerful grin"
    ", standing up, calm expression, cheerful, brown bag"
)


def compiled():
    r = subprocess.run(
        ["uv", "run", "-q", "--with", "pyyaml", "python", str(TM / "loop/tools/loop.py"), "compile",
         "--kind", "video", "--tags", "face_closeup,emotion_negative,crying,char:罗慧娟", "--ep", "01", "--json"],
        capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def jobs():
    c = compiled()
    au = ", ".join(c["prompt"])
    p1 = ("Raw devastating 1991 35mm low-angle close-up on cold hospital linoleum floor under harsh cool light. "
          "Slumped against the wall in grief, " + au + ", tears running down pale cheeks; "
          "her trembling clenched fist strikes twice weakly against the cold floor tiles as her shoulders shake.")
    p2 = ("Sorrowful 1991 hospital corridor close-up: woman slumped against white wall, " + au +
          ", tears on her cheeks, she presses her small clenched fist softly against the cold floor in helplessness, shoulders shaking.")
    neg_b = NEG_BASE + ", " + ", ".join(c["neg"])
    return [
        ("21b_AU_A_s1", "i2v", KEY, None, NF, 8216, NEG_BASE, p1),
        ("21b_AU_A_s2", "i2v", KEY, None, NF, 8217, NEG_BASE, p2),
        ("21b_AU_B_s1", "i2v", KEY, None, NF, 8216, neg_b, p1),
        ("21b_AU_B_s2", "i2v", KEY, None, NF, 8217, neg_b, p2),
    ], c


def main():
    todo, c = jobs()
    (HERE / "plan.json").write_text(json.dumps({"rules": c["rules"], "jobs": [
        {"id": j[0], "seed": j[5], "neg": j[6], "prompt": j[7]} for j in todo]}, ensure_ascii=False, indent=1))
    todo = [j for j in todo if not (OUT / f"clip_{j[0]}.mp4").exists()]
    if not todo:
        print("[skip] all done"); return
    stop = threading.Event()
    try:
        print("[1/4] wake G4", flush=True)
        w = s2v9.run_bridge("wake", "--gpu", "G4"); print(w, flush=True)
        if "WAKE_ERROR" in w:
            raise RuntimeError(w)
        base = re.findall(r"https://[a-zA-Z0-9.-]+\.gradio\.live", w)[-1].rstrip("/")
        threading.Thread(target=s2v9.keepalive_loop, args=(stop,), daemon=True).start()
        cf = s2v9.ensure_wan22_and_comfyui(base)
        vhs = s2v9.has_vhs_node(cf)
        cid, cache = uuid.uuid4().hex, {}
        print(f"[2/4] ComfyUI {cf}; {len(todo)} scout clips", flush=True)
        for j in todo:
            s2v10.submit_and_download(cf, base, cid, vhs, cache, j, 832, 480, OUT, "rg")
        print("[3/4] SCOUT DONE", flush=True)
    finally:
        stop.set()
        print("[4/4] stop_all", flush=True)
        for k in range(4):
            o = s2v9.run_bridge("stop_all"); print(o, flush=True)
            if '"ok": true' in o and '"burn_rate_hourly": 0.0' in o:
                break
            time.sleep(3 * (k + 1))
        print(s2v9.run_bridge("auth_status"), flush=True)


if __name__ == "__main__":
    main()
