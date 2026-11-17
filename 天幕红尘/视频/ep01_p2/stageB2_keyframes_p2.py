#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage B2 (ep01_p2): Generate spatially & character-locked Start/End keyframes for Ep01 Scenes 1-5 & 1-6
using Qwen-Image-2.1 on G4 GPU.

Continuity locks:
- Living room set: stills/set_ny_living_room.png & v02_pilot/stills/still_08.png
- Su Yuping (70yo): v02_pilot/stills/still_08.png (silver hair, glasses, beige cardigan)
- Lin Xuehong (38yo): ref/林雪红.png (dark grey-taupe collared top, shoulder-length hair)
- Luo Huijuan (35yo): ref/罗慧娟.png (plain soft-grey knit home sweater)
- US ER Doctor (45yo): ref/美国医生.png
- 17_end IS REUSED DIRECTLY as 18a_start (zero seam between chest-clutch & fall!).
"""

import base64
import json
import os
import re
import subprocess
import threading
import time
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
STILL_DIR = P2_ROOT / "stills"
STILL_DIR.mkdir(parents=True, exist_ok=True)

STYLE = (
    "1991 Kodak Vision 35mm cinema film still, anamorphic lens, natural skin texture, "
    "subtle film grain, realistic lighting, shallow depth of field, no subtitles, no watermarks."
)
NEG_NY = (
    "cartoon, anime, CGI, 3d render, oversaturated, plastic skin, modern smartphone, wireless phone, iPhone, "
    "flatscreen TV, watermark, subtitle, text, extra fingers, deformed hands, fused fingers, six fingers"
)

KEYFRAMES = [
    # --- 14: Hui answers ringing beige phone in sunny NY living room -> turns pale horrified ---
    {
        "id": "14_start",
        "mode": "i2i_edit",
        "ref": REF_DIR / "罗慧娟.png",
        "seed": 6201,
        "neg": NEG_NY + ", broad smile, cheerful grin, teeth laughing",
        "prompt": (
            "Keep the EXACT same 35-year-old Chinese woman (same face, shoulder-length dark hair, soft-grey knit home sweater). "
            "Medium shot inside a warm sunlit 1991 Manhattan apartment living room (sheer cream sunlit window curtains behind left, "
            "dark wooden bookshelves behind right, small wooden side table holding a clear half-full glass of water and small pill box). "
            "Standing beside the table, unsmiling with parted slightly anxious lips and puzzled brows, she holds a beige 1991 corded telephone handset to her ear listening intently. " + STYLE
        ),
    },
    {
        "id": "14_end",
        "mode": "i2i_edit",
        "ref_still_id": "14_start",
        "seed": 6202,
        "neg": NEG_NY,
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME camera angle, sunlit Manhattan living room background, sheer curtains, bookshelves, "
            "wooden table with clear water glass, and the exact same 35-year-old Chinese woman in soft-grey sweater holding the beige corded handset. "
            "Now her face has drained completely pale white with sudden horror and shock, eyebrows knotted, eyes wide and terrified as she hears devastating news. " + STYLE
        ),
    },

    # --- 15: Tight MCU Hui screams '哥——!' -> handset slips dangling on coiled cord ---
    {
        "id": "15_start",
        "mode": "i2i_edit",
        "ref": REF_DIR / "罗慧娟.png",
        "seed": 6211,
        "neg": NEG_NY + ", smile, smiling grin, laughing",
        "prompt": (
            "Keep the EXACT same 35-year-old Chinese woman (same face, hair, soft-grey knit sweater). Tight emotional medium close-up inside "
            "a warm sunlit 1991 Manhattan living room (soft-focused sunlit sheer curtain and wooden bookshelves behind). "
            "Un-smiling, devastated and horrified with brows knotted in terror, her face is pale white, eyes shimmering with shock, mouth open shouting urgently in panic while gripping the beige corded telephone handset against her ear. " + STYLE
        ),
    },
    {
        "id": "15_end",
        "mode": "i2i_edit",
        "ref_still_id": "15_start",
        "seed": 6212,
        "neg": NEG_NY + ", holding receiver firmly to ear, smiling, cheerful grin",
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME camera framing, warm sunlit Manhattan apartment background, and the exact same woman in soft-grey sweater. "
            "Now her pale trembling five-fingered hand has opened limp in shock by her shoulder, and the beige telephone handset has slipped free "
            "from her grasp, hanging downward in front of her chest suspended on its stretched beige coiled cord, "
            "her eyes wide and frozen pale in silent devastation. " + STYLE
        ),
    },

    # --- 16: Lin rushes out from kitchen & snatches dangling handset urgently ---
    {
        "id": "16_start",
        "mode": "i2i_edit",
        "ref": REF_DIR / "林雪红.png",
        "seed": 6221,
        "neg": NEG_NY,
        "prompt": (
            "Keep the EXACT same 38-year-old Chinese woman (same face, shoulder-length dark hair, dark grey-taupe collared top, "
            "wearing a simple dark-cream cotton kitchen apron over her front). Medium shot in a warm sunlit 1991 Manhattan living room with "
            "a round dark wood coffee table in the foreground (a beige telephone base and a clear glass of water resting on the table). "
            "Rushing urgently out from the side hallway toward the table, she leans forward reaching her hand rapidly down toward a beige handset dangling off the edge. " + STYLE
        ),
    },
    {
        "id": "16_end",
        "mode": "i2i_edit",
        "ref_still_id": "16_start",
        "seed": 6222,
        "neg": NEG_NY,
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME camera angle, sunlit Manhattan living room, wooden coffee table with beige telephone base and clear water glass, "
            "and the exact same 38-year-old woman in dark grey-taupe top and simple apron. "
            "Now she stands braced upright right by the table, gripping the beige corded handset firmly to her ear with sharp fierce urgency, leaning in demanding loudly into the phone. " + STYLE
        ),
    },

    # --- 17: Su Yuping just stepped out by side table hears leaked words -> clutches chest sweater ---
    {
        "id": "17_start",
        "mode": "i2i_edit",
        "ref": VID_ROOT / "v02_pilot" / "stills" / "still_08.png",
        "seed": 6231,
        "neg": NEG_NY + ", holding telephone, sitting smiling",
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME 70-year-old silver-haired Chinese woman (exact same face, thin glasses, beige knit cardigan over cream collared blouse) "
            "and the EXACT SAME sunlit 1991 Manhattan apartment living room, sheer window curtains left, wooden bookshelves right, and small wooden coffee table "
            "with the half-full clear glass water tumbler, pill box, and empty beige phone base (remove handset from her hand). "
            "Now she has just stepped upright out of the doorway standing beside the wooden table, frozen mid-step facing slightly left, sudden startled shock on her face. " + STYLE
        ),
    },
    {
        "id": "17_end",
        "mode": "i2i_edit",
        "ref_still_id": "17_start",
        "seed": 6232,
        "neg": NEG_NY + ", smiling, relaxed",
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME camera framing, sunlit Manhattan living room, sheer curtains, wooden bookshelves, "
            "round wooden coffee table with the clear glass of water, and the exact same 70-year-old silver-haired woman. "
            "Struck by a sudden fatal heart attack, her face is twisted pale in silent agony with eyes squeezed tight, and BOTH trembling five-fingered hands "
            "clutch tightly onto the fabric of her beige knit cardigan right over the center of her chest as her knees stiffen. " + STYLE
        ),
    },

    # --- 18a: Start IS 17_end! End = Su falls rigid backward onto floor knocking glass tumbler off table ---
    {
        "id": "18a_end_a",
        "mode": "i2i_edit",
        "ref_still_id": "17_end",
        "seed": 6241,
        "neg": NEG_NY + ", standing upright, glass still upright untouched on table",
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME camera angle, sunlit Manhattan living room, sheer curtains left, wooden bookshelves right, and small wooden coffee table. "
            "Now the 70-year-old silver-haired woman in the beige cardigan has collapsed rigid backward flat down onto the floor beside the sofa behind the table, "
            "lying unconscious on the rug with her hand still near her chest; her fall has swept across the table edge knocking the clear glass water tumbler "
            "sideways off the table — broken glass and spilled water splash onto the dark wood floor in the lower foreground. " + STYLE
        ),
    },
    {
        "id": "18a_end_b",
        "mode": "i2i_edit",
        "ref_still_id": "17_end",
        "seed": 6242,
        "neg": NEG_NY + ", standing upright, glass still upright untouched on table",
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME camera framing, sunlit Manhattan living room, curtains, bookshelves, and wooden coffee table. "
            "Now the elderly silver-haired woman has collapsed stiffly backward onto the floor/carpet in her beige cardigan, head resting low near the sofa edge, "
            "while the clear glass water tumbler has tumbled off the corner of the wooden coffee table onto the floor, overturned with spilled water glistening beside shattered glass shards. " + STYLE
        ),
    },

    # --- 18b: Lin drops to knees cradling unconscious Su screaming for ambulance/medicine ---
    {
        "id": "18b_start",
        "mode": "i2i_edit",
        "ref": REF_DIR / "林雪红.png",
        "seed": 6251,
        "neg": NEG_NY + ", smiling, calm, hospital",
        "prompt": (
            "Keep the EXACT same 38-year-old Chinese woman (exact face, dark shoulder-length hair, dark grey-taupe collared top, simple kitchen apron). "
            "Low-angle medium close-up kneeling urgently on a sunlit 1991 Manhattan apartment floor beside a spilled water puddle and overturned glass cup by a wooden coffee table leg. "
            "In her arms she tightly cradles an unconscious 70-year-old silver-haired grandmother wearing a beige knit cardigan (elderly woman's head turned resting limp in her crook). "
            "The 38-year-old woman looks up desperately toward off-screen left with tear-streaked terrified eyes, mouth open screaming urgently for help and medicine. " + STYLE
        ),
    },

    # --- 19: Night Hospital ER Corridor overhead sign lamp clicks OFF ---
    {
        "id": "19_start",
        "mode": "t2i",
        "seed": 6261,
        "neg": NEG_NY + ", people, doctor, sunny window, warm living room",
        "prompt": (
            "Empty 1991 New York hospital emergency operating room corridor at night, low-angle shot looking toward double swinging metal-trimmed frosted glass ER doors. "
            "Above the doors, a rectangular backlit red-amber surgical status lightbox sign is illuminated glowing warm red reading IN SURGERY. "
            "Overhead cool pale green-white fluorescent corridor tubes dimly reflect on quiet linoleum floor tiles. " + STYLE
        ),
    },
    {
        "id": "19_end",
        "mode": "i2i_edit",
        "ref_still_id": "19_start",
        "seed": 6262,
        "neg": NEG_NY + ", lit red sign, glowing red box",
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME camera position, frosted double emergency room doors, and cool fluorescent 1991 hospital hallway. "
            "The rectangular illuminated red status lightbox sign above the doors has now switched completely OFF and gone dark/unlit, "
            "leaving only cold sterile greenish-white fluorescent corridor reflection on the frosted glass doors and empty hallway. " + STYLE
        ),
    },

    # --- 20: Solemn American ER doctor exits wearing mask -> pulls mask down under chin ---
    {
        "id": "20_start",
        "mode": "i2i_edit",
        "ref": REF_DIR / "美国医生.png",
        "seed": 6271,
        "neg": NEG_NY + ", smiling, cheerful, mask already down under chin, uncovered mouth",
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME 45-year-old solemn American male surgeon (exact same face, hair, white doctor's lab coat over pale blue scrubs, stethoscope, "
            "frosted hospital ER doors behind under cool fluorescent corridor lighting). "
            "Medium close-up right as he exits the doors: the pale blue medical face mask is STILL worn OVER his nose and mouth, and his right five-fingered hand reaches up pinching the bottom edge of the blue mask beginning to pull it down, heavy sorrow in his tired eyes. " + STYLE
        ),
    },
    {
        "id": "20_end",
        "mode": "i2i_edit",
        "ref_still_id": "20_start",
        "seed": 6272,
        "neg": NEG_NY + ", smiling, mask still over mouth",
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME camera framing, frosted ER corridor doors, fluorescent lighting, and the exact same 45-year-old American doctor. "
            "Now he has pulled the pale blue surgical mask all the way down hanging beneath his chin, lowered his hand out of frame, and gazes gravely ahead "
            "with a heavy somber expression ready to shake his head silently. " + STYLE
        ),
    },

    # --- 21a: Hui slides helplessly down white hospital corridor wall weeping ---
    {
        "id": "21a_start",
        "mode": "i2i_edit",
        "ref": REF_DIR / "罗慧娟.png",
        "seed": 6281,
        "neg": NEG_NY + ", smiling, cheerful grin, sunny curtains, wood bookshelf",
        "prompt": (
            "Keep the EXACT same 35-year-old Chinese woman (same face, shoulder-length black hair, soft-grey casual home knit sweater). "
            "Cold sterile pale white-green 1991 hospital corridor at night under harsh fluorescent lighting. Medium shot with her back pressed against "
            "the cold flat painted corridor wall, devastating grief, brows crumpled weeping, knees starting to give way as shock overwhelms her. " + STYLE
        ),
    },
    {
        "id": "21a_end",
        "mode": "i2i_edit",
        "ref_still_id": "21a_start",
        "seed": 6282,
        "neg": NEG_NY + ", standing tall, smiling",
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME camera angle, cold white hospital corridor wall, linoleum floor strip at bottom, cool fluorescent lighting, "
            "and the exact same woman in soft-grey knit sweater. Now she has slid helplessly all the way down the wall into a slumped seated heap on the cold hospital floor, "
            "tears streaming, clutching her knees and sobbing inconsolably. " + STYLE
        ),
    },

    # --- 21b: Tighter floor shot of Hui beating fist softly & crying helplessly ---
    {
        "id": "21b_start",
        "mode": "i2i_edit",
        "ref": REF_DIR / "罗慧娟.png",
        "seed": 6291,
        "neg": NEG_NY + ", standing, smiling, apartment",
        "prompt": (
            "Keep the EXACT same 35-year-old Chinese woman (same face, hair, soft-grey knit sweater). Tight low-angle close-up slumped against the base "
            "of a cold white-painted 1991 hospital hallway wall on linoleum floor under cool fluorescent night light. Face wet with tears, "
            "mouth crying brokenly as she strikes one trembling fist weakly against the hospital floor beside her knee in despair. " + STYLE
        ),
    },

    # --- 22: Lin leans against cold white hospital wall biting lower lip forcing tears back ---
    {
        "id": "22_start",
        "mode": "i2i_edit",
        "ref": REF_DIR / "林雪红.png",
        "seed": 6301,
        "neg": NEG_NY + ", apron, smiling, apartment",
        "prompt": (
            "Keep the EXACT same 38-year-old Chinese woman (exact face, shoulder-length black hair, dark grey-taupe collared top, NO kitchen apron). "
            "Tight emotional medium close-up leaning her back flat against a cold sterile white painted 1991 hospital corridor wall at night under pale fluorescent lighting. "
            "Her face is pale, eyes red-rimmed glistening with unshed tears, teeth visibly biting firmly down onto her lower lip as her chest heaves trying not to cry. " + STYLE
        ),
    },
    {
        "id": "22_end",
        "mode": "i2i_edit",
        "ref_still_id": "22_start",
        "seed": 6302,
        "neg": NEG_NY + ", apron, crying loudly with open mouth, heavy tears pouring",
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME camera angle, cold white hospital corridor wall, fluorescent lighting, dark grey-taupe collared top, and the exact same 38-year-old woman. "
            "Now she has released her bitten lower lip and forced every tear completely back inside — jawline locked hard like iron, eyes dry, razor-sharp, and deadly calm, "
            "taking a braced upright posture ready to take command. " + STYLE
        ),
    },

    # --- 23: Lin bends & yanks sobbing Hui up against white hospital wall ---
    {
        "id": "23_start",
        "mode": "i2i_edit",
        "ref": REF_DIR / "林雪红.png",
        "seed": 6311,
        "neg": NEG_NY + ", apron, smiling, extra arm, three hands",
        "prompt": (
            "Keep the EXACT same 38-year-old Chinese woman (same face, hair, dark grey-taupe collared top, NO apron). Medium shot against cold white 1991 hospital corridor wall at night. "
            "Leaning forward firmly in foreground right facing left, she reaches both hands down gripping the soft-grey knit sweater shoulders of another crouching 35-year-old dark-haired Chinese woman (seen from 3/4 rear/side shoulder angle kneeling low on left against wall), yanking her upward off the floor. " + STYLE
        ),
    },
    {
        "id": "23_end",
        "mode": "i2i_edit",
        "ref_still_id": "23_start",
        "seed": 6312,
        "neg": NEG_NY + ", apron, smiling, extra arm, three hands",
        "prompt": (
            "STRICTLY KEEP THE EXACT SAME camera framing, cold white hospital corridor wall, lighting, and exact clothes of both women. "
            "Now the 38-year-old woman has pulled the younger grey-sweatered woman all the way upright facing her, holding her shoulders tightly at close eye-level against the white wall, "
            "looking fiercely into her eyes with cold hoarse iron authority. " + STYLE
        ),
    },

    # --- 24a / 24c: Tight steely MCU Lin giving iron command ---
    {
        "id": "24_lin_mcu",
        "mode": "i2i_edit",
        "ref": REF_DIR / "林雪红.png",
        "seed": 6321,
        "neg": NEG_NY + ", apron, smiling",
        "prompt": (
            "Keep the EXACT same 38-year-old Chinese woman (same face, dark shoulder-length hair, dark grey-taupe collared top, NO apron). "
            "Tight dramatic medium close-up in cold sterile fluorescent light of a 1991 hospital hallway at night, back-of-head blurred edge of a dark-haired listener in soft foreground left corner. "
            "Her face is intense, pale, dry-eyed, speaking rapidly and decisively with unyielding iron resolve. " + STYLE
        ),
    },

    # --- 24b: Reverse OTS onto Hui listening stunned & tear-streaked ---
    {
        "id": "24b_hui_ots",
        "mode": "i2i_edit",
        "ref": REF_DIR / "罗慧娟.png",
        "seed": 6331,
        "neg": NEG_NY + ", smiling, cheerful grin, teeth laughing, two frontal faces",
        "prompt": (
            "Keep the EXACT same 35-year-old Chinese woman (same face, shoulder-length black hair, soft-grey knit sweater). "
            "Tight over-the-shoulder reverse medium close-up in a cold 1991 hospital hallway at night — the dark out-of-focus shoulder and dark hair edge of another woman frame the right foreground, "
            "while the 35-year-old woman stands against the cold white wall facing her, completely unsmiling, eyes tear-rimmed, pale shocked and listening intently in stunned obedience. " + STYLE
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
    todo = [j for j in KEYFRAMES if not (STILL_DIR / f"still_{j['id']}.png").exists()]
    if not todo:
        print("[skip] All Stage B2 stills already exist.")
        return

    stop_ka = threading.Event()
    b64_cache: dict[Path, str] = {}
    try:
        print(f"[1/4] Waking EasyColab G4 GPU for Qwen-Image-2.1 Stage B2 ({len(todo)} stills)...", flush=True)
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

        print(f"[3/4] Generating {len(todo)} storyboard keyframes...", flush=True)
        for j in KEYFRAMES:
            out_p = STILL_DIR / f"still_{j['id']}.png"
            if out_p.exists() and out_p.stat().st_size > 20_000:
                print(f"  [skip] {out_p.name}", flush=True)
                continue
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
                rp = j["ref"] if "ref" in j else (STILL_DIR / f"still_{j['ref_still_id']}.png")
                if not rp.exists():
                    raise FileNotFoundError(f"Missing reference still: {rp}")
                if rp not in b64_cache:
                    b64_cache[rp] = base64.b64encode(rp.read_bytes()).decode("ascii")
                payload["first_frame_base64"] = b64_cache[rp]
            t0 = time.time()
            job = http_json(f"{base_url}/minimax_api/generate", payload)
            jid = job["job_id"]
            while True:
                time.sleep(2.0)
                jst = http_json(f"{base_url}/minimax_api/job/{jid}")
                if jst.get("status") == "completed":
                    fn = jst.get("filename") or Path(jst["filepath"]).name
                    download_bytes(f"{base_url}/minimax_api/media/{fn}", out_p)
                    print(f"  [saved] {out_p.name} ({out_p.stat().st_size // 1024} KB, {time.time() - t0:.1f}s)", flush=True)
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
