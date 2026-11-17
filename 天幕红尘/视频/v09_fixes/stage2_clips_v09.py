#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage 2 (v0.9): Generate Wan2.2 14B 4-step LightX2V clips on EasyColab G4:
- 01: Back-view quiet walk -> sudden tight shoulder flinch & dead mid-step arrest (I2V, zero arm-flinging, zero cars/headlights)
- 02a: Pixel-locked Start->End FLF2V (clean white crewneck -> subtle tremor + organic crimson cotton bleed + gentle 5-finger touch)
- 02b: Pixel-locked Start->End FLF2V (upright wounded building glance -> fast deadweight drop flat onto wet stone steps)
Then immediately stop_all and verify burn_rate_hourly == 0.0.
"""

import json
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

BRIDGE_PY = "/Users/duxiying/.local/share/uv/tools/google-colab-cli/bin/python"
BRIDGE = "/Applications/EasyColab.app/Contents/Resources/colab_bridge.py"

VID_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频")
V08_STILL = VID_ROOT / "v08_fixes" / "stills"
V09 = VID_ROOT / "v09_fixes"
STILL_DIR = V09 / "stills"
CLIP_DIR = V09 / "clips"
CLIP_DIR.mkdir(parents=True, exist_ok=True)

NEG_01 = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，文字水印，整体发灰，最差质量，低质量，JPEG压缩残留，"
    "turning around, face visible, head turn showing profile, spreading both arms wide, T-pose, jumping jack, "
    "arms raised outward, car headlights, passing car, vehicle lights, glowing spark, muzzle flash, lens flare, "
    "blue sky, daylight, long hair, extra limbs, deformed legs"
)
NEG_02A = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，文字水印，整体发灰，最差质量，低质量，JPEG压缩残留，"
    "bullet, projectile, metal casing, sparks, smoke explosion, pinched fabric funnel, origami cloth crease, "
    "six fingers, extra fingers, deformed hand, fused fingers, silver bracelet, watch, cufflinks, chin, mouth, face"
)
NEG_02B = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，文字水印，整体发灰，最差质量，低质量，JPEG压缩残留，"
    "slow sitting down, praying pose, sitting cleanly on heels, long hair, woman hair, turning face to camera, "
    "face visible, blue sky, daylight, hovering, levitating, extra legs, deformed feet"
)

# Each job: (cid, mode ['i2v'|'flf2v'], start_still, end_still_or_None, nframes, seed, neg, pos)
JOBS = [
    # --- 01 (4 I2V candidates): natural back walk -> abrupt tight dead-stop shoulder hitch (NO wide arm-flap!) ---
    (
        "01_v9_s1", "i2v", STILL_DIR / "still_01_v9_a.png", None, 65, 9111, NEG_01,
        "Realistic 35mm midnight Paris cinema shot staying strictly behind the man's back (back of short dark hair only, zero face turn, zero cars). With arms hanging calmly down close to his sides, he walks two easy steady steps forward down the damp sidewalk beside the warm French restaurant steps; abruptly his forward stride cuts completely dead as an unseen impact punches his front torso — keeping both arms tucked close in toward his stomach/ribs without swinging out wide, his right shoulder jerks tightly back-down and one knee dips slightly as he freezes rigid mid-stride.",
    ),
    (
        "01_v9_s2", "i2v", STILL_DIR / "still_01_v9_a.png", None, 65, 9112, NEG_01,
        "Grounded 35mm thriller shot strictly from behind in midnight Paris (no passing headlights, no face visible, arms never spread wide). In a white crewneck sweatshirt and dark pants, he takes two casual steps down the wet stone pavement past the warm restaurant doors; suddenly struck silently from ahead, his walking motion stops instantly dead in place with a sharp involuntary upper-spine twitch and slight hunch forward as one hand moves protectively inward toward his ribs.",
    ),
    (
        "01_v9_s3", "i2v", STILL_DIR / "still_01_v9_a.png", None, 65, 9113, NEG_01,
        "Quiet 35mm Paris night tracking shot directly behind the pedestrian (arms always close to torso, zero sparks, zero traffic). After two relaxed strides along the wet sidewalk toward the dark windowed apartment building ahead, an unseen silent sniper blow hits his chest: his left foot stops short mid-step, his chest/shoulders absorb one tight heavy shudder inward without flinging his arms, and he holds abruptly frozen in shock.",
    ),
    (
        "01_v9_s4", "i2v", V08_STILL / "still_01_v8_a.png", None, 65, 9114, NEG_01,
        "Strict back-view 35mm midnight shot in Paris (no vehicles, no headlights, zero camera-facing turn, arms never flared outward). Walking two calm relaxed steps forward down the wet walkway past the golden doors, his stride halts abruptly dead mid-step from a silent unseen chest impact — his upper back dips slightly forward-right in a sharp physical twitch as one hand lightly catches near his lower ribs.",
    ),

    # --- 02a (4 FLF2V candidates on Pair 1 & Pair 2): organic crimson capillary bleed + gentle 5-finger touch ---
    (
        "02a_v9_p1_s1", "flf2v", STILL_DIR / "still_02a_v9_start_1.png", STILL_DIR / "still_02a_v9_end_1.png", 65, 9221, NEG_02A,
        "Photorealistic 35mm macro cinema transition strictly collarbone-to-waist (zero projectiles, zero funnel fabric creases). At the start his torso catches one sharp subtle shudder from a silent chest impact; dark red liquid blood immediately begins wicking and soaking rapidly outward into the thick white knitted cotton weave across left-center chest, followed smoothly by his bare five-fingered right hand gently rising from below to press lightly over the soaking red edge with blood-tinted fingertips.",
    ),
    (
        "02a_v9_p1_s2", "flf2v", STILL_DIR / "still_02a_v9_start_1.png", STILL_DIR / "still_02a_v9_end_1.png", 65, 9222, NEG_02A,
        "Natural 35mm night close-up strictly on white crewneck sweatshirt chest (no CGI pinch cone, no flying bullet). Immediately following a tight physical chest flinch, deep crimson blood saturates rapidly outward through the white cotton fibers into an organic wet stain while his five-fingered hand lifts softly from below frame and touches the wet bloodstain with red-stained fingertips.",
    ),
    (
        "02a_v9_p2_s1", "flf2v", STILL_DIR / "still_02a_v9_start_2.png", STILL_DIR / "still_02a_v9_end_2.png", 65, 9231, NEG_02A,
        "Photorealistic 35mm close-up strictly below collarbone on clean white crewneck cotton sweatshirt (zero projectiles, zero fabric origami cone). A sudden muffled chest tremor ripples across his shoulders as rich dark arterial crimson rapidly blooms and saturates wetly down into the heavy cotton weave; smoothly afterward his clean five-fingered right hand rises from below to rest lightly against the wet dark-red stain with bloody fingertips.",
    ),
    (
        "02a_v9_p2_s2", "flf2v", STILL_DIR / "still_02a_v9_start_2.png", STILL_DIR / "still_02a_v9_end_2.png", 65, 9232, NEG_02A,
        "Grounded practical-effects 35mm macro on plain white cotton sweater chest at midnight. Following a subtle involuntary recoil shock, deep red blood wicks rapidly and naturally through the knitted cotton fibers into a wet dark-crimson patch while his bare five-fingered right hand reaches up gently to press beside the bleeding chest wound with stained fingertips.",
    ),

    # --- 02b (3 FLF2V candidates): standing glance -> FAST deadweight gravity collapse onto stone steps ---
    (
        "02b_v9_s1", "flf2v", STILL_DIR / "still_02b_v9_start_a.png", STILL_DIR / "still_02b_v9_end_a.png", 65, 9271, NEG_02B,
        "Realistic 35mm midnight back shot on wet French restaurant stone steps under pitch-black night sky (camera locked static, face hidden at all times). Standing upright for the first moment as the back of his short-haired head lifts slightly looking toward the dark windowed apartment building across the street, suddenly both legs lose all strength at once — his knees buckle straight out and his white-sweatshirt torso drops fast and heavily like dead weight flat down across the wet stone steps.",
    ),
    (
        "02b_v9_s2", "flf2v", STILL_DIR / "still_02b_v9_start_a.png", STILL_DIR / "still_02b_v9_end_a.png", 65, 9272, NEG_02B,
        "Static camera 35mm midnight back shot on wet stone Parisian stairs. Brief calm pause upright looking faintly up toward the dark building facade across the dark boulevard; then with sudden true gravity his knees snap weak beneath him and his wounded body crashes rapidly and heavily downward onto the wet stone steps into a motionless limp sprawl.",
    ),
    (
        "02b_v9_s3", "flf2v", STILL_DIR / "still_02b_v9_start_a.png", STILL_DIR / "still_02b_v9_end_a.png", 65, 9273, NEG_02B,
        "Dramatic locked-off 35mm midnight shot strictly from behind on wet stone restaurant steps (zero slow float). After holding upright for one calm second gazing across toward the dark building windows, his knees give way abruptly and he plunges swiftly straight down sideways onto the wet stone steps with heavy sudden impact.",
    ),
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
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            last_err = RuntimeError(f"HTTP {e.code} on {url}: {body[:800]}")
            if 400 <= e.code < 500:
                raise last_err from e
            if attempt + 1 < retries:
                time.sleep(2.5 * (attempt + 1))
        except Exception as e:
            last_err = e
            if attempt + 1 < retries:
                time.sleep(2.5 * (attempt + 1))
    raise last_err


def ensure_wan22_and_comfyui(base_gradio: str) -> str:
    print("[2/5] Starting ComfyUI & verifying Wan2.2 I2V/FLF2V pack on G4 GPU...", flush=True)
    http_req(f"{base_gradio}/minimax_api/comfyui/start", data=b"{}", headers={"Content-Type": "application/json"}, method="POST", timeout=120)
    pack_requested = False
    for _ in range(240):
        st = json.loads(http_req(f"{base_gradio}/minimax_api/comfyui/status", timeout=30))
        c = st.get("comfyui") or st
        cf_url = (c.get("public_url") or c.get("url") or c.get("comfy_url") or c.get("comfyui_url") or "").rstrip("/")
        is_run = bool(c.get("is_running") or c.get("running"))
        packs = {p.get("id"): p for p in (c.get("preset_packs") or [])}
        wan_pack = packs.get("wan22_i2v_flf2v") or {}
        wan_ready = bool(wan_pack.get("ready")) or int(wan_pack.get("installed_models") or 0) >= 6
        is_dl = bool(c.get("is_downloading_weight") or c.get("installing_pack_id"))
        msg = c.get("status_message", "")
        if is_run and cf_url and not wan_ready and not pack_requested and not is_dl:
            print("  [install_pack] Installing wan22_i2v_flf2v weights (6 models)...", flush=True)
            http_req(
                f"{base_gradio}/minimax_api/comfyui/install_pack",
                data=json.dumps({"pack_id": "wan22_i2v_flf2v", "auto_start": True}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
                timeout=60,
            )
            pack_requested = True
        elif is_run and cf_url and wan_ready and not is_dl:
            return cf_url
        if msg:
            print(f"  [comfy wait] {msg} (wan={wan_pack.get('installed_models', 0)}/6)", flush=True)
        time.sleep(3.5)
    raise RuntimeError("Timed out waiting for ComfyUI + Wan2.2 ready")


def has_vhs_node(cf_url: str) -> bool:
    try:
        info = json.loads(http_req(f"{cf_url}/object_info/VHS_VideoCombine", timeout=20, retries=2))
        return "VHS_VideoCombine" in info
    except Exception:
        return False


def inspect_flf_node(cf_url: str) -> dict:
    info = json.loads(http_req(f"{cf_url}/object_info/WanFirstLastFrameToVideo", timeout=20, retries=3))
    node_meta = info.get("WanFirstLastFrameToVideo") or {}
    req = list((node_meta.get("input") or {}).get("required", {}).keys())
    opt = list((node_meta.get("input") or {}).get("optional", {}).keys())
    print(f"  [node check] WanFirstLastFrameToVideo required={req} optional={opt}", flush=True)
    return node_meta


def upload_image(cf_url: str, img_path: Path) -> str:
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
        f"{cf_url}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    return json.loads(raw)["name"]


def build_wan22_graph(
    mode: str,
    start_img_name: str,
    end_img_name: str | None,
    pos_prompt: str,
    neg_prompt: str,
    num_frames: int,
    seed: int,
    prefix: str,
    use_vhs: bool = False,
) -> dict:
    g = {
        "84": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan", "device": "default"}},
        "90": {"class_type": "VAELoader", "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},
        "95": {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors", "weight_dtype": "default"}},
        "96": {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors", "weight_dtype": "default"}},
        "101": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["95", 0], "lora_name": "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors", "strength_model": 1.0}},
        "102": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["96", 0], "lora_name": "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors", "strength_model": 1.0}},
        "104": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["101", 0], "shift": 5.0}},
        "103": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["102", 0], "shift": 5.0}},
        "93": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["84", 0], "text": pos_prompt}},
        "89": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["84", 0], "text": neg_prompt}},
        "97": {"class_type": "LoadImage", "inputs": {"image": start_img_name}},
        "86": {"class_type": "KSamplerAdvanced", "inputs": {"add_noise": "enable", "noise_seed": int(seed), "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "start_at_step": 0, "end_at_step": 2, "return_with_leftover_noise": "enable", "model": ["104", 0], "positive": ["98", 0], "negative": ["98", 1], "latent_image": ["98", 2]}},
        "85": {"class_type": "KSamplerAdvanced", "inputs": {"add_noise": "disable", "noise_seed": 0, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "start_at_step": 2, "end_at_step": 4, "return_with_leftover_noise": "disable", "model": ["103", 0], "positive": ["98", 0], "negative": ["98", 1], "latent_image": ["86", 0]}},
        "87": {"class_type": "VAEDecode", "inputs": {"samples": ["85", 0], "vae": ["90", 0]}},
    }
    if mode == "flf2v":
        assert end_img_name is not None
        g["99"] = {"class_type": "LoadImage", "inputs": {"image": end_img_name}}
        g["98"] = {
            "class_type": "WanFirstLastFrameToVideo",
            "inputs": {
                "positive": ["93", 0],
                "negative": ["89", 0],
                "vae": ["90", 0],
                "start_image": ["97", 0],
                "end_image": ["99", 0],
                "width": 1280,
                "height": 720,
                "length": int(num_frames),
                "batch_size": 1,
            },
        }
    else:
        g["98"] = {
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
        }
    if use_vhs:
        g["108"] = {"class_type": "VHS_VideoCombine", "inputs": {"images": ["87", 0], "frame_rate": 16, "loop_count": 0, "filename_prefix": prefix, "format": "video/h264-mp4", "pix_fmt": "yuv420p", "crf": 18, "save_metadata": False, "trim_to_audio": False, "pingpong": False, "save_output": True}}
    else:
        g["108"] = {"class_type": "CreateVideo", "inputs": {"images": ["87", 0], "fps": 16}}
        g["109"] = {"class_type": "SaveVideo", "inputs": {"video": ["108", 0], "filename_prefix": prefix, "format": "auto", "codec": "auto"}}
    return g


def main():
    force = "--force" in sys.argv
    only_ids = [a for a in sys.argv[1:] if not a.startswith("--")]
    stop_ka = threading.Event()
    uploaded_cache: dict[Path, str] = {}
    try:
        print("[1/5] Waking EasyColab G4 GPU for ComfyUI Wan2.2 Stage 2 (v0.9 I2V + FLF2V)...", flush=True)
        wake_out = run_bridge("wake", "--gpu", "G4")
        print(wake_out, flush=True)
        if "WAKE_ERROR" in wake_out:
            raise RuntimeError(f"wake failed: {wake_out}")
        m = re.findall(r"https://[a-zA-Z0-9.-]+\.gradio\.live", wake_out)
        if not m:
            raise RuntimeError("Missing gradio.live URL")
        base_gradio = m[-1].rstrip("/")

        ka_thread = threading.Thread(target=keepalive_loop, args=(stop_ka,), daemon=True)
        ka_thread.start()

        cf_url = ensure_wan22_and_comfyui(base_gradio)
        use_vhs = has_vhs_node(cf_url)
        inspect_flf_node(cf_url)
        print(f"[3/5] ComfyUI URL ready: {cf_url} (use_vhs={use_vhs})", flush=True)
        client_id = uuid.uuid4().hex

        for idx, (cid, mode, s_path, e_path, nframes, seed, neg_prompt, prompt) in enumerate(JOBS, 1):
            if only_ids and cid not in only_ids:
                continue
            if not s_path.exists():
                raise FileNotFoundError(f"Missing start still: {s_path}")
            if mode == "flf2v" and (e_path is None or not e_path.exists()):
                raise FileNotFoundError(f"Missing end still: {e_path}")
            out_mp4 = CLIP_DIR / f"clip_{cid}.mp4"
            if out_mp4.exists() and out_mp4.stat().st_size > 20_000 and not force:
                print(f"[skip] clip_{cid}.mp4 already exists", flush=True)
                continue
            t0 = time.time()
            try:
                http_req(f"{base_gradio}/minimax_api/comfyui/status", timeout=15)
            except Exception:
                pass
            if s_path not in uploaded_cache:
                uploaded_cache[s_path] = upload_image(cf_url, s_path)
            s_name = uploaded_cache[s_path]
            e_name = None
            if mode == "flf2v" and e_path is not None:
                if e_path not in uploaded_cache:
                    uploaded_cache[e_path] = upload_image(cf_url, e_path)
                e_name = uploaded_cache[e_path]

            graph = build_wan22_graph(mode, s_name, e_name, prompt, neg_prompt, nframes, seed, f"v09_clip_{cid}", use_vhs=use_vhs)
            sub = json.loads(http_req(f"{cf_url}/prompt", data=json.dumps({"prompt": graph, "client_id": client_id}).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST"))
            pid = sub["prompt_id"]
            print(f"[{idx}/{len(JOBS)}] submitted clip_{cid} ({mode}, {nframes}f, seed={seed}) pid={pid[:8]}...", flush=True)
            while True:
                time.sleep(3.0)
                hist = json.loads(http_req(f"{cf_url}/history/{pid}", timeout=30))
                if pid not in hist:
                    continue
                entry = hist[pid]
                if entry.get("status", {}).get("status_str") == "error":
                    raise RuntimeError(f"ComfyUI error on {cid}: {entry.get('status')}")
                outputs = entry.get("outputs", {})
                out_node = outputs.get("109") or outputs.get("108")
                if out_node:
                    gifs = out_node.get("gifs") or out_node.get("videos") or out_node.get("images") or []
                    mp4_info = next((g for g in gifs if str(g.get("filename", "")).endswith(".mp4")), None) or (gifs[0] if gifs else None)
                    if not mp4_info:
                        raise RuntimeError(f"No output file in history for {cid}: {outputs}")
                    qs = urllib.parse.urlencode({"filename": mp4_info["filename"], "subfolder": mp4_info.get("subfolder", ""), "type": mp4_info.get("type", "output")})
                    vid_bytes = http_req(f"{cf_url}/view?{qs}", timeout=120)
                    out_mp4.write_bytes(vid_bytes)
                    print(f"[done] clip_{cid}.mp4 ({len(vid_bytes) // 1024} KB, {time.time() - t0:.1f}s)", flush=True)
                    break
        print("[4/5] ALL V0.9 CANDIDATE CLIPS GENERATED SUCCESSFULLY!", flush=True)
    finally:
        stop_ka.set()
        print("[5/5] IMMEDIATELY stopping all Colab GPUs (stop_all)...", flush=True)
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
