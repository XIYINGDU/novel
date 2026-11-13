#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wake clean G4 GPU, run Wan2.2 ComfyUI for remaining v0.3 clips with keepalive, and immediately stop_all."""

import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request

BRIDGE_PY = "/Users/duxiying/.local/share/uv/tools/google-colab-cli/bin/python"
BRIDGE_SCRIPT = "/Applications/EasyColab.app/Contents/Resources/colab_bridge.py"
GEN_SCRIPT = "/Users/duxiying/Documents/novel/天幕红尘/视频/v03_pilot/gen_videos_comfy_v03.py"


def run_bridge(*args):
    p = subprocess.run([BRIDGE_PY, BRIDGE_SCRIPT, *args], capture_output=True, text=True)
    return (p.stdout or "") + "\n" + (p.stderr or "")


def main():
    stop_ka = threading.Event()

    def keepalive_loop():
        while not stop_ka.wait(75.0):
            try:
                out = run_bridge("keepalive").strip()
                last = out.splitlines()[-1] if out else "ok"
                print(f"[keepalive] {last}", flush=True)
            except Exception as e:
                print(f"[keepalive warn] {e}", flush=True)

    try:
        print("[1/5] Waking fresh G4 GPU (clean /dev/shm)...", flush=True)
        w_out = run_bridge("wake", "--gpu", "G4")
        print(w_out, flush=True)
        m = re.search(r"https://[a-zA-Z0-9]+\.gradio\.live", w_out)
        if not m:
            raise RuntimeError(f"Could not find gradio URL in wake output: {w_out}")
        base = m.group(0)
        print(f"[wake ok] BASE={base}", flush=True)

        ka_thread = threading.Thread(target=keepalive_loop, daemon=True)
        ka_thread.start()

        def post(path, obj):
            req = urllib.request.Request(
                base + path,
                data=json.dumps(obj).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            return json.loads(urllib.request.urlopen(req, timeout=60).read())

        def get(path):
            return json.loads(urllib.request.urlopen(base + path, timeout=30).read())

        print("[2/5] Starting ComfyUI...", flush=True)
        post("/minimax_api/comfyui/start", {})
        pub = ""
        while True:
            time.sleep(4)
            c = get("/minimax_api/comfyui/status").get("comfyui", {})
            if c.get("is_running") and c.get("public_url"):
                pub = c["public_url"]
                print(f"[comfy ready] {pub}", flush=True)
                break

        print("[3/5] Installing wan22_i2v_flf2v weights...", flush=True)
        c = get("/minimax_api/comfyui/status").get("comfyui", {})
        packs = {p["id"]: p for p in c.get("preset_packs", [])}
        if not packs.get("wan22_i2v_flf2v", {}).get("ready"):
            post("/minimax_api/comfyui/install_pack", {"pack_id": "wan22_i2v_flf2v"})
            while True:
                time.sleep(5)
                c = get("/minimax_api/comfyui/status").get("comfyui", {})
                wp = {p["id"]: p for p in c.get("preset_packs", [])}.get("wan22_i2v_flf2v", {})
                inst = wp.get("installed_models")
                tot = wp.get("total_models")
                rdy = wp.get("ready")
                print(f"  [pack] {inst}/{tot} ready={rdy}", flush=True)
                if rdy and not c.get("is_downloading_weight"):
                    break

        print("[4/5] Rendering remaining v0.3 clips...", flush=True)
        env = dict(os.environ, EASYCOLAB_URL=base, COMFY_URL=pub)
        subprocess.check_call([sys.executable, GEN_SCRIPT], env=env)
    finally:
        stop_ka.set()
        print("[5/5] IMMEDIATELY stopping all Colab GPUs (stop_all)...", flush=True)
        for attempt in range(4):
            out = run_bridge("stop_all")
            print(out, flush=True)
            if '"ok": true' in out and '"burn_rate_hourly": 0.0' in out:
                break
            time.sleep(3.0 * (attempt + 1))
        print(run_bridge("auth_status"), flush=True)


if __name__ == "__main__":
    main()
