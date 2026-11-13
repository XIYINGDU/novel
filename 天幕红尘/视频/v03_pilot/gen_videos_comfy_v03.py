#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate v0.3 dynamic 1280x720 HD cinema clips via EasyColab ComfyUI (Wan2.2 14B 4-step LightX2V)."""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

BASE_GRADIO = os.environ.get("EASYCOLAB_URL", "").rstrip("/")
CF_URL = os.environ.get("COMFY_URL", "").rstrip("/")

ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v03_pilot")
STILL_DIR = ROOT / "stills"
CLIP_DIR = ROOT / "clips"
CLIP_DIR.mkdir(parents=True, exist_ok=True)

NEG_PROMPT = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，文字水印，风格，画作，静止不动，整体发灰，最差质量，低质量，"
    "JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，"
    "手指融合，杂乱的背景，三条腿，倒着走，cartoon, anime, CGI, face reveal on back shot, grimacing, squinting"
)

CLIPS = [
    (
        "01_v3",
        "still_01_v3.png",
        81,
        199301,
        "Realistic 35mm night film shot from behind, the man's head and face never visible. Wearing a plain white crewneck sweatshirt and sneakers, he walks relaxed down the four wide stone steps from the warm-lit French restaurant doorway toward the dark Paris boulevard and the dense multi-window building across the street; suddenly his back and shoulders jolt sharply forward and freeze mid-step as a silent bullet strikes his chest.",
    ),
    (
        "02a_v3",
        "still_02a_v3.png",
        65,
        199302,
        "Extreme 35mm night close-up framed strictly on the chest and torso below the collarbone, head completely outside frame. Dark crimson blood spreads wider across the white crewneck cotton sweatshirt as a second silent bullet hits; his right hand reaches in, presses gently against his bloodstained chest, and lifts slightly with red-stained fingertips.",
    ),
    (
        "02b_v3",
        "still_02b_v3.png",
        65,
        199303,
        "Low-angle ground-level 35mm night shot from behind on wet stone restaurant steps, head never in frame. The man's knees give way completely and his white-sweatshirt torso collapses heavily downward onto the wet stone steps.",
    ),
    (
        "04_v3",
        "still_04_v3.png",
        81,
        199304,
        "Slow brooding 35mm cinema push-in looking up at the dark 15-story Soviet office tower on a wet deserted 1991 Moscow midnight street; rain shimmer glistens on the empty asphalt while the single warm amber-lit window high on the 12th floor east corner glows steadily in the night.",
    ),
    (
        "05_ins1",
        "still_05_ins1.png",
        81,
        199305,
        "Slow atmospheric 35mm macro dolly-in on the dark mahogany desk at midnight: thin grey smoke curls lazily upward from the cut-glass ashtray packed half-full of crushed cigarette butts while the blurred blue Soviet CRT television flickers faintly in the dark background.",
    ),
    (
        "05_ins2",
        "still_05_ins2.png",
        89,
        199306,
        "Subtle intimate 35mm slow push-in under warm brass desk-lamp light toward the wooden tabletop photo frame on the dark desk corner showing the four smiling Chinese women in front of the New York restaurant.",
    ),
    (
        "05c_v3",
        "still_05c_v3.png",
        89,
        199307,
        "Tight low-key 35mm close-up on the dark office desk at midnight: the man's calm right index finger reaches down smoothly and presses firmly onto the black telephone cradle hook-switch button to cut off the call, holding it pressed down.",
    ),
    (
        "06b_v3",
        "still_06b_v3.png",
        65,
        199308,
        "Close-up in a dark 1991 Moscow office at midnight: the man's hand in a white shirt cuff presses the mechanical power button on the front of the small boxy Soviet CRT television, clicking it firmly inward.",
    ),
    (
        "07_v3",
        "still_07_v3.png",
        97,
        199309,
        "Intimate 35mm slow push-in inside the silent midnight Moscow office under warm brass lamp light. Seated behind his mahogany desk, the 42-year-old Chinese man gazes sorrowfully at the family photo frame while his right index finger presses buttons on the black desk telephone keypad and he holds the black receiver up to his ear.",
    ),
    (
        "08a_v3",
        "still_08a_v3.png",
        65,
        199310,
        "Warm sunlit 1991 Manhattan afternoon close-up on the wooden side table beside sheer curtains: the elderly Chinese woman's gentle hand in a beige knit cardigan sleeve reaches onto the ringing beige corded telephone and lifts the receiver smoothly upward off the cradle.",
    ),
    (
        "09a_v3",
        "still_09a_v3.png",
        97,
        199311,
        "Restrained 35mm cinema close-up in the dark Moscow office. The 42-year-old Chinese man holds the black telephone receiver tightly against his right ear with pale knuckles; unshed tears glisten quietly in his reddened eyes, his throat swallows once, and his closed lips tremble almost imperceptibly without speaking a word.",
    ),
    (
        "09b_v3",
        "still_09b_v3.png",
        65,
        199312,
        "Extreme 35mm close-up on the dark wooden desk under warm amber lamp light: the man's pale hand slowly, gently lowers the black corded telephone receiver all the way down until it rests softly on the telephone cradle.",
    ),
    (
        "10a_v3",
        "still_10a_v3.png",
        81,
        199313,
        "High-angle 35mm macro close-up on the dark mahogany desk: the man's fingers push the gleaming brass cartridge smoothly inside the open chamber of the vintage blued-steel revolver cylinder in the red velvet box and push the cylinder inward to close it.",
    ),
    (
        "10b_v3",
        "still_10b_v3.png",
        97,
        199314,
        "High-angle 35mm macro close-up on the dark wooden desk under warm brass lamp light: the man's right hand in a white shirt cuff writes slowly across the white paper with the uncapped black gold-nib fountain pen, then pauses and rests the pen quietly beside the note.",
    ),
    (
        "11a_v3",
        "still_11a_v3.png",
        97,
        199315,
        "Solemn 35mm slow dolly push-in inside the dark wood-paneled Moscow office at midnight: the 42-year-old Chinese man in white shirt and loosened maroon tie stands quietly in the lower-left foreground gazing steadily upward at the framed calligraphy scroll '見路不走' on the dark wooden wall.",
    ),
    (
        "11b_v3",
        "still_11b_v3.png",
        97,
        199316,
        "Tight chiaroscuro 35mm slow push-in close-up of the 42-year-old Chinese man in the dark midnight office staring upward with hollow, desolate, motionless eyes under faint warm lamp rim-light, breathing slowly one last time.",
    ),
    (
        "12b_v3",
        "still_12b_v3.png",
        81,
        199317,
        "Locked-off 35mm macro close-up of the dark mahogany desk corner edge rim-lit by warm brass lamp light: in the sharp foreground, glossy vivid crimson blood swells over the wooden bevel and drips drop by drop downward into the black shadow below while the clean white paper rests untouched on the black telephone behind.",
    ),
]


