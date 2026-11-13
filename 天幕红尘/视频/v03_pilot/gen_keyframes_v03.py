#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate v0.3 zero-flaw cinema keyframes (1280x720) on EasyColab G4 using Qwen-Image-2.1."""

import base64
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

BASE_URL = os.environ.get("EASYCOLAB_URL", "").rstrip("/")
V02_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v02_pilot")
ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v03_pilot")
STILL_DIR = ROOT / "stills"
STILL_DIR.mkdir(parents=True, exist_ok=True)

LUO_REF_PATH = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/ref/罗家明.png")
SU_REF_PATH = V02_ROOT / "stills" / "still_08.png"

LUO_B64 = base64.b64encode(LUO_REF_PATH.read_bytes()).decode("ascii")
SU_B64 = base64.b64encode(SU_REF_PATH.read_bytes()).decode("ascii")

STYLE = (
    "1991 Kodak Vision 35mm cinema film still, anamorphic lens, natural skin texture, "
    "subtle film grain, realistic chiaroscuro lighting, shallow depth of field, no subtitles, no watermarks."
)
NEG = (
    "cartoon, anime, CGI, 3d render, oversaturated, plastic skin, modern smartphone, "
    "flatscreen monitor, watermark, subtitle, extra fingers, deformed hands, blurry text, face visible in back shot"
)

