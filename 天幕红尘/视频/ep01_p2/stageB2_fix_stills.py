#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage B2-fix (ep01_p2): Targeted Qwen-Image-2.1 regeneration of defective/continuity-broken keyframes."""

import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stageB2_keyframes_p2 as sb2

VID_ROOT = sb2.VID_ROOT
STILL_DIR = sb2.STILL_DIR
STYLE = sb2.STYLE
NEG_NY = sb2.NEG_NY

NO_SMILE = (
    ", smiling, smile, grin, cheerful, smirk, pleasant expression, teeth showing in a smile, laughing"
)

FIX_KEYFRAMES = [
    # 1. 14_end: natural warm skin pallor + horror (avoid monochrome ghost/zombie skin)
    {
        "id": "14_end",
        "mode": "i2i_edit",
        "ref_still_id": "14_start",
        "seed": 7202,
        "neg": NEG_NY + NO_SMILE + ", monochrome skin, grey zombie makeup, chalk white facepaint, painted white skin",
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME camera angle, sunlit Manhattan living room, curtains, bookshelves, "
            "wooden table with clear water glass, and the exact same 35-year-old Chinese woman holding the beige handset, keeping natural human skin tone. "
            "Now her expression turns suddenly pale-tense and terrified with shock: eyebrows drawn tightly up in horror, wide frightened eyes staring ahead, "
            "lips parted trembling in disbelief as she hears devastating news. " + STYLE
        ),
    },
    # 2. 15_end: remove phantom extra hand on shoulder; keep clean empty shoulder + dangling handset
    {
        "id": "15_end",
        "mode": "i2i_edit",
        "ref_still_id": "15_start",
        "seed": 7212,
        "neg": NEG_NY + NO_SMILE + ", hand on shoulder, touching shoulder, fingers on sweater, third hand, extra arm, holding receiver to ear",
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME tight medium close-up camera framing, warm sunlit Manhattan apartment background, and the exact same 35-year-old woman in soft-grey knit sweater. "
            "REMOVE her hand from her ear so BOTH shoulders remain completely empty with NO hand or fingers touching her shoulders (left arm dropped low completely out of frame). "
            "The beige telephone handset has slipped from her grasp and hangs suspended upside-down on its coiled beige cord in front of her chest; "
            "her face is frozen in wide-eyed trembling silent shock, mouth slackened open in grief. " + STYLE
        ),
    },
    # 3. 16_start: edit backwards from unsmiling worried 16_end so Lin does NOT smile!
    {
        "id": "16_start",
        "mode": "i2i_edit",
        "ref_still_id": "16_end",
        "seed": 7221,
        "neg": NEG_NY + NO_SMILE + ", handset held to ear, standing calm",
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME 38-year-old Chinese woman (same face, hair, dark grey-taupe collared top, cream apron), "
            "the EXACT SAME Manhattan apartment hallway, round dark wooden table with clear water glass and beige telephone base. "
            "Do NOT smile — give her an urgent panicked frantic scowl with brows tightly furrowed. "
            "Pose her one stride earlier rushing urgently forward toward the table: the beige telephone handset is dangling loose off the side of the table edge, "
            "and she leans down stretching her right five-fingered hand mid-reach to snatch the dangling handset before it falls. " + STYLE
        ),
    },
    # 4. 18a_end_a: edit from 17_end REMOVE upright glass on table, keep only ONE fallen glass spilling water on floor
    {
        "id": "18a_end_a",
        "mode": "i2i_edit",
        "ref_still_id": "17_end",
        "seed": 7241,
        "neg": NEG_NY + ", standing upright, glass sitting on table, upright water glass on table, two glasses",
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME camera angle, sunlit Manhattan living room, sheer curtains left, bookshelves right, sofa and wooden coffee table. "
            "REMOVE the upright glass of water completely from the top of the wooden coffee table so the wood tabletop spot beside the phone is completely bare with only a wet splash trail. "
            "The 70-year-old silver-haired woman in the beige cardigan has collapsed stiffly backward down onto the floor beside the sofa behind the table, "
            "lying unconscious on the rug with one trembling hand still near her chest; that single clear glass water tumbler has fallen off the coffee table onto the wooden floor in the foreground, lying overturned in shattered shards and spilled water. " + STYLE
        ),
    },
    # 5. 20_start: edit backwards from clean 20_end putting blue surgical mask UP over nose & mouth!
    {
        "id": "20_start",
        "mode": "i2i_edit",
        "ref_still_id": "20_end",
        "seed": 7271,
        "neg": NEG_NY + NO_SMILE + ", uncovered mouth, nose uncovered, mask hanging under chin, bare lower face",
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME 45-year-old American male surgeon (same eyes, hair, white coat over pale blue scrubs, stethoscope), "
            "the EXACT SAME frosted hospital ER corridor doors and cool fluorescent lighting. "
            "Move the pale blue medical surgical mask UP so it snugly covers his nose and mouth completely (only his somber tired eyes and forehead visible above the mask), "
            "while his clean five-fingered right hand reaches up gripping the bottom fold of the blue mask beginning to pull it downward. " + STYLE
        ),
    },
    # 6. 21a_start -> 21a_end: consistent medium-full shot standing then slid down wall in dark pants/shoes
    {
        "id": "21a_start",
        "mode": "i2i_edit",
        "ref": sb2.REF_DIR / "罗慧娟.png",
        "seed": 7281,
        "neg": NEG_NY + NO_SMILE + ", sitting on floor, cropped at chest, sunlit living room",
        "prompt": (
            "Keep the EXACT same 35-year-old Chinese woman (same face, black hair, soft-grey knit sweater), wearing dark charcoal trousers and black flat shoes. "
            "Cold pale green-white 1991 hospital corridor at night under dim cool fluorescent overhead lights, wet reflections on tiled linoleum floor, long corridor vanishing behind right. "
            "Medium-wide three-quarter shot of her STANDING leaning weakly with her back against the flat painted corridor wall on the left, "
            "knees trembling and just beginning to buckle under shock, face crumpled weeping in helpless grief. " + STYLE
        ),
    },
    {
        "id": "21a_end",
        "mode": "i2i_edit",
        "ref_still_id": "21a_start",
        "seed": 7282,
        "neg": NEG_NY + NO_SMILE + ", standing tall, camera zoom in",
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME static camera position, wide hospital corridor background, cool fluorescent lighting, flat left painted wall, "
            "and the exact same woman in soft-grey sweater, charcoal trousers, and dark flat shoes. "
            "Now she has slid all the way down the wall onto the linoleum floor, seated slumped tightly against the baseboard with knees drawn up and head bowed sobbing uncontrollably. " + STYLE
        ),
    },
    # 7. 21b_start: seated slumped (NOT lying flat, NO weird tan blob in foreground left) beating floor weakly
    {
        "id": "21b_start",
        "mode": "i2i_edit",
        "ref": sb2.REF_DIR / "罗慧娟.png",
        "seed": 7291,
        "neg": NEG_NY + NO_SMILE + ", lying horizontal sleeping, brown bag foreground, apartment",
        "prompt": (
            "Keep the EXACT same 35-year-old Chinese woman (same face, shoulder-length black hair, soft-grey knit sweater, dark charcoal pants). "
            "Low-angle medium close-up SEATED UPRIGHT slumped against the base of a cold sterile white painted 1991 hospital hallway wall on empty gray linoleum tiles under cool fluorescent night light (completely clear empty foreground floor left and right). "
            "Face wet with tears, mouth crying brokenly upward/forward in despair as one five-fingered clenched fist beats weakly against the bare hospital floor beside her leg. " + STYLE
        ),
    },
    # 8. 22_start: edit backwards from unsmiling steely 22_end so she clearly BITES LOWER LIP with unshed tears!
    {
        "id": "22_start",
        "mode": "i2i_edit",
        "ref_still_id": "22_end",
        "seed": 7301,
        "neg": NEG_NY + NO_SMILE + ", relaxed calm lips, happy eyes",
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME 38-year-old Chinese woman (exact same face, dark shoulder-length hair, dark grey-taupe collared top, NO smile), "
            "and the EXACT SAME cold white painted 1991 hospital corridor wall and pale fluorescent night lighting. "
            "Make her eyes glistening red-rimmed brimming with unshed tears, brows tense with suppressed grief, and her upper teeth visibly BITING down onto her trembling lower lip as she holds back tears. " + STYLE
        ),
    },
    # 9. 23_end FIRST (anchored to cold white hospital still_22_end, ZERO smile, cold hospital wall!) -> then 23_start!
    {
        "id": "23_end",
        "mode": "i2i_edit",
        "ref_still_id": "22_end",
        "seed": 7312,
        "neg": NEG_NY + NO_SMILE + ", apron, warm wooden doorway, bookshelves, extra arm, three hands",
        "prompt": (
            "Keep the EXACT same unsmiling 38-year-old Chinese woman (same face, shoulder-length hair, dark grey-taupe collared top, stern cold iron-willed scowl — strictly unsmiling) "
            "inside the SAME cold sterile pale white-green 1991 hospital hallway at night under fluorescent tubes (white painted corridor wall behind left). "
            "Medium shot facing left at close eye-level: with both five-fingered hands she firmly grips the soft-grey knit sweater shoulders of another 35-year-old dark-haired Chinese woman "
            "(seen from 3/4 rear-left angle pressed upright against the white hospital wall), staring fiercely and urgently into her eyes commanding her to stop crying. " + STYLE
        ),
    },
    {
        "id": "23_start",
        "mode": "i2i_edit",
        "ref_still_id": "23_end",
        "seed": 7311,
        "neg": NEG_NY + NO_SMILE + ", apron, warm wood paneling, extra arm",
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME static camera position, cold pale white-green 1991 hospital corridor wall, fluorescent lighting, and exact clothes and unsmiling stern face of the 38-year-old woman. "
            "Pose them one action earlier: the grey-sweatered younger woman is still slumped low kneeling down on the floor on the left against the baseboard, "
            "while the 38-year-old woman on the right bends sharply downward grabbing the grey sweater shoulders with both five-fingered hands to yank her upright off the floor. " + STYLE
        ),
    },
]


