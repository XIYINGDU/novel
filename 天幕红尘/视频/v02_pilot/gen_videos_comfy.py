#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate 13 dynamic 1280x720 HD cinema clips via EasyColab ComfyUI (Wan2.2 14B 4-step LightX2V)."""

import json
import mimetypes
import os
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

BASE_GRADIO = os.environ.get("EASYCOLAB_URL", "https://b7c1afb6b9587feb07.gradio.live").rstrip("/")
CF_URL = os.environ.get("COMFY_URL", "https://frames-far-recording-stay.trycloudflare.com").rstrip("/")

ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v02_pilot")
STILL_DIR = ROOT / "stills"
CLIP_DIR = ROOT / "clips"
CLIP_DIR.mkdir(parents=True, exist_ok=True)

NEG_PROMPT = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，文字水印，风格，画作，静止不动，整体发灰，最差质量，低质量，"
    "JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，"
    "手指融合，杂乱的背景，三条腿，倒着走，cartoon, anime, CGI, face reveal on back shot"
)

CLIPS = [
    (
        "01",
        "still_01.png",
        81,
        199101,
        "Realistic 35mm night film shot from behind at waist height, the man's face never visible. The man in the plain white crewneck sweatshirt and sneakers walks relaxed down the stone steps onto the wet Paris pavement; suddenly his torso jolts sharply forward and his footsteps freeze mid-stride as a silent bullet hits his chest from above.",
    ),
    (
        "02",
        "still_02.png",
        81,
        199102,
        "Tight 35mm night close-up framed strictly below the neck, face completely out of frame above top edge. Dark crimson blood spreads wider across the white crewneck sweatshirt chest; his bloodstained right hand trembles and presses his chest as he exhales, then his knees give way and his white-clad torso collapses downward out of frame.",
    ),
    (
        "04",
        "still_04.png",
        81,
        199104,
        "Slow, brooding 35mm cinema dolly push-in down the deserted rain-slicked 1991 Moscow boulevard at midnight. Distant red taillights of the lone Soviet sedan glide away into the mist, wet asphalt shimmers faintly, and the single warm amber window high on the 12th floor of the dark office tower glows steadily.",
    ),
    (
        "05a",
        "still_05.png",
        97,
        199105,
        "Realistic 35mm low-key interior shot. The 42-year-old Chinese man stands leaning at his dark wooden desk holding the black corded telephone receiver to his right ear; he speaks two brief calm syllables, then listens with an exhausted, motionless expression while the small blue CRT television flickers faintly in the dark background corner and thin smoke curls from the ashtray.",
    ),
    (
        "05b",
        "still_05b.png",
        97,
        199155,
        "Subtle slow 35mm push-in close-up under the warm brass desk lamp. The 42-year-old Chinese man listens with terrifyingly calm, hollow eyes fixed on the framed family photo on his desk, speaks a brief quiet sentence, and calmly presses his right index finger down onto the black telephone hook switch to cut off the call.",
    ),
    (
        "06",
        "still_06.png",
        89,
        199106,
        "Moody 35mm cinema medium shot beside the open 12th-floor Moscow window at midnight. The 42-year-old Chinese man slowly exhales thin grey cigarette smoke into the night air, flicks ash lightly from his cigarette out the open window, casts a cold sideways glance toward the flickering blue CRT television in the room, and turns slightly inward.",
    ),
    (
        "07",
        "still_07.png",
        81,
        199107,
        "Intimate 35mm slow push-in in the dark midnight office lit by a warm brass lamp. Seated behind his mahogany desk, the 42-year-old Chinese man gazes tenderly and sorrowfully at the framed family photograph while his right index finger presses buttons on the black desk telephone keypad to dial a long-distance number, lifting the receiver toward his ear.",
    ),
    (
        "08",
        "still_08.png",
        81,
        199108,
        "Warm sunlit 1991 New York apartment 35mm medium shot. The gentle 70-year-old silver-haired Chinese grandmother holds the beige corded telephone receiver to her ear, smiling warmly and speaking softly with maternal affection as sheer window curtains sway almost imperceptibly in golden afternoon sunlight.",
    ),
    (
        "09",
        "still_09.png",
        97,
        199109,
        "Raw, restrained 35mm cinema close-up in the dark Moscow office. The 42-year-old Chinese man grips the black telephone receiver tightly against his ear; tears glisten in his reddened eyes without falling, his throat swallows hard, and his slightly parted lips tremble silently without uttering a single word before he slowly closes his eyes and gently lowers the receiver.",
    ),
    (
        "10",
        "still_10.png",
        97,
        199110,
        "High-angle 35mm close-up on the dark wooden desk under warm brass lamp light. The man's right hand in a white shirt cuff and steel wristwatch inserts the gleaming brass bullet cleanly into the open cylinder of the blued-steel WWII revolver inside the red velvet box, then slowly reaches toward the black fountain pen on the white letter paper.",
    ),
    (
        "11",
        "still_11.png",
        89,
        199111,
        "Solemn 35mm slow push-in inside the dark wood-paneled Moscow office at midnight. The 42-year-old Chinese man in white shirt and loosened maroon tie stands quietly in the foreground looking up at the framed horizontal Chinese brush calligraphy plaque '見路不走' on the wooden wall, his lips barely moving in an almost silent whisper.",
    ),
    (
        "12a",
        "still_12a.png",
        65,
        199112,
        "Slow, steady, ominous 35mm cinema dolly push-in straight toward the antique framed Chinese brush calligraphy scroll '見路不走' hanging on the dark wood-paneled wall at midnight; the warm lamp glow from the lower right flickers subtly in the quiet room, keeping the four brush characters razor-sharp.",
    ),
    (
        "12b",
        "still_12b.png",
        81,
        199113,
        "Locked-off 35mm macro close-up of the dark mahogany desk corner at midnight under warm brass lamp light. In the soft background the clean white suicide note rests untouched atop the black telephone, while at the sharp wooden foreground bevel, dark crimson blood slowly swells and drips drop by drop downward off the desk edge into darkness.",
    ),
]


