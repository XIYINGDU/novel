#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate 12 consistent 1280x720 cinema keyframes on EasyColab G4 using Qwen-Image-2.1."""

import base64
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

BASE_URL = os.environ.get("EASYCOLAB_URL", "https://b7c1afb6b9587feb07.gradio.live").rstrip("/")
ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v02_pilot")
STILL_DIR = ROOT / "stills"
STILL_DIR.mkdir(parents=True, exist_ok=True)
LUO_REF_PATH = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/ref/罗家明.png")

LUO_B64 = base64.b64encode(LUO_REF_PATH.read_bytes()).decode("ascii")

STYLE = (
    "1991 Kodak Vision 35mm cinema film still, anamorphic lens, natural skin texture, "
    "subtle film grain, realistic lighting, shallow depth of field, no subtitles, no watermarks."
)
NEG = (
    "cartoon, anime, CGI, 3d render, oversaturated, plastic skin, modern smartphone, "
    "flatscreen monitor, watermark, subtitle, extra fingers, deformed hands, blurry text"
)

KEYFRAMES = [
    {
        "id": "01",
        "mode": "t2i",
        "seed": 199101,
        "prompt": (
            "Night in Paris on a quiet upscale street. Camera positioned behind a man at waist-to-shoulder height, "
            "strictly back view, his face completely hidden and never visible. The man wears a plain loose white "
            "crewneck cotton sports sweatshirt (pullover crewneck, NOT a suit, NO hood) and casual white-grey sneakers, "
            "walking relaxed down four wide classical stone steps outside an elegant French restaurant with warm golden "
            "door light spilling onto wet-sheen large stone paving slabs. Across the dark street rises a tall building "
            "dense with rows of dark and dimly lit windows. " + STYLE
        ),
    },
    {
        "id": "02",
        "mode": "t2i",
        "seed": 199102,
        "prompt": (
            "Tight cinematic close-up at night framed strictly from the collarbone and shoulders down to the waist — "
            "head and face completely out of frame above the top edge. A man wearing a plain white crewneck cotton "
            "sports sweatshirt stands on stone steps at night; a vivid dark-crimson bloodstain is spreading rapidly "
            "across the center-left chest of the white sweatshirt fabric. His right hand reaches up and presses gently "
            "against the bloodstained chest, fingertips stained dark red. Warm French restaurant doorway glow behind, "
            "dark Paris street bokeh ahead. " + STYLE
        ),
    },
    {
        "id": "04",
        "mode": "t2i",
        "seed": 199104,
        "prompt": (
            "Wide establishing shot of a deserted Moscow boulevard at midnight in August 1991. Rain-slicked wet black "
            "asphalt reflecting dim sodium streetlights, closed Soviet-era shops with pulled-down metal shutters, "
            "distant red taillights of a lone Soviet Volga sedan fading down the empty avenue. Dominating the night "
            "skyline is a dark gloomy 15-story Soviet modernist office tower, every window pitch black except for one "
            "solitary warm amber-lit office window on the 12th floor east corner. Cold blue-grey Soviet night palette. "
            + STYLE
        ),
    },
    {
        "id": "05",
        "mode": "i2i_edit",
        "ref": "luo",
        "seed": 199105,
        "prompt": (
            "Keep the exact same 42-year-old Chinese man from the reference image (same face, weathered expression, "
            "short black hair with slight grey at the temples, white dress shirt with rolled sleeves, loosened dark "
            "maroon tie, and steel wristwatch). Transform the scene into a dark wood-paneled 1991 Moscow executive "
            "office at midnight, lit only by a single warm brass desk lamp on a heavy dark wooden desk. He stands "
            "leaning slightly over the desk holding a black corded vintage telephone receiver to his right ear, his "
            "face exhausted and ashen, looking down calmly at a framed family photograph on the corner of the desk "
            "next to a glass ashtray half-full of cigarette butts. In the dim background corner, a small boxy Soviet "
            "CRT television glows faint blue showing a blurred grey-haired Soviet politician speaking. Chiaroscuro "
            "low-key lighting. " + STYLE
        ),
    },
    {
        "id": "06",
        "mode": "i2i_edit",
        "ref": "luo",
        "seed": 199106,
        "prompt": (
            "Keep the exact same 42-year-old Chinese man from the reference image (same face, hair, white dress shirt, "
            "loosened dark maroon tie, steel wristwatch). Medium three-quarter side-profile shot standing beside an "
            "open 12th-floor office window at midnight in 1991 Moscow. Cold dark-blue Moscow city lights twinkle far "
            "below outside the open window; dim warm desk-lamp glow behind him inside the dark wood-paneled office. "
            "He holds a lit cigarette near the window sill with thin grey smoke drifting into the night air, turning "
            "his eyes coldly sideways over his shoulder toward the faint blue CRT television glow inside the room. "
            + STYLE
        ),
    },
    {
        "id": "07",
        "mode": "i2i_edit",
        "ref": "luo",
        "seed": 199107,
        "prompt": (
            "Keep the exact same 42-year-old Chinese man from the reference image (same face, hair, white dress shirt, "
            "loosened dark maroon tie, steel wristwatch). Medium close-up seated behind a dark wooden executive desk "
            "in a pitch-quiet 1991 Moscow office at midnight under a single warm brass desk lamp. In the near desk "
            "corner stands a wooden photo frame showing a warm family photo. His left hand holds a black corded "
            "telephone receiver near his chest while his right index finger presses the push-buttons of the black "
            "desk telephone to dial an international call, his eyes fixed sorrowfully on the family photo frame. "
            + STYLE
        ),
    },
    {
        "id": "08",
        "mode": "t2i",
        "seed": 199108,
        "prompt": (
            "Medium shot inside a warm sunlit 1991 Manhattan New York apartment living room in the afternoon. Soft "
            "golden sunlight streams through sheer window curtains onto wooden bookshelves filled with Chinese and "
            "English books. A refined, gentle 70-year-old retired Chinese female professor with neat silver-grey hair, "
            "wearing thin-rimmed glasses and a soft beige knit cardigan over a collared blouse, sits beside a small "
            "table with a glass of warm water, a small pill box, and a cream embossed invitation card; she smiles "
            "warmly and affectionately as she holds a classic beige corded telephone receiver to her ear. " + STYLE
        ),
    },
    {
        "id": "09",
        "mode": "i2i_edit",
        "ref": "luo",
        "seed": 199109,
        "prompt": (
            "Keep the exact same 42-year-old Chinese man from the reference image (same facial structure, eyebrows, "
            "short black hair with greying temples, white shirt collar, loosened dark maroon tie). Tight emotional "
            "close-up in a dark 1991 Moscow office at midnight, half his face illuminated by warm amber desk-lamp "
            "light and half in deep shadow. He grips a black corded telephone receiver tightly against his right ear "
            "with pale tense knuckles; his eyes are reddened and glistening with unshed tears, his throat tense, his "
            "lips slightly parted and trembling in complete wordless grief unable to utter a single sound. " + STYLE
        ),
    },
    {
        "id": "10",
        "mode": "t2i",
        "seed": 199110,
        "prompt": (
            "High-angle close-up on a dark mahogany executive desk at midnight illuminated by a warm brass desk lamp "
            "in 1991 Moscow. An open crimson velvet gift box rests on the desk holding a vintage blued-steel WWII "
            "revolver and small brass cartridges; a man's hands in white shirt cuffs and a steel wristwatch push a "
            "single gleaming brass cartridge into the open cylinder of the revolver. Right beside it on the desk lie "
            "a clean sheet of white letter paper, an uncapped black fountain pen, and a glass ashtray with stubbed-out "
            "cigarettes. Dramatic low-key chiaroscuro lighting. " + STYLE
        ),
    },
    {
        "id": "11",
        "mode": "i2i_edit",
        "ref": "luo",
        "seed": 199111,
        "prompt": (
            "Keep the exact same Chinese man in white dress shirt and loosened maroon tie from the reference image. "
            "Over-the-shoulder medium-wide shot inside a dark wood-paneled 1991 Moscow office at midnight: the man "
            "stands in the lower-left foreground in three-quarter back view looking up silently at the dark wood "
            "east wall lit by warm lamp glow. Hanging centered on the wooden wall is an antique dark-wood framed "
            "horizontal Chinese calligraphy plaque on aged xuan paper featuring four large powerful black ink brush "
            "characters '见路不走' with a small red cinnabar seal on the left margin. Somber low-key film lighting. "
            + STYLE
        ),
    },
    {
        "id": "12a",
        "mode": "t2i",
        "seed": 199112,
        "prompt": (
            "Straight-on cinematic close-up of a dark wood-paneled 1991 Moscow office wall at midnight, warmly "
            "lit from below by an off-screen desk lamp with deep atmospheric shadows around the edges. Hanging "
            "centered on the wall is an antique dark Rosewood-framed silk-mounted horizontal Chinese calligraphy "
            "scroll on warm aged xuan paper. Written across the scroll in bold, masterful, vigorous black ink brush "
            "calligraphy are the exact four large Chinese characters '见路不走', accompanied only by a tiny vertical "
            "calligrapher date inscription and one small square red cinnabar seal stamp on the far left. " + STYLE
        ),
    },
    {
        "id": "12b",
        "mode": "t2i",
        "seed": 199113,
        "prompt": (
            "Moody low-angle extreme close-up of the corner edge of a dark mahogany office desk at midnight under "
            "the warm glow of a brass desk lamp in a silent dark room. In the slightly soft background on the desk "
            "sits a black corded vintage telephone with a clean, unstained white sheet of letter paper resting neatly "
            "on top of the receiver. In the sharp foreground at the polished dark wooden edge of the desk, a thin "
            "rivulet of dark crimson blood pools at the bevel and forms a heavy red droplet dripping downward off "
            "the desk edge into darkness. Tasteful, solemn 1991 35mm cinema still. " + STYLE
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
        data = resp.read()
    dst.write_bytes(data)


def main():
    force = "--force" in sys.argv
    only_ids = [a for a in sys.argv[1:] if not a.startswith("--")]

    for item in KEYFRAMES:
        kid = item["id"]
        if only_ids and kid not in only_ids:
            continue
        out_path = STILL_DIR / f"still_{kid}.png"
        if out_path.exists() and out_path.stat().st_size > 10000 and not force:
            print(f"[skip] still_{kid}.png already exists ({out_path.stat().st_size // 1024} KB)")
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

        t0 = time.time()
        print(f"[submit] still_{kid} ({item['mode']}) ...", flush=True)
        job = post_json("/minimax_api/generate", payload)
        jid = job.get("job_id")
        if not jid or job.get("status") == "failed":
            raise RuntimeError(f"Submit failed for {kid}: {job}")

        while True:
            time.sleep(2.5)
            st = get_json(f"/minimax_api/job/{jid}")
            status = st.get("status")
            if status == "completed":
                fname = st["filename"]
                download_file(f"/minimax_api/media/{fname}", out_path)
                print(
                    f"[done]   still_{kid}.png <- {fname} ({out_path.stat().st_size // 1024} KB, {time.time() - t0:.1f}s)",
                    flush=True,
                )
                break
            elif status == "failed":
                raise RuntimeError(f"Job failed for {kid}: {st.get('message')}")

    print("ALL KEYFRAMES GENERATED SUCCESSFULLY!")


if __name__ == "__main__":
    main()