KEYFRAMES = [
    {
        "id": "01_v3",
        "mode": "t2i",
        "seed": 199301,
        "prompt": (
            "Night in Paris on a wide quiet upscale commercial street. Camera positioned behind a man on the upper "
            "landing of four wide classical stone steps outside a grand French restaurant whose heavy glass-and-brass "
            "doors stand slightly ajar behind him, spilling warm golden chandelier glow onto wet stone paving slabs. "
            "Strictly back view — the man's head and face are turned completely away and never visible. He wears a "
            "plain loose white crewneck cotton sports pullover sweatshirt (NO hood, NOT a suit) and casual sneakers, "
            "stepping casually down the four stone steps toward the street. Directly across the wide dark boulevard "
            "looms an imposing dark grey 8-story building packed densely with hundreds of small dark windows. " + STYLE
        ),
    },
    {
        "id": "02a_v3",
        "mode": "t2i",
        "seed": 199302,
        "prompt": (
            "Extreme close-up framed strictly from the lower chest and sternum to the waist — NO neck, NO chin, "
            "NO jaw, head completely above and outside the top frame border. Night outside a warm-lit French restaurant "
            "in Paris. A man wears a clean plain white crewneck cotton sweatshirt; a small fresh wet crimson bullet "
            "impact stain has just appeared on the left-center chest of the white cotton fabric, and his right hand "
            "is reaching upward into frame to touch the fresh red stain. " + STYLE
        ),
    },
    {
        "id": "02b_v3",
        "mode": "t2i",
        "seed": 199303,
        "prompt": (
            "Low-angle ground-level 35mm night shot on wet classical stone steps outside a French restaurant in Paris, "
            "framed strictly from the knees and stone steps up to the mid-back — head and face completely out of frame. "
            "Seen from behind in warm golden doorway backlight against the dark Paris street ahead, a man in a white "
            "cotton sweatshirt, casual trousers, and white-grey sneakers has his knees buckling sharply inward as his "
            "body loses balance and begins collapsing downward onto the wet stone steps. " + STYLE
        ),
    },
    {
        "id": "04_v3",
        "mode": "t2i",
        "seed": 199304,
        "prompt": (
            "Wide establishing cinema shot looking slightly upward at a massive gloomy 15-story Soviet modernist concrete "
            "office building on a deserted rain-slicked Moscow boulevard at midnight in August 1991. Closed storefronts "
            "with pulled-down metal shutters line the empty wet street below. Every single window across the entire "
            "dark facade of the towering building is completely pitch black EXCEPT for ONE solitary brightly glowing "
            "warm amber-yellow office window high up on the 12th floor east corner, standing out starkly against the "
            "cold blue-black Moscow night sky. " + STYLE
        ),
    },
    {
        "id": "05_ins1",
        "mode": "t2i",
        "seed": 199305,
        "prompt": (
            "Moody macro close-up on a dark mahogany executive desk at midnight in a 1991 Moscow office lit by a single "
            "warm brass desk lamp. In sharp foreground sits a heavy cut-glass ashtray overflowing with half a bowl of "
            "crushed cigarette butts, a thin wisp of grey smoke curling up from a freshly stubbed cigarette. In the "
            "dark out-of-focus background corner glows a small boxy Soviet CRT television showing a blurred grey-haired "
            "politician in blue phosphor light. " + STYLE
        ),
    },
    {
        "id": "05_ins2",
        "mode": "i2i_edit",
        "ref": "su",
        "seed": 199306,
        "prompt": (
            "Transform into a warm desk-lamp close-up of a wooden tabletop photo frame resting on the corner of a dark "
            "mahogany office desk at night. Inside the wooden frame is a realistic 1990s color family photograph taken "
            "outdoors in front of an upscale New York Chinese restaurant entrance with a gold-lettered plaque '裕香阁'. "
            "The photograph shows ONLY FOUR CHINESE WOMEN standing close together smiling warmly (NO men, NO elderly man): "
            "the exact 70-year-old silver-haired Chinese grandmother with thin glasses from the reference image in the "
            "center, beside a poised 38-year-old Chinese woman (wife), a 35-year-old Chinese woman (younger sister), "
            "and a 12-year-old Chinese girl (daughter). Shallow depth of field on the dark desk. " + STYLE
        ),
    },
    {
        "id": "05c_v3",
        "mode": "t2i",
        "seed": 199307,
        "prompt": (
            "Tight low-key 35mm macro close-up on a dark mahogany executive desk at midnight under warm brass lamp light "
            "in 1991 Moscow. A man's left hand holds a black coiled-cord vintage telephone receiver slightly away from "
            "his ear at the upper edge while his right hand in a white dress shirt cuff and steel wristwatch extends "
            "his index finger directly above the black plastic cradle hook-switch button on the desk telephone base, "
            "poised to press down and disconnect the call. " + STYLE
        ),
    },
    {
        "id": "06b_v3",
        "mode": "t2i",
        "seed": 199308,
        "prompt": (
            "Close-up in a dark wood-paneled 1991 Moscow office at midnight of a small boxy vintage Soviet CRT television "
            "set on a wooden stand. The curved glass CRT screen glows cold blue-white showing a slightly blurred Soviet "
            "news broadcast of a grey-haired statesman at a desk; from the left side of the frame, a man's hand in a "
            "white dress shirt cuff reaches right up to the physical mechanical power push-button on the front bezel "
            "of the television, ready to click it off. " + STYLE
        ),
    },
    {
        "id": "08a_v3",
        "mode": "t2i",
        "seed": 199309,
        "prompt": (
            "Warm sunlit 1991 Manhattan New York apartment afternoon close-up of a wooden side table beside sheer golden "
            "window curtains. On the polished table sit a clear glass of water, a small plastic pill organizer box, a "
            "cream embossed invitation card, and a classic beige corded desk telephone with its receiver resting on the "
            "cradle; from the right edge, the gentle aged hand of a 70-year-old Chinese woman in a soft beige knit "
            "cardigan sleeve reaches gracefully toward the beige telephone receiver to pick it up. " + STYLE
        ),
    },
    {
        "id": "09a_v3",
        "mode": "i2i_edit",
        "ref": "luo",
        "seed": 199310,
        "prompt": (
            "Keep the exact same 42-year-old Chinese man from the reference image (same facial structure, eyebrows, "
            "short black hair with greying temples, white shirt collar, loosened dark maroon tie). Tight emotional "
            "35mm close-up in a dark 1991 Moscow office at midnight, half his face lit by warm amber desk-lamp light "
            "and half in deep shadow. He presses a black corded telephone receiver against his right ear with tense "
            "white knuckles; his reddened eyes glisten quietly with unshed tears, his lips pressed tightly together "
            "in silent choked grief, completely unable to speak. " + STYLE
        ),
    },
    {
        "id": "09b_v3",
        "mode": "t2i",
        "seed": 199311,
        "prompt": (
            "Extreme close-up on a dark mahogany desk at midnight under a single warm brass desk lamp in 1991 Moscow. "
            "A man's pale hand in a white shirt cuff holds a black corded vintage telephone receiver just two centimeters "
            "above the black telephone base cradle, lowering it down with agonizing slowness and tenderness onto the "
            "hook switch in dead silence. " + STYLE
        ),
    },
    {
        "id": "10a_v3",
        "mode": "t2i",
        "seed": 199312,
        "prompt": (
            "High-angle macro 35mm close-up on a dark mahogany desk at midnight under warm brass lamp light. Inside an "
            "open crimson velvet box lies a vintage blued-steel WWII revolver with its six-chamber cylinder swung OPEN "
            "outward to the left, clearly exposing the empty round chambers; a man's right thumb and index finger in a "
            "white shirt cuff and steel wristwatch slide a single gleaming brass .38 cartridge halfway into one open "
            "chamber of the swung-out cylinder. Glass ashtray with cigarette butts at left. " + STYLE
        ),
    },
    {
        "id": "10b_v3",
        "mode": "t2i",
        "seed": 199313,
        "prompt": (
            "High-angle macro 35mm close-up on a dark mahogany executive desk at midnight lit by a warm brass lamp. "
            "At the upper left edge rests the dark blued-steel WWII revolver on the wood; in the sharp center foreground "
            "lies a clean white sheet of letter paper where a man's right hand in a white shirt cuff and steel wristwatch "
            "holds an UNCAPPED black gold-nib fountain pen, its nib touching the paper midway through writing two short "
            "neat lines of black ink handwriting. " + STYLE
        ),
    },
    {
        "id": "11b_v3",
        "mode": "i2i_edit",
        "ref": "luo",
        "seed": 199314,
        "prompt": (
            "Keep the exact same 42-year-old Chinese man from the reference image (same face, hair, white dress shirt, "
            "loosened dark maroon tie). Tight slightly low-angle chiaroscuro close-up in a dark wood-paneled 1991 Moscow "
            "office at midnight: he stares slightly upward toward an off-screen wall with hollow, desolate, utterly calm "
            "eyes, warm amber lamp glow grazing one cheek while the rest of the room sinks into pitch shadow. " + STYLE
        ),
    },
    {
        "id": "12b_v3",
        "mode": "t2i",
        "seed": 199315,
        "prompt": (
            "Extreme macro eye-level 35mm close-up of the sharp front corner bevel of a dark mahogany desk at midnight. "
            "A warm brass desk lamp from the upper left rim-lights a vivid, glossy bright-crimson stream of fresh blood "
            "creeping over the polished wooden desk edge, forming a heavy glistening ruby-red droplet suspended mid-drip "
            "against the pitch-black shadow below the desk. In the softly blurred background on top of the desk sits "
            "the black vintage telephone with a spotless white sheet of paper resting cleanly across its receiver. " + STYLE
        ),
    },
]


