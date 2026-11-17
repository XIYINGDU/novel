#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage 2 (v0.10): Fast 480p Scout -> Selective 720p HD Pipeline on EasyColab G4.
Reuses single warmed ComfyUI session across Scout and HD so 35GB Wan2.2 weights download ONCE.

Modes:
  --scout         Render small 832x480 scout candidates (~20s/clip), build contact sheets, then stop_all.
  --hd            Render final 1280x720 clips listed in hd_plan.json (or default winners), then stop_all.
  --warm-pipeline Run --scout, extract contact sheets, wait up to 180s for hd_plan.json in the SAME
                  live G4 ComfyUI session, render HD clips immediately, then stop_all!
"""

import json
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid
from pathlib import Path

V09_DIR = Path(__file__).resolve().parent.parent / "v09_fixes"
sys.path.insert(0, str(V09_DIR))
import stage2_clips_v09 as s2v9

VID_ROOT = s2v9.VID_ROOT
V10 = VID_ROOT / "v10_fixes"
STILL_DIR = V10 / "stills"
SCOUT_DIR = V10 / "scout_clips"
CLIP_DIR = V10 / "clips"
for d in (SCOUT_DIR, CLIP_DIR):
    d.mkdir(parents=True, exist_ok=True)

SCRATCH_SHEET_DIR = Path("/Users/duxiying/.gemini/antigravity-cli/brain/a18da7f8-846f-4989-874d-c081bff5e532/scratch")

NEG_01 = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，文字水印，整体发灰，最差质量，低质量，JPEG压缩残留，"
    "hands behind back, clasped hands behind waist, touching lower back, elbows flared wide, T-pose, jumping jack, "
    "turning around, face visible, profile face, car, automobile, sedan, taxi, vehicle, headlights, taillights, traffic, "
    "muzzle flash, sparks, blue sky, daylight, long hair, extra limbs"
)
NEG_02A = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，文字水印，整体发灰，最差质量，低质量，JPEG压缩残留，"
    "blood dripping from top, blood falling from neck, red stream from top edge, pouring from above, "
    "bullet, projectile, sparks, smoke, origami cloth pinch, dining tables behind, candles behind chest, "
    "six fingers, extra fingers, fused fingers, silver bracelet, watch, cufflinks, mouth, lips, face"
)
NEG_02B1 = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，文字水印，整体发灰，最差质量，低质量，JPEG压缩残留，"
    "turning around, face visible, profile face, long hair, blue sky, daylight, walking away, car headlights"
)
NEG_02B2 = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，文字水印，整体发灰，最差质量，低质量，JPEG压缩残留，"
    "slow sitting down, praying pose, push-up hold, long hair, turning face to camera, face visible, "
    "blue sky, daylight, hovering, levitating, extra legs, deformed feet"
)

# Default scout slate (2 focused seeds x 4 shots = 8 fast 480p clips -> ~2.5-3 min!)
DEFAULT_SCOUT_JOBS = [
    (
        "01_v10_s1", "i2v", STILL_DIR / "still_01_v10_a.png", None, 49, 10111, NEG_01,
        "Realistic 35mm midnight Paris cinema shot staying strictly behind the man on a deserted French restaurant threshold (zero cars, zero face turn). Arms hanging loosely at his sides, he walks two easy steps DOWN the four limestone steps onto the flagstone forecourt facing the dark multi-windowed building across the empty boulevard; abruptly mid-step an unseen sniper chest hit jolts his shoulders and upper spine backward an inch in sharp physical shock — front foot plants dead stiff, upper back hunches tight in startled pain while hands stay down at his sides.",
    ),
    (
        "01_v10_s2", "i2v", STILL_DIR / "still_01_v10_a.png", None, 49, 10112, NEG_01,
        "Grounded 35mm Paris night thriller shot strictly from behind outside a warm French restaurant doorway on an empty deserted street (never hands behind back, zero traffic). With both arms relaxed beside his hips, he strolls smoothly DOWN the four limestone steps; suddenly struck silently in the front chest from ahead, his forward step slams abruptly dead — chest caves slightly back, shoulders twitch upward-right in physical trauma recoil, freezing rigid on the stones.",
    ),
    (
        "02a_v10_s1", "flf2v", STILL_DIR / "still_02a_v10_start.png", STILL_DIR / "still_02a_v10_end.png", 41, 10211, NEG_02A,
        "Photorealistic 35mm macro cinema transition strictly chin-below to waist on dark Parisian midnight street bokeh (air above completely clear, zero red falling from neck). Immediately his chest jerks slightly back-inward from an abrupt silent bullet punch, slight crease at left chest; dark arterial blood emerges directly from inside the center white cotton weave and wicks rapidly outward downward into the knit while lower chin tilts faintly down and his bare five-fingered right hand rises gently to touch beside the wet bloodstain with stained fingertips.",
    ),
    (
        "02a_v10_s2", "flf2v", STILL_DIR / "still_02a_v10_start.png", STILL_DIR / "still_02a_v10_end.png", 41, 10212, NEG_02A,
        "Intimate 35mm midnight outdoor street-bokeh close-up on white crewneck sweatshirt chest (no liquid dripping from top collar). His shoulders and chest absorb one sharp involuntary recoil shudder inward from an unseen shot; deep dark crimson blooms rapidly straight from within the chest cotton weave into a soaking patch as his clean five-fingered right hand moves up softly to touch the bleeding cloth, fingertips visibly wet with blood.",
    ),
    (
        "02b1_v10_s1", "i2v", STILL_DIR / "still_02b1_v10_a.png", None, 33, 10311, NEG_02B1,
        "Dramatic 35mm midnight over-shoulder rear shot strictly behind the wounded man's white sweatshirt shoulders and short dark hair (face hidden at all times). Across the dark street looms the towering 8-story building packed with black unlit windows; slowly the back of his head tilts visibly upward glancing toward those high dark windows, pauses a brief heartbeat in cold realization, then bows faintly downward toward his chest.",
    ),
    (
        "02b1_v10_s2", "i2v", STILL_DIR / "still_02b1_v10_a.png", None, 33, 10312, NEG_02B1,
        "Quiet tense 35mm Paris night rear shot staying behind the man's short dark hair and white sweatshirt shoulders looking toward the huge dark multi-windowed apartment facade ahead. His chin tilts upward slightly as if scanning the dark windows across the avenue, holds a split second with a slight ragged breath across his shoulders, then drops his head subtly downward toward his chest.",
    ),
    (
        "02b2_v10_s1", "flf2v", STILL_DIR / "still_02b2_v10_start.png", STILL_DIR / "still_02b2_v10_end.png", 41, 10411, NEG_02B2,
        "Static locked-off 35mm midnight back shot on those four limestone restaurant steps facing the empty dark Paris street and opposite dark building (face never seen). Holding weak posture for the first split-second, suddenly both knees snap loose at once under dead weight and his white-sweatshirt figure collapses swiftly sideways downward across the limestone steps into a limp motionless heap.",
    ),
    (
        "02b2_v10_s2", "flf2v", STILL_DIR / "still_02b2_v10_start.png", STILL_DIR / "still_02b2_v10_end.png", 41, 10412, NEG_02B2,
        "Locked-off camera 35mm Paris night back shot on four French restaurant entrance limestone steps. After one tense trembling beat at the bottom step, his legs fold helplessly beneath him and his heavy body drops rapidly and limply sideways onto the limestone steps, lying completely still.",
    ),
]


def submit_and_download(cf_url: str, base_gradio: str, client_id: str, use_vhs: bool, uploaded_cache: dict, job: tuple, width: int, height: int, out_dir: Path, prefix_tag: str) -> Path:
    cid, mode, s_path, e_path, nframes, seed, neg_prompt, prompt = job
    s_path = Path(s_path)
    e_path = Path(e_path) if e_path else None
    out_mp4 = out_dir / f"clip_{cid}.mp4"
    t0 = time.time()
    try:
        s2v9.http_req(f"{base_gradio}/minimax_api/comfyui/status", timeout=15)
    except Exception:
        pass
    if s_path not in uploaded_cache:
        uploaded_cache[s_path] = s2v9.upload_image(cf_url, s_path)
    s_name = uploaded_cache[s_path]
    e_name = None
    if mode == "flf2v":
        assert e_path is not None
        if e_path not in uploaded_cache:
            uploaded_cache[e_path] = s2v9.upload_image(cf_url, e_path)
        e_name = uploaded_cache[e_path]

    graph = s2v9.build_wan22_graph(mode, s_name, e_name, prompt, neg_prompt, nframes, seed, f"{prefix_tag}_{cid}", use_vhs=use_vhs)
    graph["98"]["inputs"]["width"] = int(width)
    graph["98"]["inputs"]["height"] = int(height)

    sub = json.loads(
        s2v9.http_req(
            f"{cf_url}/prompt",
            data=json.dumps({"prompt": graph, "client_id": client_id}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    )
    pid = sub["prompt_id"]
    print(f"  [submit] {out_mp4.name} ({mode}, {width}x{height}, {nframes}f, seed={seed}) pid={pid[:8]}...", flush=True)
    while True:
        time.sleep(2.5)
        hist = json.loads(s2v9.http_req(f"{cf_url}/history/{pid}", timeout=30))
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
            vid_bytes = s2v9.http_req(f"{cf_url}/view?{qs}", timeout=120)
            out_mp4.write_bytes(vid_bytes)
            print(f"  [done]   {out_mp4.name} ({len(vid_bytes) // 1024} KB, {time.time() - t0:.1f}s)", flush=True)
            return out_mp4


def make_contact_sheet(mp4_path: Path, step: int = 3):
    SCRATCH_SHEET_DIR.mkdir(parents=True, exist_ok=True)
    out_png = SCRATCH_SHEET_DIR / f"v10_{mp4_path.stem}.png"
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", str(mp4_path),
            "-vf", f"select='not(mod(n,{step}))',scale=320:-1,tile=5x4",
            "-frames:v", "1", str(out_png),
        ],
        check=True,
    )
    return out_png


def resolve_jobs_from_json(json_path: Path) -> list[tuple]:
    items = json.loads(json_path.read_text(encoding="utf-8"))
    by_id = {j[0]: j for j in DEFAULT_SCOUT_JOBS}
    out = []
    for item in items:
        if isinstance(item, str):
            out.append(by_id[item])
        else:
            # dict allowing canonical out_id, seed override, or custom prompt override
            base = list(by_id[item["base_id"]]) if item.get("base_id") in by_id else None
            if base is None:
                out.append((
                    item["id"], item["mode"], Path(item["start"]), Path(item["end"]) if item.get("end") else None,
                    int(item["frames"]), int(item["seed"]), item["neg"], item["prompt"],
                ))
            else:
                if "id" in item:
                    base[0] = item["id"]
                if "start" in item:
                    base[2] = Path(item["start"])
                if "end" in item:
                    base[3] = Path(item["end"]) if item["end"] else None
                if "frames" in item:
                    base[4] = int(item["frames"])
                if "seed" in item:
                    base[5] = int(item["seed"])
                if "neg" in item:
                    base[6] = item["neg"]
                if "prompt" in item:
                    base[7] = item["prompt"]
                out.append(tuple(base))
    return out


def main():
    mode_arg = sys.argv[1] if len(sys.argv) > 1 else "--scout"
    scout_plan_path = V10 / "scout_plan.json"
    hd_plan_path = V10 / "hd_plan.json"
    scout_ready_flag = V10 / "scout_ready.json"

    stop_ka = threading.Event()
    uploaded_cache: dict[Path, str] = {}
    try:
        print(f"[1/5] Waking EasyColab G4 GPU for v0.10 ({mode_arg})...", flush=True)
        wake_out = s2v9.run_bridge("wake", "--gpu", "G4")
        print(wake_out, flush=True)
        if "WAKE_ERROR" in wake_out:
            raise RuntimeError(f"wake failed: {wake_out}")
        m = re.findall(r"https://[a-zA-Z0-9.-]+\.gradio\.live", wake_out)
        if not m:
            raise RuntimeError("Missing gradio.live URL")
        base_gradio = m[-1].rstrip("/")

        ka_thread = threading.Thread(target=s2v9.keepalive_loop, args=(stop_ka,), daemon=True)
        ka_thread.start()

        cf_url = s2v9.ensure_wan22_and_comfyui(base_gradio)
        use_vhs = s2v9.has_vhs_node(cf_url)
        client_id = uuid.uuid4().hex
        print(f"[3/5] ComfyUI ready: {cf_url} (use_vhs={use_vhs})", flush=True)

        if mode_arg in ("--scout", "--warm-pipeline"):
            if hd_plan_path.exists():
                hd_plan_path.unlink()
            if scout_ready_flag.exists():
                scout_ready_flag.unlink()
            scout_jobs = resolve_jobs_from_json(scout_plan_path) if scout_plan_path.exists() else DEFAULT_SCOUT_JOBS
            sheets = []
            print(f"[4/5-SCOUT] Running {len(scout_jobs)} fast 832x480 scout clips...", flush=True)
            for job in scout_jobs:
                mp4_p = submit_and_download(cf_url, base_gradio, client_id, use_vhs, uploaded_cache, job, 832, 480, SCOUT_DIR, "v10s")
                sh = make_contact_sheet(mp4_p, step=2 if job[4] <= 41 else 3)
                sheets.append(str(sh))
            scout_ready_flag.write_text(json.dumps({"sheets": sheets, "ready_at": time.time()}, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[SCOUT DONE] Contact sheets ready ({len(sheets)}).", flush=True)

        if mode_arg == "--warm-pipeline":
            print("[WAIT-APPROVAL] Waiting up to 240s on warm G4 for hd_plan.json...", flush=True)
            deadline = time.time() + 240.0
            while time.time() < deadline:
                if hd_plan_path.exists() and hd_plan_path.stat().st_size > 10:
                    time.sleep(0.5)
                    break
                time.sleep(2.0)
            else:
                print("[TIMEOUT] No hd_plan.json within 240s; safely stopping GPU.", flush=True)
                return

        if mode_arg in ("--hd", "--warm-pipeline"):
            hd_jobs = resolve_jobs_from_json(hd_plan_path) if hd_plan_path.exists() else [DEFAULT_SCOUT_JOBS[0], DEFAULT_SCOUT_JOBS[2], DEFAULT_SCOUT_JOBS[4], DEFAULT_SCOUT_JOBS[6]]
            print(f"[4/5-HD] Rendering {len(hd_jobs)} winning 1280x720 HD clips on warmed session...", flush=True)
            for job in hd_jobs:
                mp4_p = submit_and_download(cf_url, base_gradio, client_id, use_vhs, uploaded_cache, job, 1280, 720, CLIP_DIR, "v10hd")
                make_contact_sheet(mp4_p, step=2 if job[4] <= 41 else 3)
            print("[HD DONE] All winning 720p clips downloaded!", flush=True)

    finally:
        stop_ka.set()
        print("[5/5] IMMEDIATELY stopping all Colab GPUs (stop_all)...", flush=True)
        for attempt in range(4):
            out = s2v9.run_bridge("stop_all")
            print(out, flush=True)
            if '"ok": true' in out and '"burn_rate_hourly": 0.0' in out:
                break
            time.sleep(3.0 * (attempt + 1))
        print("[auth_status check]", flush=True)
        print(s2v9.run_bridge("auth_status"), flush=True)


if __name__ == "__main__":
    main()
