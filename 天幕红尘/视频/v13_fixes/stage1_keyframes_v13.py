#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage 1 (v0.13): Fix shot-and-collapse sequence per user spec:
1) 01_v13_hit_{a,b,c}: Frontal chest sniper punch from across street -> subtle BACKWARD upper-body jolt & abrupt freeze (micro backward recoil, NOT forward hunch/crouch)
2) 02a_v13_end_{a,b}: Anchored directly to still_02a_v3_ref.png -> large ~15cm crimson soaked patch + 5-fingered right PALM pressing squarely INTO the wet blood
3) 02b2_v13_start + 02b2_v13_end_{a,b,c}: Stationary halted chest-clutched stance -> full-length SPRAWLED flat sideways collapse across dark pavement (legs stretched long, arms splayed limp, ZERO kowtow/curled kneel/steps dive)
"""

import base64
import re
import shutil
import sys
import threading
import time
from pathlib import Path

V09_DIR = Path(__file__).resolve().parent.parent / "v09_fixes"
V12_DIR = Path(__file__).resolve().parent.parent / "v12_fixes"
sys.path.insert(0, str(V09_DIR))
import stage1_keyframes_v09 as s1v9

VID_ROOT = s1v9.VID_ROOT
ROOT = VID_ROOT / "v13_fixes"
STILL_DIR = ROOT / "stills"
STILL_DIR.mkdir(parents=True, exist_ok=True)

# Stage verified reference stills locally before GPU launch
for src_name, dst_name in [
    ("still_01_v12_cutframe.png", "still_01_v13_cutframe.png"),
    ("still_02a_v3_ref.png", "still_02a_v13_start.png"),
    ("still_02b1_v12_t2i.png", "still_02b1_v13.png"),
]:
    src = V12_DIR / "stills" / src_name
    dst = STILL_DIR / dst_name
    if not dst.exists():
        shutil.copy2(src, dst)

NEG_REAR = (
    s1v9.NEG_PARIS
    + ", face visible, cheek profile turning toward camera, wide crab legs, wide straddle, diving sideways, leaping onto steps, "
    "bowing head into kowtow, yoga childs pose, knees tucked under belly, sitting on buttocks, hands propped behind hips, curled fetal ball, blurry distortion"
)
NEG_CHEST = (
    s1v9.NEG_PARIS
    + ", black vertical gash, black slit tear, ragged cutout hole, comic sunburst spikes, bright white studio background, "
    "tiny pinpoint dot stain only, hand avoiding stain, extra fingers, missing fingers, distorted thumb, watch, jewelry, face"
)

KEYFRAMES_V13 = [
    # --- 1. 01_v13_hit: Sudden frontal chest hit -> subtle backward torso shock arrest ---
    {
        "id": "01_v13_hit_a",
        "mode": "i2i_edit",
        "ref_still_id": "01_v13_cutframe",
        "seed": 13101,
        "neg": NEG_REAR,
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME Paris street camera angle, empty golden four limestone steps on left, flat stone pavement, "
            "dark multi-windowed Parisian building across road, off-white cotton crewneck sweatshirt, black trousers, sneakers, and "
            "STRICT REAR VIEW FROM BEHIND (man NEVER turns around, ZERO face or profile visible). Struck suddenly in the front upper "
            "chest by a bullet from across the road: his forward walk stops dead mid-step, feet planted in a narrow walking stride "
            "(rear leg stiffening, front heel catching weight, NO wide straddle, NO forward crouch). Instead of hunching forward, his "
            "upper spine and shoulders JERK SUBTLY BACKWARD AND STIFFEN IN SHOCK (~5-8cm crisp backward torso recoil, head snapping "
            "slightly back upright rather than bowing down), while his right hand starts swinging up/inward beside his ribs toward his chest."
        ),
    },
    {
        "id": "01_v13_hit_b",
        "mode": "i2i_edit",
        "ref_still_id": "01_v13_cutframe",
        "seed": 13102,
        "neg": NEG_REAR,
        "prompt": (
            "LOCK THE EXACT SAME Paris night street scene, left limestone steps, dark building facade ahead, plain off-white crewneck "
            "sweatshirt, black pants, and STRICTLY BACK-OF-HEAD REAR VIEW ONLY. Just hit high in the chest by a silent sniper round from "
            "in front: his stride halts instantly on flat pavement, torso whips slightly BACKWARD in sudden frontal impact recoil "
            "(shoulders thrown subtly back, chest pushed back-right slightly off balance, chin flicking up-back a fraction in shock rather "
            "than ducking down), left arm flinching subtly outward, right elbow pulling forward-inward as right hand moves up toward chest."
        ),
    },
    {
        "id": "01_v13_hit_c",
        "mode": "i2i_edit",
        "ref_still_id": "01_v13_cutframe",
        "seed": 13103,
        "neg": NEG_REAR,
        "prompt": (
            "EXACT SAME camera framing, golden left steps, flat pavement, dark building, clothing, and STRICT REAR VIEW FROM BEHIND "
            "(never show side cheek). On abrupt front-chest bullet strike, forward momentum breaks violently backward: knees stay narrow "
            "and braced catching weight on back heel, upper torso jolts slightly backward-to-the-right in authentic ballistic chest impact "
            "(upper back pulled taut and tilted slightly backward, head snapped slightly up-back, NOT hunched forward), right forearm bending "
            "inward across front ribcage."
        ),
    },

    # --- 2. 02a_v13_end: Large crimson chest soak + 5-fingered palm pressing squarely ON the wet blood ---
    {
        "id": "02a_v13_end_a",
        "mode": "i2i_edit",
        "ref_still_id": "02a_v13_start",
        "seed": 13201,
        "neg": NEG_CHEST,
        "prompt": (
            "KEEP THE EXACT SAME warm dark Paris bistro night amber bokeh background, exact off-white heavyweight cotton crewneck sweatshirt "
            "folds and lighting, and collarbone-to-waist framing (chin edge barely at top, face never visible). Expand the small chest stain "
            "into a DRAMATIC LARGE (~15cm wide) irregular organic dark-crimson bloodstain soaking deeply through the soft white fleece weave "
            "across his upper/center chest (authentic wet deep-crimson fabric saturation bleeding outward, ZERO black open gash or cut slit). "
            "Raise his clean anatomically accurate five-fingered right palm upward so his palm and pressing fingers rest FIRMLY DIRECTLY OVER "
            "the center-bottom of the large wet crimson bloodstain, with bright dark-red wet blood soaking around his fingertips and palm edge."
        ),
    },
    {
        "id": "02a_v13_end_b",
        "mode": "i2i_edit",
        "ref_still_id": "02a_v13_start",
        "seed": 13202,
        "neg": NEG_CHEST,
        "prompt": (
            "KEEP THE EXACT SAME warm Parisian night bistro bokeh lighting, off-white cotton crewneck texture, and shoulder-down framing. "
            "After the second chest hit, his chest cotton is saturated with a LARGE (~16cm) realistic wet dark-crimson blood soak spreading "
            "organically across upper chest (zero black slash tear, deep saturated burgundy/crimson cotton fiber bleed). His natural five-fingered "
            "bare right hand presses directly ON TOP OF the wet crimson blood patch — fingers curved pressing firmly against the soaked chest "
            "fabric, rich red blood clearly coating his fingertips and inner edge of his hand."
        ),
    },

    # --- 3. 02b2_v13_start: Halted wounded chest-clutch stance on pavement clear of stairs (NOT walking!) ---
    {
        "id": "02b2_v13_start",
        "mode": "i2i_edit",
        "ref_still_id": "01_v13_cutframe",
        "seed": 13401,
        "neg": NEG_REAR,
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME camera angle, empty four golden limestone steps on the far left untouched, wide dark flat stone "
            "sidewalk filling the center & right of frame, and dark Parisian building across street. Place the same man strictly from behind "
            "(zero face visible) standing HALTED on the center flat stone pavement (around center of frame well away from left steps, leaving "
            "wide empty stone ground on his right): NOT walking or stepping forward — both feet stopped flat as his knees suddenly buckle "
            "weakly beneath him, body weight losing support and beginning to sag slightly right/forward, right arm pressed tightly against front "
            "chest holding his chest wound, left arm hanging slack as his strength drains away."
        ),
    },

    # --- 4. 02b2_v13_end: Full-length flat sideways-prone sprawl across flat stone (limbs stretched, ZERO curl!) ---
    {
        "id": "02b2_v13_end_a",
        "mode": "i2i_edit",
        "ref_still_id": "02b2_v13_start",
        "seed": 13411,
        "neg": NEG_REAR,
        "prompt": (
            "STRICTLY LOCK THE EXACT SAME Paris street camera angle, exact four empty golden limestone steps on the far left completely empty "
            "and untouched, wide dark stone pavement, and dark Parisian building across the street. Directly on the flat dark stone pavement "
            "center-right (completely clear of the left stairs), the man in off-white crewneck sweatshirt, black trousers, and white sneakers "
            "has collapsed DEAD-WEIGHT AT FULL BODY LENGTH SPRAWLED FLAT ON HIS SIDE/FRONT along the ground: his entire body stretches out long "
            "diagonally from lower-center-left toward middle-right on the stone floor — both dark trousered legs and white sneakers EXTENDED "
            "OUT STRAIGHT AND LIMP BEHIND HIM (completely unbent, zero folded knees, zero sitting/kneeling hump), torso lying flat against the "
            "dark flagstones on his right chest/shoulder, head slumped flat sideways on pavement (back/side of dark hair only, zero face), and his "
            "left arm stretched/flung out limp sideways across the flagstones motionless."
        ),
    },
    {
        "id": "02b2_v13_end_b",
        "mode": "i2i_edit",
        "ref_still_id": "02b2_v13_start",
        "seed": 13412,
        "neg": NEG_REAR,
        "prompt": (
            "EXACT SAME locked wide street camera, untouched empty golden steps on far left, dark windowed building across road, dark flat stone "
            "ground. The mortally wounded man in white crewneck sweatshirt and black pants lies COMPLETELY STRETCHED OUT FLAT ON HIS SIDE/STOMACH "
            "across the center-right stone pavement: full human length extended horizontally/diagonally from center toward lower-right foreground "
            "like a felled tree — black pants legs stretched long and slack onto the pavement with white sneakers limp apart behind him (NEVER "
            "tucked under hips, NEVER crouched in a ball), white sweatshirt shoulder and chest flat flush against the cold stones, one arm flung "
            "out limp to the ground, dark head resting flat sideways face-down (strictly back of hair visible)."
        ),
    },
    {
        "id": "02b2_v13_end_c",
        "mode": "i2i_edit",
        "ref_still_id": "02b2_v13_start",
        "seed": 13413,
        "neg": NEG_REAR,
        "prompt": (
            "EXACT SAME night Paris street framing, untouched four golden steps far left, dark building across road. On the wide flat stone "
            "sidewalk center-right, the shot man lies completely limp and STRETCHED FULL LENGTH sideways-prone across the flagstones — body fully "
            "unfolded and flat to the ground (NO bent torso hump, NO tucked legs underneath, NO kneeling pose): long straight black trousers and "
            "sneakers trailing limp toward lower-left-center, flat white crewneck back/side pressed flat to stone toward center-right, outstretched "
            "loose arm resting palm-up/slack beside him, head down sideways in back view, completely motionless."
        ),
    },
]


def main():
    b64_cache: dict[Path, str] = {}
    stop_ka = threading.Event()
    try:
        print("[1/4] Waking EasyColab G4 GPU for Qwen-Image-2.1 Stage 1 (v0.13)...", flush=True)
        wake_out = s1v9.run_bridge("wake", "--gpu", "G4")
        print(wake_out, flush=True)
        if "WAKE_ERROR" in wake_out:
            raise RuntimeError(f"wake failed: {wake_out}")
        m = re.findall(r"https://[a-zA-Z0-9.-]+\.gradio\.live", wake_out)
        if not m:
            raise RuntimeError(f"Missing gradio.live URL:\n{wake_out}")
        base_url = m[-1].rstrip("/")

        threading.Thread(target=s1v9.keepalive_loop, args=(stop_ka,), daemon=True).start()

        st = s1v9.get_json(base_url, "/minimax_api/status?model_id=qwen_image_21")
        if not st.get("all_downloaded"):
            s1v9.post_json(base_url, "/minimax_api/download_model", {"model_id": "qwen_image_21"})
            while True:
                time.sleep(5.0)
                st = s1v9.get_json(base_url, "/minimax_api/status?model_id=qwen_image_21")
                if st.get("all_downloaded") and not st.get("is_downloading"):
                    break
        if not st.get("model_loaded"):
            s1v9.post_json(base_url, "/minimax_api/load_model", {"model_id": "qwen_image_21", "precision_mode": "bf16", "offload_mode": "disk"})
            while True:
                time.sleep(4.0)
                st = s1v9.get_json(base_url, "/minimax_api/status?model_id=qwen_image_21")
                if st.get("model_loaded") and not st.get("is_loading_vram"):
                    break
                msg = st.get("task_message", "")
                if not st.get("is_loading_vram") and not st.get("model_loaded") and "失败" in msg:
                    raise RuntimeError(f"load_model failed: {msg}")
        print("  qwen_image_21 loaded!", flush=True)

        print(f"[3/4] Generating {len(KEYFRAMES_V13)} keyframes...", flush=True)
        for item in KEYFRAMES_V13:
            kid = item["id"]
            out_path = STILL_DIR / f"still_{kid}.png"
            if out_path.exists() and out_path.stat().st_size > 20_000:
                print(f"  [skip] {out_path.name}", flush=True)
                continue
            rp = STILL_DIR / f"still_{item['ref_still_id']}.png"
            if not rp.exists():
                raise FileNotFoundError(f"Missing reference: {rp}")
            if rp not in b64_cache:
                b64_cache[rp] = base64.b64encode(rp.read_bytes()).decode("ascii")
            payload = {
                "model_id": "qwen_image_21",
                "task_mode": item["mode"],
                "first_frame_base64": b64_cache[rp],
                "visual_prompt": item["prompt"],
                "negative_prompt": item["neg"],
                "width": 1280,
                "height": 720,
                "num_inference_steps": 30,
                "seed": item["seed"],
                "randomize_seed": False,
                "batch_count": 1,
            }
            t0 = time.time()
            print(f"  [submit] still_{kid} (seed={item['seed']}) ...", flush=True)
            job = s1v9.post_json(base_url, "/minimax_api/generate", payload)
            jid = job.get("job_id")
            if not jid or job.get("status") == "failed":
                raise RuntimeError(f"Submit failed for {kid}: {job}")
            while True:
                time.sleep(2.0)
                st = s1v9.get_json(base_url, f"/minimax_api/job/{jid}")
                status = st.get("status")
                if status == "completed":
                    s1v9.download_file(base_url, f"/minimax_api/media/{st['filename']}", out_path)
                    print(f"  [done]   still_{kid}.png ({out_path.stat().st_size // 1024} KB, {time.time() - t0:.1f}s)", flush=True)
                    break
                elif status == "failed":
                    raise RuntimeError(f"Job failed for {kid}: {st.get('message')}")
        print("STAGE 1 KEYFRAMES (v0.13) DONE!", flush=True)
    finally:
        stop_ka.set()
        print("[4/4] IMMEDIATELY stopping all Colab GPUs (stop_all)...", flush=True)
        for attempt in range(4):
            out = s1v9.run_bridge("stop_all")
            print(out, flush=True)
            if '"ok": true' in out and '"burn_rate_hourly": 0.0' in out:
                break
            time.sleep(3.0 * (attempt + 1))
        print("[auth_status check]", flush=True)
        print(s1v9.run_bridge("auth_status"), flush=True)


if __name__ == "__main__":
    main()