def post_json(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def get_json(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=30) as resp:
        return json.loads(resp.read())


def download_file(path: str, dst: Path):
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=120) as resp:
        dst.write_bytes(resp.read())


def main():
    if not BASE_URL:
        raise RuntimeError("EASYCOLAB_URL env var is required")
    force = "--force" in sys.argv
    only_ids = [a for a in sys.argv[1:] if not a.startswith("--")]

    for item in KEYFRAMES:
        kid = item["id"]
        if only_ids and kid not in only_ids:
            continue
        out_path = STILL_DIR / f"still_{kid}.png"
        if out_path.exists() and out_path.stat().st_size > 10000 and not force:
            print(f"[skip] still_{kid}.png exists ({out_path.stat().st_size // 1024} KB)", flush=True)
            continue

        payload = {
            "model_id": "qwen_image_21",
            "task_mode": item["mode"],
            "visual_prompt": item["prompt"],
            "negative_prompt": NEG,
            "width": 1280,
            "height": 720,
            "num_inference_steps": 30,
            "seed": item["seed"],
            "randomize_seed": False,
            "batch_count": 1,
        }
        if item.get("ref") == "luo":
            payload["first_frame_base64"] = LUO_B64
        elif item.get("ref") == "su":
            payload["first_frame_base64"] = SU_B64

        t0 = time.time()
        print(f"[submit] still_{kid} ({item['mode']}) ...", flush=True)
        job = post_json("/minimax_api/generate", payload)
        jid = job.get("job_id")
        if not jid or job.get("status") == "failed":
            raise RuntimeError(f"Submit failed for {kid}: {job}")

        while True:
            time.sleep(2.0)
            st = get_json(f"/minimax_api/job/{jid}")
            status = st.get("status")
            if status == "completed":
                fname = st["filename"]
                download_file(f"/minimax_api/media/{fname}", out_path)
                print(
                    f"[done]   still_{kid}.png ({out_path.stat().st_size // 1024} KB, {time.time() - t0:.1f}s)",
                    flush=True,
                )
                break
            elif status == "failed":
                raise RuntimeError(f"Job failed for {kid}: {st.get('message')}")

    print("ALL V0.3 KEYFRAMES GENERATED SUCCESSFULLY!", flush=True)


if __name__ == "__main__":
    main()