def http_req(url: str, data: bytes = None, headers: dict = None, method: str = "GET", timeout: int = 60):
    hdrs = {"User-Agent": "Mozilla/5.0"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def upload_image(img_path: Path) -> str:
    boundary = "----EasyColabBoundary" + uuid.uuid4().hex
    img_bytes = img_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{img_path.name}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode("utf-8") + img_bytes + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    raw = http_req(
        f"{CF_URL}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    res = json.loads(raw)
    return res["name"]


def build_wan22_prompt(img_name: str, pos_prompt: str, num_frames: int, seed: int, prefix: str) -> dict:
    return {
        "84": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                "type": "wan",
                "device": "default",
            },
        },
        "90": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "wan_2.1_vae.safetensors"},
        },
        "95": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
                "weight_dtype": "default",
            },
        },
        "96": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
                "weight_dtype": "default",
            },
        },
        "101": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["95", 0],
                "lora_name": "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
                "strength_model": 1.0,
            },
        },
        "102": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["96", 0],
                "lora_name": "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
                "strength_model": 1.0,
            },
        },
        "104": {
            "class_type": "ModelSamplingSD3",
            "inputs": {"model": ["101", 0], "shift": 5.0},
        },
        "103": {
            "class_type": "ModelSamplingSD3",
            "inputs": {"model": ["102", 0], "shift": 5.0},
        },
        "93": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["84", 0], "text": pos_prompt},
        },
        "89": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["84", 0], "text": NEG_PROMPT},
        },
        "97": {
            "class_type": "LoadImage",
            "inputs": {"image": img_name},
        },
        "98": {
            "class_type": "WanImageToVideo",
            "inputs": {
                "positive": ["93", 0],
                "negative": ["89", 0],
                "vae": ["90", 0],
                "start_image": ["97", 0],
                "width": 1280,
                "height": 720,
                "length": int(num_frames),
                "batch_size": 1,
            },
        },
        "86": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "add_noise": "enable",
                "noise_seed": int(seed),
                "steps": 4,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "start_at_step": 0,
                "end_at_step": 2,
                "return_with_leftover_noise": "enable",
                "model": ["104", 0],
                "positive": ["98", 0],
                "negative": ["98", 1],
                "latent_image": ["98", 2],
            },
        },
        "85": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "add_noise": "disable",
                "noise_seed": 0,
                "steps": 4,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "start_at_step": 2,
                "end_at_step": 4,
                "return_with_leftover_noise": "disable",
                "model": ["103", 0],
                "positive": ["98", 0],
                "negative": ["98", 1],
                "latent_image": ["86", 0],
            },
        },
        "87": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["85", 0], "vae": ["90", 0]},
        },
        "108": {
            "class_type": "VHS_VideoCombine",
            "inputs": {
                "images": ["87", 0],
                "frame_rate": 16,
                "loop_count": 0,
                "filename_prefix": prefix,
                "format": "video/h264-mp4",
                "pix_fmt": "yuv420p",
                "crf": 18,
                "save_metadata": False,
                "trim_to_audio": False,
                "pingpong": False,
                "save_output": True,
            },
        },
    }


