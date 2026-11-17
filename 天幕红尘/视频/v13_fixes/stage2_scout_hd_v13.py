#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage 2 (v0.13): Fast 480p Scout -> 1-frame-step inspection -> Warm G4 720p HD Wan2.2 pipeline
for redesigned Paris Cold Open clips (01_hit backward chest jolt, 02a large soak + palm-on-blood,
02b1 weakening look-up-and-sag, 02b2 fast knees-give sideways full-length sprawl).
"""

import json
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

V10_DIR = Path(__file__).resolve().parent.parent / "v10_fixes"
V09_DIR = Path(__file__).resolve().parent.parent / "v09_fixes"
sys.path.insert(0, str(V09_DIR))
sys.path.insert(0, str(V10_DIR))

import stage2_clips_v09 as s2v9
import stage2_scout_hd_v10 as s2v10

ROOT = Path(__file__).resolve().parent
STILL_DIR = ROOT / "stills"
SCOUT_DIR = ROOT / "scout_clips"
CLIP_DIR = ROOT / "clips"
SCOUT_DIR.mkdir(parents=True, exist_ok=True)
CLIP_DIR.mkdir(parents=True, exist_ok=True)
SCRATCH = Path("/Users/duxiying/.gemini/antigravity-cli/brain/a18da7f8-846f-4989-874d-c081bff5e532/scratch")

NEG_REAR_VID = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，文字水印，整体发灰，最差质量，低质量，JPEG压缩残留，"
    "turning around, face visible, cheek profile, wide crab straddle, jumping onto stairs, drunk swaying, "
    "sitting on buttocks, hands propped behind hips, kowtow kneeling hump, yoga childs pose, slow motion, orange flash"
)
NEG_CHEST_VID = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，文字水印，整体发灰，最差质量，低质量，JPEG压缩残留，"
    "black vertical gash, open slit wound, jagged spikes, extra fingers, missing fingers, distorted hand, face, watch, bracelet"
)

DEFAULT_SCOUT_JOBS = [
    (
        "01_hit_s1", "flf2v",
        STILL_DIR / "still_01_v13_cutframe.png", STILL_DIR / "still_01_v13_hit_b.png",
        25, 13121, NEG_REAR_VID,
        "Immediate real-time 35mm cinema continuation strictly from behind on the exact Paris night street (zero face turn, zero camera shift). "
        "Just struck violently in the upper front chest by a silent sniper round from ahead: forward walking stride freezes dead mid-step, "
        "rear leg locks stiff catching weight while upper back and shoulders JERK SUBTLY BACKWARD in authentic chest-impact shock recoil, "
        "chin lifting a fraction back upright before stabilizing, as his right arm swings inward/upward toward his front chest."
    ),
    (
        "01_hit_s2", "flf2v",
        STILL_DIR / "still_01_v13_cutframe.png", STILL_DIR / "still_01_v13_hit_c.png",
        25, 13122, NEG_REAR_VID,
        "Seamless fast 35mm continuation from the exact walking back-view cutframe (strictly back-of-head only, no side profile). "
        "Struck abruptly in the chest from the front: walk arrests dead in stride, knees brake hard with narrow footing, torso whips "
        "backward slightly off-balance in real ballistic front-chest shock recoil while right elbow pulls sharply inward to front ribcage."
    ),
    (
        "02a_s1", "flf2v",
        STILL_DIR / "still_02a_v13_start.png", STILL_DIR / "still_02a_v13_end_a.png",
        33, 13221, NEG_CHEST_VID,
        "Real-time 35mm medium-closeup anchored to warm Paris bistro bokeh lighting on heavyweight off-white cotton crewneck. "
        "Starts with small first stain already visible as rising bare five-fingered hand lifts toward chest; at frame 4 a silent bullet punch "
        "ripples the cotton inward and backwards slightly, and deep wet crimson blood rapidly surges outward soaking a wide ~15cm cotton patch "
        "(zero black tear/slit) as his five-fingered right palm presses directly onto the center-bottom wet bloodstain, red soaking his fingers."
    ),
    (
        "02a_s2", "flf2v",
        STILL_DIR / "still_02a_v13_start.png", STILL_DIR / "still_02a_v13_end_a.png",
        33, 13222, NEG_CHEST_VID,
        "Authentic 35mm cinema chest closeup in warm dark Parisian night glow. On opening second-bullet impact, his chest flinches briefly "
        "backward as organic dark-crimson blood spreads rapidly outward across a large patch of cotton knit fleece while his anatomically "
        "normal five-fingered right palm rises and presses squarely against the soaking crimson center, fingers coated naturally in wet blood."
    ),
    (
        "02b1_s1", "i2v",
        STILL_DIR / "still_02b1_v13.png", None,
        33, 13311, NEG_REAR_VID,
        "Subtle authentic 35mm night exterior over-shoulder rear view facing the towering 6-story windowed Parisian apartment building across the road "
        "(strictly back of hair & white shoulders, zero cheek turn). Struggling to stay upright, he glances slightly up toward high lit windows "
        "across the avenue, breathes heavily, and in the final beat his head dips and shoulders subtly lose strength sinking ~6cm downward as legs weaken."
    ),
    (
        "02b1_s2", "i2v",
        STILL_DIR / "still_02b1_v13.png", None,
        33, 13312, NEG_REAR_VID,
        "Quiet dramatic 35mm night over-shoulder shot facing the dense window grid across the Paris avenue (strictly rear head/shoulders). "
        "He tilts chin subtly upward looking at high windows, whispers grimly, then chin lowers and shoulders visibly droop downward slightly "
        "under draining blood loss right before collapsing."
    ),
    (
        "02b2_s1", "flf2v",
        STILL_DIR / "still_02b2_v13_start.png", STILL_DIR / "still_02b2_v13_end_c.png",
        25, 13421, NEG_REAR_VID,
        "Fast real-time deadweight sniper collapse on flat dark stone pavement (LOCK camera, keep left four steps untouched, ZERO sitting back "
        "on hips, ZERO kowtow kneeling hump, ZERO jumping onto left stairs). Already halted clutching chest, his knees suddenly buckle "
        "sideways/down under gravity and his entire body topples cleanly forward-right like a felled tree, stretching out completely flat at full "
        "length across the wide dark stone sidewalk with both legs extended limp behind and arms splayed slack motionless."
    ),
    (
        "02b2_s2", "flf2v",
        STILL_DIR / "still_02b2_v13_start.png", STILL_DIR / "still_02b2_v13_end_a.png",
        25, 13422, NEG_REAR_VID,
        "Abrupt realistic gravity collapse in real-time cinema speed strictly on the flat dark pavement right of the untouched left steps "
        "(ZERO frog squat, ZERO sitting backward, ZERO kneeling bow). From the halted chest-clutch stance, both knees give way straight down "
        "as upper torso pitches rapidly sideways-right and slams dead-weight full-length flat onto his side/front on the stones with legs "
        "stretched long and arms spread limply motionless."
    ),
]


def make_full_sheet(mp4_path: Path, n_frames: int) -> Path:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    out_png = SCRATCH / f"v13_{mp4_path.stem}.png"
    tile = "5x5" if n_frames <= 25 else "6x6"
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", str(mp4_path),
            "-vf", f"select='between(n,0,{n_frames - 1})',scale=320:-1,tile={tile}",
            "-frames:v", "1", str(out_png),
        ],
        check=True,
    )
    return out_png


def resolve_jobs(json_path: Path, fallback_jobs: list[tuple]) -> list[tuple]:
    items = json.loads(json_path.read_text(encoding="utf-8"))
    by_id = {j[0]: j for j in fallback_jobs}
    out = []
    for item in items:
        if isinstance(item, str):
            out.append(by_id[item])
        else:
            base = list(by_id[item["base_id"]])
            base[0] = item.get("id", base[0])
            for k, idx in (("mode", 1), ("frames", 4), ("seed", 5), ("neg", 6), ("prompt", 7)):
                if k in item:
                    base[idx] = int(item[k]) if k in ("frames", "seed") else item[k]
            if "start" in item:
                base[2] = Path(item["start"])
            if "end" in item:
                base[3] = Path(item["end"]) if item["end"] else None
            out.append(tuple(base))
    return out


def main():
    mode_arg = sys.argv[1] if len(sys.argv) > 1 else "--warm-pipeline"
    scout_plan_path = ROOT / "scout_plan.json"
    hd_plan_path = ROOT / "hd_plan.json"
    ready_flag = ROOT / "scout_ready.json"

    stop_ka = threading.Event()
    uploaded_cache: dict[Path, str] = {}
    try:
        print(f"[1/5] Waking EasyColab G4 GPU for v0.13 Wan2.2 ({mode_arg})...", flush=True)
        wake_out = s2v9.run_bridge("wake", "--gpu", "G4")
        print(wake_out, flush=True)
        if "WAKE_ERROR" in wake_out:
            raise RuntimeError(f"wake failed: {wake_out}")
        m = re.findall(r"https://[a-zA-Z0-9.-]+\.gradio\.live", wake_out)
        if not m:
            raise RuntimeError("Missing gradio.live URL")
        base_gradio = m[-1].rstrip("/")

        threading.Thread(target=s2v9.keepalive_loop, args=(stop_ka,), daemon=True).start()

        cf_url = s2v9.ensure_wan22_and_comfyui(base_gradio)
        use_vhs = s2v9.has_vhs_node(cf_url)
        client_id = uuid.uuid4().hex
        print(f"[3/5] ComfyUI ready: {cf_url}", flush=True)

        if mode_arg in ("--scout", "--warm-pipeline"):
            for p in (ready_flag, hd_plan_path):
                if p.exists():
                    p.unlink()
            jobs = resolve_jobs(scout_plan_path, DEFAULT_SCOUT_JOBS) if scout_plan_path.exists() else DEFAULT_SCOUT_JOBS
            sheets = []
            for job in jobs:
                mp4_p = s2v10.submit_and_download(cf_url, base_gradio, client_id, use_vhs, uploaded_cache, job, 832, 480, SCOUT_DIR, "v13s")
                sheets.append(str(make_full_sheet(mp4_p, job[4])))
            ready_flag.write_text(json.dumps({"sheets": sheets, "ready_at": time.time()}, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[SCOUT DONE] {len(sheets)} full-frame-step sheets ready.", flush=True)

        if mode_arg == "--warm-pipeline":
            print("[WAIT-APPROVAL] Waiting up to 300s on warm G4 for v13_fixes/hd_plan.json...", flush=True)
            deadline = time.time() + 300.0
            while time.time() < deadline:
                if hd_plan_path.exists() and hd_plan_path.stat().st_size > 5:
                    time.sleep(0.5)
                    break
                time.sleep(2.0)
            else:
                print("[TIMEOUT] No hd_plan.json within 300s; safely stopping GPU.", flush=True)
                return

        if mode_arg in ("--hd", "--warm-pipeline"):
            hd_jobs = resolve_jobs(hd_plan_path, DEFAULT_SCOUT_JOBS)
            hd_sheets = []
            for job in hd_jobs:
                mp4_p = s2v10.submit_and_download(cf_url, base_gradio, client_id, use_vhs, uploaded_cache, job, 1280, 720, CLIP_DIR, "v13hd")
                hd_sheets.append(str(make_full_sheet(mp4_p, job[4])))
            print(f"[HD DONE] {len(hd_sheets)} 720p clips ready!", flush=True)
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
