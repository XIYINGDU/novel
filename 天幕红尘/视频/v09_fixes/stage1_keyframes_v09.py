#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage 1 (v0.9): Generate pixel-matched FLF2V Start/End keyframe pairs for 01, 02a (organic blood soak + hand touch),
and 02b (standing wounded glance -> fast motionless collapsed heap on Paris stone steps) via Qwen-Image-2.1 on G4 GPU.
"""

import base64
import json
import re
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

BRIDGE_PY = "/Users/duxiying/.local/share/uv/tools/google-colab-cli/bin/python"
BRIDGE = "/Applications/EasyColab.app/Contents/Resources/colab_bridge.py"

VID_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频")
ROOT = VID_ROOT / "v09_fixes"
STILL_DIR = ROOT / "stills"
STILL_DIR.mkdir(parents=True, exist_ok=True)

REF_02A_E1 = VID_ROOT / "v08_fixes" / "stills" / "still_02a_v8_e1.png"

STYLE = (
    "1991 Kodak Vision 35mm cinema film still, anamorphic lens, natural skin texture, "
    "subtle film grain, realistic chiaroscuro lighting, shallow depth of field, no subtitles, no watermarks."
)
NEG_BASE = (
    "cartoon, anime, CGI, 3d render, oversaturated, plastic skin, watermark, subtitle, text, "
    "extra fingers, deformed hands, fused fingers"
)
NEG_PARIS = (
    NEG_BASE
    + ", blue sky, daylight sky, daytime, bright sky, long hair, woman hair, ponytail, hood, hoodie, "
    "suit jacket, face revealed, profile face, silver bracelet, watch, cufflinks, jewelry, bright red paint dot"
)

KEYFRAMES = [
    # --- 01: Back view walking naturally DOWN the four stone steps outside French bistro (arms relaxed at sides) ---
    {
        "id": "01_v9_a",
        "mode": "t2i",
        "seed": 9101,
        "neg": NEG_PARIS,
        "prompt": (
            "Midnight quiet shot in Paris on an upscale wet street under a pitch-black night sky. Medium wide shot strictly from BEHIND "
            "a man (back of short neat dark male hair only, face NEVER visible, zero profile). Wearing a loose plain white crewneck "
            "cotton sweatshirt (NO hood), dark charcoal trousers, and casual sneakers, both arms hanging naturally down at his sides "
            "(NOT in pockets), he steps calmly downward on the wide wet limestone steps outside an opulent warm amber-lit classical French "
            "restaurant on the left. Across the dark empty asphalt street ahead stands an imposing 8-story dark grey Parisian stone apartment "
            "building with dark unlit windows, zero cars or headlights. " + STYLE
        ),
    },
    {
        "id": "01_v9_b",
        "mode": "t2i",
        "seed": 9102,
        "neg": NEG_PARIS,
        "prompt": (
            "35mm Paris night cinema frame strictly from behind a man descending four wide classical limestone steps outside an amber-lit "
            "French restaurant doorway on the left. Plain loose white crewneck cotton sweatshirt, dark charcoal trousers, casual white-grey "
            "sneakers, back of short neat dark hair only. Arms relaxed loosely by his hips as he walks calmly down toward the wet dark stone "
            "sidewalk facing an empty dark boulevard and a tall multi-window grey Parisian building across the street under pitch-black sky. " + STYLE
        ),
    },

    # --- 02a Start frames: Clean plain white cotton chest below collarbone (NO preset dot, NO wrist bangle, hands below frame) ---
    {
        "id": "02a_v9_start_1",
        "mode": "i2i_edit",
        "ref_path": REF_02A_E1,
        "seed": 9201,
        "neg": NEG_PARIS,
        "prompt": (
            "Keep the exact Paris night bistro lighting, dark softly bokeh restaurant interior behind, collarbone-to-waist tight framing "
            "(NO chin, NO neck face, head above top border), and the plain loose white heavyweight crewneck cotton sweatshirt. "
            "COMPLETELY REMOVE the red blood spot from the white sweater chest and COMPLETELY REMOVE the hand/knuckle at the very bottom "
            "edge so ONLY clean, unmarked plain white knitted cotton sweatshirt chest fills the shot with both arms down out of frame."
        ),
    },
    {
        "id": "02a_v9_start_2",
        "mode": "t2i",
        "seed": 9202,
        "neg": NEG_PARIS,
        "prompt": (
            "Tight 35mm cinema medium-close-up strictly framed from the collarbone/crewneck down to upper waist — ZERO chin, ZERO neck/face, "
            "blurred warm amber lights of a Paris restaurant patio softly behind at midnight. A man wears a thick plain white crewneck cotton "
            "sweatshirt completely clean and unstained yet, both arms dropped naturally downward outside the frame (zero hands, zero wrists, "
            "zero blood, zero folds pinched). Realistic fabric weave and subtle midnight key light. " + STYLE
        ),
    },

    # --- 02a End frames (pixel-locked to Start frames!): Organic soaked crimson cotton bloodstain + gentle 5-finger touch ---
    {
        "id": "02a_v9_end_1",
        "mode": "i2i_edit",
        "ref_still_id": "02a_v9_start_1",
        "seed": 9211,
        "neg": NEG_PARIS,
        "prompt": (
            "Keep the EXACT same blurred warm Paris night bistro background, lighting, framing below collarbone, white crewneck cotton "
            "sweatshirt, and natural fabric drape. Now on the left-center chest of the white cotton sweater sits a realistic, organic "
            "palm-sized deep arterial crimson bloodstain soaked naturally into the thick woven cotton fibers — dark burgundy core with "
            "irregular capillary-feathered wet red soaking into the cloth weave (NO cartoonish paint splat, NO inward origami cloth funnel). "
            "A bare anatomically natural five-fingered right hand (zero jewelry, zero wristwatch, zero silver bracelet) gently reaches up and "
            "presses lightly with curved fingertips against the lower edge of the soaking wet crimson stain, fingertips visibly stained dark red."
        ),
    },
    {
        "id": "02a_v9_end_2",
        "mode": "i2i_edit",
        "ref_still_id": "02a_v9_start_2",
        "seed": 9212,
        "neg": NEG_PARIS,
        "prompt": (
            "Keep the EXACT same midnight blurred Paris restaurant background, lighting, collar crop, and white crewneck cotton sweatshirt. "
            "Soaking rapidly across the left chest is a realistic wet dark-red crimson bloodstain absorbed deep into the white cotton weave "
            "(natural capillary edge soak, zero stiff fabric pinch-cone, zero cartoonish spray). One bare anatomically clean five-fingered "
            "male hand (zero watch or bracelet) rises from the bottom edge to lightly touch/press beside the wet bloodstain with red-stained "
            "fingertips."
        ),
    },

    # --- 02b Start frames: Standing strictly back view on the 4 wet restaurant steps glancing toward dark building across road ---
    {
        "id": "02b_v9_start_a",
        "mode": "t2i",
        "seed": 9251,
        "neg": NEG_PARIS,
        "prompt": (
            "Low-angle 35mm cinema midnight back shot on four wide wet classical limestone steps outside an amber-lit French restaurant "
            "in Paris under a pitch-black night sky (zero blue sky, zero daylight). Strictly from BEHIND (back of short neat dark male hair "
            "only, face NEVER visible), a man wearing a loose plain white crewneck cotton sweatshirt, dark charcoal trousers, and white-grey "
            "sneakers stands UPRIGHT on the second stone step (weight still on both feet, NOT crouching yet), slightly hunched at one shoulder "
            "with head angled very slightly upward looking across the empty dark asphalt street toward a dark 8-story multi-window Parisian "
            "building ahead. " + STYLE
        ),
    },
    {
        "id": "02b_v9_start_b",
        "mode": "t2i",
        "seed": 9252,
        "neg": NEG_PARIS,
        "prompt": (
            "Dramatic low-angle 35mm night back view on wet stone French restaurant steps in Paris, warm amber bistro light on right stairs "
            "and dark wet street leading to a dark multi-window 8-story Parisian facade across the road, pitch-black night darkness above. "
            "Seen strictly from behind with back of short neat black hair (zero profile, face never seen), a wounded man in plain white "
            "crewneck sweatshirt, dark grey-black pants, and white sneakers stands still on the stone step tilting his back-of-head slightly "
            "upward toward the distant building across the street. " + STYLE
        ),
    },

    # --- 02b End frames (pixel-locked to Start frames!): Limp collapsed heap down on the exact same wet stone steps ---
    {
        "id": "02b_v9_end_a",
        "mode": "i2i_edit",
        "ref_still_id": "02b_v9_start_a",
        "seed": 9261,
        "neg": NEG_PARIS,
        "prompt": (
            "Keep the EXACT same camera angle, exact same wet classical limestone steps, warm amber restaurant doorway lighting, empty dark "
            "Paris street, 8-story dark building across the road, and pitch-black night sky (zero blue sky). Keep the exact same man's clothes "
            "(plain white crewneck sweatshirt, dark charcoal trousers, white sneakers, short neat dark male hair, face completely hidden). "
            "Instead of standing upright, the man has now collapsed completely downward onto the stone steps into a limp motionless heap — "
            "legs crumpled sideways on the lower step and his white-sweatshirt back and shoulder sprawled low and flat face-down against the "
            "wet stone steps."
        ),
    },
    {
        "id": "02b_v9_end_b",
        "mode": "i2i_edit",
        "ref_still_id": "02b_v9_start_b",
        "seed": 9262,
        "neg": NEG_PARIS,
        "prompt": (
            "Keep the EXACT same camera position, wet stone French restaurant steps, warm amber light, dark street, distant apartment "
            "facade, and pitch-black sky. Keep the exact same man in plain white crewneck sweatshirt, dark charcoal pants, white sneakers, "
            "and short dark male hair (zero face visible). Now the man has crashed completely down onto the lower stone steps — knees tucked "
            "crumpled on wet pavement and torso curled heavily limp and face-down across the stone steps."
        ),
    },
]


def run_bridge(*args: str) -> str:
    res = subprocess.run([BRIDGE_PY, BRIDGE, *args], capture_output=True, text=True)
    return (res.stdout + res.stderr).strip()


def keepalive_loop(stop_evt: threading.Event):
    while not stop_evt.wait(70.0):
        try:
            out = run_bridge("keepalive")
            print(f"  [keepalive] {out}", flush=True)
        except Exception as e:
            print(f"  [keepalive err] {e}", flush=True)


def post_json(base_url: str, path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{base_url}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def get_json(base_url: str, path: str) -> dict:
    with urllib.request.urlopen(f"{base_url}{path}", timeout=30) as resp:
        return json.loads(resp.read())


def download_file(base_url: str, path: str, dst: Path):
    with urllib.request.urlopen(f"{base_url}{path}", timeout=120) as resp:
        dst.write_bytes(resp.read())


def main():
    b64_cache: dict[Path, str] = {}
    stop_ka = threading.Event()
    try:
        print("[1/4] Waking EasyColab G4 GPU for Qwen-Image-2.1 Stage 1 (v0.9)...", flush=True)
        wake_out = run_bridge("wake", "--gpu", "G4")
        print(wake_out, flush=True)
        if "WAKE_ERROR" in wake_out:
            raise RuntimeError(f"wake failed: {wake_out}")
        m = re.findall(r"https://[a-zA-Z0-9.-]+\.gradio\.live", wake_out)
        if not m:
            raise RuntimeError(f"Missing gradio.live URL:\n{wake_out}")
        base_url = m[-1].rstrip("/")

        ka_thread = threading.Thread(target=keepalive_loop, args=(stop_ka,), daemon=True)
        ka_thread.start()

        print("[2/4] Checking qwen_image_21 status...", flush=True)
        st = get_json(base_url, "/minimax_api/status?model_id=qwen_image_21")
        if not st.get("all_downloaded"):
            post_json(base_url, "/minimax_api/download_model", {"model_id": "qwen_image_21"})
            while True:
                time.sleep(5.0)
                st = get_json(base_url, "/minimax_api/status?model_id=qwen_image_21")
                if st.get("all_downloaded") and not st.get("is_downloading"):
                    break
        if not st.get("model_loaded"):
            post_json(base_url, "/minimax_api/load_model", {"model_id": "qwen_image_21", "precision_mode": "bf16", "offload_mode": "disk"})
            while True:
                time.sleep(4.0)
                st = get_json(base_url, "/minimax_api/status?model_id=qwen_image_21")
                if st.get("model_loaded") and not st.get("is_loading_vram"):
                    break
                msg = st.get("task_message", "")
                if not st.get("is_loading_vram") and not st.get("model_loaded") and "失败" in msg:
                    raise RuntimeError(f"load_model failed: {msg}")
        print("  qwen_image_21 loaded & ready!", flush=True)

        print(f"[3/4] Generating {len(KEYFRAMES)} candidate stills...", flush=True)
        for item in KEYFRAMES:
            kid = item["id"]
            out_path = STILL_DIR / f"still_{kid}.png"
            if out_path.exists() and out_path.stat().st_size > 20_000:
                print(f"  [skip] {out_path.name}", flush=True)
                continue
            payload = {
                "model_id": "qwen_image_21",
                "task_mode": item["mode"],
                "visual_prompt": item["prompt"],
                "negative_prompt": item["neg"],
                "width": 1280,
                "height": 720,
                "num_inference_steps": 30,
                "seed": item["seed"],
                "randomize_seed": False,
                "batch_count": 1,
            }
            if item["mode"] == "i2i_edit":
                rp = item["ref_path"] if "ref_path" in item else (STILL_DIR / f"still_{item['ref_still_id']}.png")
                if not rp.exists():
                    raise FileNotFoundError(f"Missing chained reference still: {rp}")
                if rp not in b64_cache:
                    b64_cache[rp] = base64.b64encode(rp.read_bytes()).decode("ascii")
                payload["first_frame_base64"] = b64_cache[rp]
            t0 = time.time()
            print(f"  [submit] still_{kid} ({item['mode']}, seed={item['seed']}) ...", flush=True)
            job = post_json(base_url, "/minimax_api/generate", payload)
            jid = job.get("job_id")
            if not jid or job.get("status") == "failed":
                raise RuntimeError(f"Submit failed for {kid}: {job}")
            while True:
                time.sleep(2.0)
                st = get_json(base_url, f"/minimax_api/job/{jid}")
                status = st.get("status")
                if status == "completed":
                    fname = st["filename"]
                    download_file(base_url, f"/minimax_api/media/{fname}", out_path)
                    print(f"  [done]   still_{kid}.png ({out_path.stat().st_size // 1024} KB, {time.time() - t0:.1f}s)", flush=True)
                    break
                elif status == "failed":
                    raise RuntimeError(f"Job failed for {kid}: {st.get('message')}")
        print("STAGE 1 KEYFRAMES (v0.9) DONE!", flush=True)
    finally:
        stop_ka.set()
        print("[4/4] IMMEDIATELY stopping all Colab GPUs (stop_all)...", flush=True)
        for attempt in range(4):
            out = run_bridge("stop_all")
            print(out, flush=True)
            if '"ok": true' in out and '"burn_rate_hourly": 0.0' in out:
                break
            time.sleep(3.0 * (attempt + 1))
        print("[auth_status check]", flush=True)
        print(run_bridge("auth_status"), flush=True)


if __name__ == "__main__":
    main()