def ensure_qwen(base_url: str):
    st = sb2.http_json(f"{base_url}/minimax_api/status?model_id=qwen_image_21")
    if not st.get("all_downloaded"):
        sb2.http_json(f"{base_url}/minimax_api/download_model", {"model_id": "qwen_image_21"})
        while True:
            time.sleep(5.0)
            st = sb2.http_json(f"{base_url}/minimax_api/status?model_id=qwen_image_21")
            if st.get("all_downloaded") and not st.get("is_downloading"):
                break
    if not st.get("model_loaded"):
        sb2.http_json(f"{base_url}/minimax_api/load_model", {"model_id": "qwen_image_21", "precision_mode": "bf16", "offload_mode": "disk"})
        while True:
            time.sleep(4.0)
            st = sb2.http_json(f"{base_url}/minimax_api/status?model_id=qwen_image_21")
            if st.get("model_loaded") and not st.get("is_loading_vram"):
                break


def main():
    stop_ka = threading.Event()
    b64_cache: dict[Path, str] = {}
    try:
        print(f"[1/4] Waking EasyColab G4 GPU for Qwen-Image-2.1 Stage B2-fix ({len(FIX_KEYFRAMES)} stills)...", flush=True)
        wake_out = sb2.run_bridge("wake", "--gpu", "G4")
        print(wake_out, flush=True)
        if "WAKE_ERROR" in wake_out:
            raise RuntimeError(f"wake failed: {wake_out}")
        m = re.findall(r"https://[a-zA-Z0-9.-]+\.gradio\.live", wake_out)
        if not m:
            raise RuntimeError("Missing gradio.live URL")
        base_url = m[-1].rstrip("/")

        threading.Thread(target=sb2.keepalive_loop, args=(stop_ka,), daemon=True).start()

        print("[2/4] Ensuring qwen_image_21 loaded on G4...", flush=True)
        ensure_qwen(base_url)

        print(f"[3/4] Regenerating {len(FIX_KEYFRAMES)} fixed keyframes...", flush=True)
        for item in FIX_KEYFRAMES:
            out_path = STILL_DIR / f"still_{item['id']}.png"
            ref_path = STILL_DIR / f"still_{item['ref_still_id']}.png" if "ref_still_id" in item else item["ref"]
            if not ref_path.exists():
                raise FileNotFoundError(f"Missing ref_path: {ref_path}")
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
                # Do NOT cache if ref_path was itself regenerated in this loop!
                payload["first_frame_base64"] = __import__("base64").b64encode(ref_path.read_bytes()).decode("ascii")
            t0 = time.time()
            job = sb2.http_json(f"{base_url}/minimax_api/generate", payload)
            jid = job["job_id"]
            while True:
                time.sleep(2.0)
                jst = sb2.http_json(f"{base_url}/minimax_api/job/{jid}")
                if jst.get("status") == "completed":
                    fn = jst.get("filename") or Path(jst["filepath"]).name
                    sb2.download_bytes(f"{base_url}/minimax_api/media/{fn}", out_path)
                    print(f"  [saved] {out_path.name} ({out_path.stat().st_size // 1024} KB, {time.time() - t0:.1f}s)", flush=True)
                    break
                if jst.get("status") in ("failed", "error"):
                    raise RuntimeError(f"Job failed {out_path.name}: {jst}")

    finally:
        stop_ka.set()
        print("[4/4] Stopping EasyColab GPU (stop_all)...", flush=True)
        for attempt in range(4):
            out = sb2.run_bridge("stop_all")
            print(out, flush=True)
            if '"ok": true' in out and '"burn_rate_hourly": 0.0' in out:
                break
            time.sleep(3.0 * (attempt + 1))
        print("[auth_status]", sb2.run_bridge("auth_status"), flush=True)


if __name__ == "__main__":
    main()