def main():
    force = "--force" in sys.argv
    only_ids = [a for a in sys.argv[1:] if not a.startswith("--")]
    client_id = uuid.uuid4().hex

    for idx, (cid, still_name, nframes, seed, prompt) in enumerate(CLIPS, 1):
        if only_ids and cid not in only_ids:
            continue
        out_mp4 = CLIP_DIR / f"clip_{cid}.mp4"
        if out_mp4.exists() and out_mp4.stat().st_size > 20000 and not force:
            print(f"[skip] clip_{cid}.mp4 exists ({out_mp4.stat().st_size // 1024} KB)", flush=True)
            continue

        t0 = time.time()
        # Keep EasyColab idle watchdog touched
        try:
            http_req(f"{BASE_GRADIO}/minimax_api/comfyui/status", timeout=15)
        except Exception:
            pass

        up_name = upload_image(STILL_DIR / still_name)
        prefix = f"v02_clip_{cid}"
        graph = build_wan22_prompt(up_name, prompt, nframes, seed, prefix)
        sub_raw = http_req(
            f"{CF_URL}/prompt",
            data=json.dumps({"prompt": graph, "client_id": client_id}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        sub = json.loads(sub_raw)
        if "prompt_id" not in sub:
            raise RuntimeError(f"Prompt submit error for {cid}: {sub}")
        pid = sub["prompt_id"]
        print(f"[{idx}/{len(CLIPS)}] submitted clip_{cid} ({nframes}f) pid={pid[:8]}...", flush=True)

        while True:
            time.sleep(3.0)
            hist_raw = http_req(f"{CF_URL}/history/{pid}", timeout=30)
            hist = json.loads(hist_raw)
            if pid not in hist:
                continue
            entry = hist[pid]
            status_str = entry.get("status", {}).get("status_str")
            if status_str == "error":
                raise RuntimeError(f"ComfyUI execution error on {cid}: {entry.get('status')}")
            outputs = entry.get("outputs", {})
            if "108" in outputs:
                gifs = outputs["108"].get("gifs") or outputs["108"].get("videos") or []
                mp4_info = next((g for g in gifs if str(g.get("filename", "")).endswith(".mp4")), None)
                if not mp4_info and gifs:
                    mp4_info = gifs[0]
                if not mp4_info:
                    raise RuntimeError(f"No output file in history for {cid}: {outputs}")
                qs = urllib.parse.urlencode(
                    {
                        "filename": mp4_info["filename"],
                        "subfolder": mp4_info.get("subfolder", ""),
                        "type": mp4_info.get("type", "output"),
                    }
                )
                vid_bytes = http_req(f"{CF_URL}/view?{qs}", timeout=120)
                out_mp4.write_bytes(vid_bytes)
                print(
                    f"[done] clip_{cid}.mp4 ({len(vid_bytes) // 1024} KB, {time.time() - t0:.1f}s)",
                    flush=True,
                )
                break

    print("ALL 13 DYNAMIC CLIPS GENERATED SUCCESSFULLY!", flush=True)


if __name__ == "__main__":
    main()