def http_req(url: str, data: bytes = None, headers: dict = None, method: str = "GET", timeout: int = 60, retries: int = 5):
    hdrs = {"User-Agent": "Mozilla/5.0"}
    if headers:
        hdrs.update(headers)
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:
            last_err = e
            if attempt + 1 < retries:
                time.sleep(2.5 * (attempt + 1))
    raise last_err


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
    return json.loads(raw)["name"]


def build_wan22_prompt(img_name: str, pos_prompt: str, num_frames: int, seed: int, prefix: str) -> dict:
    return {
        "84": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan", "device": "default"},
        },
        "90": {"class_type": "VAELoader", "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},
        "95": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors", "weight_dtype": "default"},
        },
        "96": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors", "weight_dtype": "default"},
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
        "104": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["101", 0], "shift": 5.0}},
        "103": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["102", 0], "shift": 5.0}},
        "93": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["84", 0], "text": pos_prompt}},
        "89": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["84", 0], "text": NEG_PROMPT}},
        "97": {"class_type": "LoadImage", "inputs": {"image": img_name}},
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
        "87": {"class_type": "VAEDecode", "inputs": {"samples": ["85", 0], "vae": ["90", 0]}},
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
    if not CF_URL:
        raise RuntimeError("COMFY_URL env var is required")
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
        if BASE_GRADIO:
            try:
                http_req(f"{BASE_GRADIO}/minimax_api/comfyui/status", timeout=15)
            except Exception:
                pass

        up_name = upload_image(STILL_DIR / still_name)
        prefix = f"v03_clip_{cid}"
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
            hist = json.loads(http_req(f"{CF_URL}/history/{pid}", timeout=30))
            if pid not in hist:
                continue
            entry = hist[pid]
            status_str = entry.get("status", {}).get("status_str")
            if status_str == "error":
                raise RuntimeError(f"ComfyUI execution error on {cid}: {entry.get('status')}")
            outputs = entry.get("outputs", {})
            if "108" in outputs:
                gifs = outputs["108"].get("gifs") or outputs["108"].get("videos") or []
                mp4_info = next((g for g in gifs if str(g.get("filename", "")).endswith(".mp4")), None) or (gifs[0] if gifs else None)
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

    print("ALL 17 V0.3 DYNAMIC CLIPS GENERATED SUCCESSFULLY!", flush=True)


if __name__ == "__main__":
    main()
