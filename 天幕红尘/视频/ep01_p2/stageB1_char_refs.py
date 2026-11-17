#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage B1 (ep01_p2): Generate canonical character portraits & clean NY living-room set on Qwen-Image-2.1 (G4):
1. ref/林雪红.png  (from family photo lin_crop.png)
2. ref/罗慧娟.png  (from family photo hui_crop.png)
3. ref/美国医生.png (45yo solemn American ER surgeon)
4. ep01_p2/stills/set_ny_living_room.png (clean empty NY apartment living room edited from still_08.png)
Respects /dev/shm isolation and calls stop_all in finally.
"""

import base64
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    proxies = urllib.request.getproxies()
    for k in ("http", "https"):
        if k in proxies and proxies[k]:
            os.environ.setdefault(f"{k}_proxy", proxies[k])
            os.environ.setdefault(f"{k.upper()}_PROXY", proxies[k])
except Exception:
    pass

BRIDGE_PY = "/Users/duxiying/.local/share/uv/tools/google-colab-cli/bin/python"
BRIDGE = "/Applications/EasyColab.app/Contents/Resources/colab_bridge.py"

VID_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频")
REF_DIR = VID_ROOT / "ref"
P2_ROOT = VID_ROOT / "ep01_p2"
TMP_REF = P2_ROOT / "ref_tmp"
STILL_DIR = P2_ROOT / "stills"
for d in (REF_DIR, STILL_DIR):
    d.mkdir(parents=True, exist_ok=True)

STYLE = (
    "1991 Kodak Vision 35mm cinema film still, anamorphic lens, natural skin texture, "
    "subtle film grain, realistic lighting, shallow depth of field, no subtitles, no watermarks."
)
NEG_PORTRAIT = (
    "cartoon, anime, CGI, 3d render, oversaturated, plastic skin, extra person, multiple people, "
    "second head, photobomb edge, cropped neighbor, watermark, subtitle, text, deformed hands, extra fingers, modern smartphone"
)

JOBS = [
    {
        "out": REF_DIR / "林雪红.png",
        "mode": "i2i_edit",
        "ref": TMP_REF / "lin_crop.png",
        "seed": 6101,
        "neg": NEG_PORTRAIT + ", smiling broadly, bright lipstick, cheerful grin",
        "prompt": (
            "Keep the EXACT same 38-year-old Chinese woman in the center of the reference image (same facial bone structure, eyes, nose, "
            "shoulder-length dark hair, dark grey-taupe collared shirt). Remove both partial adjacent people on the left and right edges "
            "completely so ONLY she stands alone in a clean 1991 Manhattan apartment corridor/room medium close-up portrait, expression "
            "composed, quiet, determined, slightly tired, natural skin texture without broad smiling. " + STYLE
        ),
    },
    {
        "out": REF_DIR / "罗慧娟.png",
        "mode": "i2i_edit",
        "ref": TMP_REF / "hui_crop.png",
        "seed": 6102,
        "neg": NEG_PORTRAIT + ", elderly hair on edge, floral robe",
        "prompt": (
            "Keep the EXACT same 35-year-old Chinese woman on the left of the reference image (same facial features, cheeks, nose, eyes, "
            "shoulder-length dark hair). Remove the beige cardigan shoulder at bottom-right completely so ONLY she is framed cleanly alone "
            "in a medium close-up 1991 domestic portrait wearing a plain muted soft-grey casual home knit sweater, soft warm indoor light, "
            "natural relaxed home expression. " + STYLE
        ),
    },
    {
        "out": REF_DIR / "美国医生.png",
        "mode": "t2i",
        "seed": 6103,
        "neg": NEG_PORTRAIT + ", surgical cap covering whole face, smiling, beard mask glitch",
        "prompt": (
            "Medium close-up 1991 cinema portrait of a solemn, compassionate 45-year-old white American male emergency room surgeon "
            "standing outside frosted hospital operating doors under cool fluorescent corridor light, wearing a crisp white doctor's lab "
            "coat over pale blue surgical scrubs with a stethoscope around his neck and a pale blue medical mask pulled down under his chin, "
            "weary sober expression. " + STYLE
        ),
    },
    {
        "out": STILL_DIR / "set_ny_living_room.png",
        "mode": "i2i_edit",
        "ref": VID_ROOT / "v02_pilot" / "stills" / "still_08.png",
        "seed": 6104,
        "neg": NEG_PORTRAIT + ", person, woman, elderly woman, hand, arm",
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME 1991 sunlit Manhattan apartment living room interior, camera angle, sheer cream sunlit window "
            "curtains on the left, wooden bookshelves on the right, small round wooden coffee table with a half-full clear glass water tumbler, "
            "small plastic pill box, beige corded push-button desk telephone with receiver resting on the cradle, and empty beige cushioned "
            "sofa on the right — simply remove the elderly woman completely so the warm morning sunlit living room sits quiet and empty. " + STYLE
        ),
    },
]


def run_bridge(*args: str) -> str:
    res = subprocess.run([BRIDGE_PY, BRIDGE, *args], capture_output=True, text=True)
    return (res.stdout + res.stderr).strip()


def keepalive_loop(stop_evt: threading.Event):
    while not stop_evt.wait(70.0):
        try:
            run_bridge("keepalive")
        except Exception:
            pass


def http_json(url: str, payload: dict | None = None, timeout: int = 60, retries: int = 5) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    hdrs = {"Content-Type": "application/json"} if payload is not None else {}
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs, method="POST" if data is not None else "GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception as e:
            last = e
            if i + 1 < retries:
                time.sleep(2.5 * (i + 1))
    raise last


def download_bytes(url: str, dst: Path, retries: int = 5):
    last = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                dst.write_bytes(resp.read())
                return
        except Exception as e:
            last = e
            if i + 1 < retries:
                time.sleep(2.5 * (i + 1))
    raise last


def main():
    todo = [j for j in JOBS if not (j["out"].exists() and j["out"].stat().st_size > 20_000)]
    if not todo:
        print("[skip] All Stage B1 refs already exist.")
        return

    stop_ka = threading.Event()
    b64_cache: dict[Path, str] = {}
    try:
        print("[1/4] Waking EasyColab G4 GPU for Qwen-Image-2.1 Stage B1...", flush=True)
        wake_out = run_bridge("wake", "--gpu", "G4")
        print(wake_out, flush=True)
        m = re.findall(r"https://[a-zA-Z0-9.-]+\.gradio\.live", wake_out)
        if not m:
            raise RuntimeError(f"Missing gradio URL:\n{wake_out}")
        base_url = m[-1].rstrip("/")

        threading.Thread(target=keepalive_loop, args=(stop_ka,), daemon=True).start()

        print("[2/4] Ensuring qwen_image_21 loaded on G4...", flush=True)
        st = http_json(f"{base_url}/minimax_api/status?model_id=qwen_image_21")
        if not st.get("all_downloaded"):
            http_json(f"{base_url}/minimax_api/download_model", {"model_id": "qwen_image_21"})
            while True:
                time.sleep(5.0)
                st = http_json(f"{base_url}/minimax_api/status?model_id=qwen_image_21")
                if st.get("all_downloaded") and not st.get("is_downloading"):
                    break
        if not st.get("model_loaded"):
            http_json(f"{base_url}/minimax_api/load_model", {"model_id": "qwen_image_21", "precision_mode": "bf16", "offload_mode": "disk"})
            while True:
                time.sleep(4.0)
                st = http_json(f"{base_url}/minimax_api/status?model_id=qwen_image_21")
                if st.get("model_loaded") and not st.get("is_loading_vram"):
                    break

        print(f"[3/4] Rendering {len(todo)} canonical character/set anchors...", flush=True)
        for j in todo:
            out_p = j["out"]
            payload = {
                "model_id": "qwen_image_21",
                "task_mode": j["mode"],
                "visual_prompt": j["prompt"],
                "negative_prompt": j["neg"],
                "width": 1280,
                "height": 720,
                "num_inference_steps": 30,
                "seed": j["seed"],
                "randomize_seed": False,
                "batch_count": 1,
            }
            if j["mode"] == "i2i_edit":
                rp = j["ref"]
                if rp not in b64_cache:
                    b64_cache[rp] = base64.b64encode(rp.read_bytes()).decode("ascii")
                payload["first_frame_base64"] = b64_cache[rp]
            job = http_json(f"{base_url}/minimax_api/generate", payload)
            jid = job["job_id"]
            while True:
                time.sleep(2.0)
                jst = http_json(f"{base_url}/minimax_api/job/{jid}")
                if jst.get("status") == "completed":
                    fn = jst.get("filename") or Path(jst["filepath"]).name
                    download_bytes(f"{base_url}/minimax_api/media/{fn}", out_p)
                    print(f"  [saved] {out_p.name} ({out_p.stat().st_size // 1024} KB)", flush=True)
                    break
                if jst.get("status") in ("failed", "error"):
                    raise RuntimeError(f"Job failed {out_p.name}: {jst}")
    finally:
        stop_ka.set()
        print("[4/4] Stopping EasyColab GPU (stop_all)...", flush=True)
        print(run_bridge("stop_all"), flush=True)
        print("[auth_status]", run_bridge("auth_status"), flush=True)


if __name__ == "__main__":
    main()
