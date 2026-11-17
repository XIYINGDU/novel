#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v0.10 Master + Incremental Fast Pipeline for《天幕红尘》Ep01 Opening Pilot:
1. Speed Architecture:
   - Per-shot SHA-256 caching + direct cross-version reuse of unchanged v0.9 shots (03..13)
     so RIFE v4.26 & PIL only run on modified shots (~10x faster iteration!).
   - Cinema color/grain baked cleanly per graded shot, enabling instant `-c:v copy` concat
     with zero redundant full-movie re-encoding.
   - Supports `--fast` (preview preset using scout clips if HD not ready) and `--master` (default).
2. Redesigned Paris Cold Open (`01 -> 02a -> 02b1 -> 02b2`) matching Episode 01 script + Chapter 44:
   - Consistent French restaurant 4 limestone entrance steps + massive opposite dark-windowed building set.
   - `01`: Exiting warm doors DOWN 4 steps (silent footsteps) -> "噗" bullet chest impact recoil shock & freeze.
   - `02a`: Outdoor street bokeh chest closeup -> 2nd "噗" physical punch -> organic cotton crimson soak + stained 5-finger touch.
   - `02b1`: Over-shoulder rear view looking up at opposite dark multi-windowed facade, dipping head to chest ("哈……还真他妈抬举我。").
   - `02b2`: Same 4 limestone steps -> ~0.44s deadweight knee-buckle gravity crash -> motionless sprawl -> hard cut to black.
"""

import array
import hashlib
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw, ImageFont
from pydub import AudioSegment

V02_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v02_pilot")
V03_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v03_pilot")
V04_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v04_pilot")
V06_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v06_master")
V07_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v07_fixes")
V08_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v08_fixes")
V09_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v09_fixes")
V10_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v10_fixes")
V11_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v11_fixes")
V12_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v12_fixes")
ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v13_fixes")

sys.path.insert(0, str(V06_ROOT))
from v06_patches import (
    apply_clean_crt_turnoff,
    apply_true_peak_limiter,
    darken_11b_midnight_window,
    patch_05_photo_frames,
    remove_10b_right_watch,
)

RIFE_ROOT = V04_ROOT / "rife_v426"
sys.path.insert(0, str(RIFE_ROOT))

AUD_DIR = ROOT / "audio_mix"
LIP_IN_DIR = ROOT / "lipsync_in"
LIP_OUT_DIR = ROOT / "lipsync_out"
V08_LIP_OUT_DIR = V08_ROOT / "lipsync_out"
V07_LIP_OUT_DIR = V07_ROOT / "lipsync_out"
V04_LIP_OUT_DIR = V04_ROOT / "lipsync_out"
SHOT_DIR = ROOT / "shots"
OUT_DIR = ROOT / "out"
STILL_DIR = ROOT / "stills"

SFX_DIR = V02_ROOT / "real_sfx"
V02_AUD_DIR = V02_ROOT / "audio"
V03_AUD_DIR = V03_ROOT / "audio"
V07_AUD_DIR = V07_ROOT / "audio"
V08_AUD_DIR = V08_ROOT / "audio"
V09_AUD_DIR = V09_ROOT / "audio"
V10_AUD_DIR = V10_ROOT / "audio"
V11_AUD_DIR = V12_ROOT / "audio"
V02_CLIP_DIR = V02_ROOT / "clips"
V03_CLIP_DIR = V03_ROOT / "clips"
V07_CLIP_DIR = V07_ROOT / "clips"
V08_CLIP_DIR = V08_ROOT / "clips"
V09_CLIP_DIR = V09_ROOT / "clips"
V10_CLIP_DIR = V10_ROOT / "clips"
V10_SCOUT_DIR = V10_ROOT / "scout_clips"
V11_CLIP_DIR = V11_ROOT / "clips"
V11_SCOUT_DIR = V11_ROOT / "scout_clips"
V12_CLIP_DIR = V12_ROOT / "clips"
V12_SCOUT_DIR = V12_ROOT / "scout_clips"
V13_CLIP_DIR = ROOT / "clips"
V13_SCOUT_DIR = ROOT / "scout_clips"
INS2_STILL_PATH = V03_ROOT / "stills" / "still_05_ins2.png"
MAC_DTMF_DIR = Path("/System/Library/Components/CoreAudio.component/Contents/SharedSupport/SystemSounds/telephony")

for d in (AUD_DIR, LIP_IN_DIR, LIP_OUT_DIR, SHOT_DIR, OUT_DIR, STILL_DIR):
    d.mkdir(parents=True, exist_ok=True)

VIDEO_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频")
PILOT_PREFIX = "第01集_开篇试片"


def get_next_version_mp4(
    video_dir: Path = VIDEO_ROOT,
    title_prefix: str = PILOT_PREFIX,
    min_minor: int = 13,
) -> Path:
    """Return the next unused `_v0.<minor>.mp4` path so every revision saves a new file."""
    pat = re.compile(rf"^{re.escape(title_prefix)}_v0\.(\d+)\.mp4$")
    max_minor = min_minor - 1
    if video_dir.exists():
        for entry in video_dir.iterdir():
            m = pat.match(entry.name)
            if m:
                max_minor = max(max_minor, int(m.group(1)))
    minor = max(min_minor, max_minor + 1)
    while (video_dir / f"{title_prefix}_v0.{minor}.mp4").exists():
        minor += 1
    return video_dir / f"{title_prefix}_v0.{minor}.mp4"

W, H = 1280, 720
FPS_FINAL = 30
FPS_LIPSYNC = 25
SR = 48000


# ==============================================================================
# RIFE v4.26 HD Arbitrary-Timestep Optical Flow Engine
# ==============================================================================
class RifeEngine:
    def __init__(self):
        from train_log.IFNet_HDv3 import IFNet

        if torch.cuda.is_available():
            self.dev = torch.device("cuda")
        elif torch.backends.mps.is_available():
            self.dev = torch.device("mps")
        else:
            self.dev = torch.device("cpu")

        self.net = IFNet().to(self.dev).eval()
        sd = torch.load(RIFE_ROOT / "train_log" / "flownet.pkl", map_location="cpu", weights_only=False)
        sd = {k.replace("module.", ""): v for k, v in sd.items()}
        self.net.load_state_dict(sd, strict=False)
        self.ph = ((H - 1) // 64 + 1) * 64  # 768
        self.pw = ((W - 1) // 64 + 1) * 64  # 1280
        self.pad = (0, self.pw - W, 0, self.ph - H)
        print(f"[RIFE v4.26] Initialized on device={self.dev}")

    def _to_padded_tensor(self, rgb_bytes: bytes) -> torch.Tensor:
        arr = np.frombuffer(rgb_bytes, dtype=np.uint8).reshape((H, W, 3))
        t = torch.from_numpy(arr.copy()).to(self.dev, dtype=torch.float32).permute(2, 0, 1).unsqueeze(0) / 255.0
        return F.pad(t, self.pad, mode="replicate")

    @torch.no_grad()
    def render_positions(self, raw_frames: list[bytes], positions: list[float]) -> list[np.ndarray]:
        """Synthesize smooth optical-flow RGB frames (H, W, 3) uint8 at arbitrary float positions."""
        n_src = len(raw_frames)
        tensor_cache: dict[int, torch.Tensor] = {}

        def get_t(idx: int) -> torch.Tensor:
            if idx not in tensor_cache:
                # Keep cache bounded so unified memory stays tiny
                if len(tensor_cache) > 8:
                    oldest = next(iter(tensor_cache))
                    del tensor_cache[oldest]
                tensor_cache[idx] = self._to_padded_tensor(raw_frames[idx])
            return tensor_cache[idx]

        out: list[np.ndarray] = []
        for pos in positions:
            pos_c = max(0.0, min(float(n_src - 1), float(pos)))
            idx_lo = int(math.floor(pos_c))
            idx_hi = min(n_src - 1, idx_lo + 1)
            frac = pos_c - idx_lo

            if idx_lo == idx_hi or frac <= 0.015:
                arr = np.frombuffer(raw_frames[idx_lo], dtype=np.uint8).reshape((H, W, 3)).copy()
                out.append(arr)
            elif frac >= 0.985:
                arr = np.frombuffer(raw_frames[idx_hi], dtype=np.uint8).reshape((H, W, 3)).copy()
                out.append(arr)
            else:
                t0 = get_t(idx_lo)
                t1 = get_t(idx_hi)
                _, _, merged = self.net(torch.cat((t0, t1), dim=1), float(frac), [16, 8, 4, 2, 1])
                pred = (merged[4][0, :, :H, :W].clamp(0.0, 1.0) * 255.0).to(torch.uint8).permute(1, 2, 0).cpu().numpy()
                out.append(pred)
        return out


_RIFE_SINGLETON: RifeEngine | None = None


def get_rife() -> RifeEngine:
    global _RIFE_SINGLETON
    if _RIFE_SINGLETON is None:
        _RIFE_SINGLETON = RifeEngine()
    return _RIFE_SINGLETON


def eval_curve(t: float, curve: list[tuple[float, float]]) -> float:
    """Piecewise linear time -> source-frame-index curve."""
    if t <= curve[0][0]:
        return curve[0][1]
    if t >= curve[-1][0]:
        return curve[-1][1]
    for i in range(len(curve) - 1):
        t0, f0 = curve[i]
        t1, f1 = curve[i + 1]
        if t0 <= t <= t1:
            if abs(t1 - t0) < 1e-6:
                return f1
            u = (t - t0) / (t1 - t0)
            return f0 + u * (f1 - f0)
    return curve[-1][1]


def decode_video_frames(mp4_path: Path) -> list[bytes]:
    cmd = [
        "ffmpeg", "-v", "error", "-i", str(mp4_path),
        "-vf", f"scale={W}:{H}:flags=lanczos",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ]
    raw = subprocess.check_output(cmd)
    frame_sz = W * H * 3
    return [raw[i : i + frame_sz] for i in range(0, len(raw) - frame_sz + 1, frame_sz)]


def encode_mp4_no_audio(frames_rgb: list[np.ndarray], out_mp4: Path, fps: int):
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
        "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-pix_fmt", "yuv420p",
        str(out_mp4),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for arr in frames_rgb:
        proc.stdin.write(arr.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg encode failed for {out_mp4}")


# ==============================================================================
# Audio Mixing & Frame-Locked Cinema Foley
# ==============================================================================
def ffmpeg_af(seg: AudioSegment, af: str) -> AudioSegment:
    raw_in = seg.set_frame_rate(SR).set_channels(1).set_sample_width(2).raw_data
    cmd = [
        "ffmpeg", "-v", "error",
        "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-",
        "-af", af,
        "-f", "s16le", "-ar", str(SR), "-ac", "1", "-",
    ]
    out_raw = subprocess.check_output(cmd, input=raw_in)
    return AudioSegment(out_raw, frame_rate=SR, sample_width=2, channels=1)


def pcm_to_seg(samples: list[float]) -> AudioSegment:
    arr = array.array("h", (max(-32767, min(32767, int(x * 32767.0))) for x in samples))
    return AudioSegment(arr.tobytes(), frame_rate=SR, sample_width=2, channels=1)


_SFX_CACHE: dict[str, AudioSegment] = {}


def load_real_wav(fname: str) -> AudioSegment:
    if fname not in _SFX_CACHE:
        _SFX_CACHE[fname] = AudioSegment.from_file(SFX_DIR / fname).set_frame_rate(SR).set_channels(1).set_sample_width(2)
    return _SFX_CACHE[fname]


def load_voice_mp3(fname: str) -> AudioSegment:
    for d in (V10_AUD_DIR, V09_AUD_DIR, V08_AUD_DIR, V07_AUD_DIR, V03_AUD_DIR, V02_AUD_DIR):
        cand = d / fname
        if cand.exists():
            return AudioSegment.from_file(cand).set_frame_rate(SR).set_channels(1).set_sample_width(2)
    raise FileNotFoundError(f"Missing voice file: {fname}")


def make_pstn_line_hiss(dur_ms: int, level_dbfs: float = -45.0) -> AudioSegment:
    rng = random.Random(19910824)
    n = int(SR * dur_ms / 1000.0)
    pi2 = 2.0 * math.pi
    buf = [0.02 * rng.gauss(0, 1) + 0.004 * math.sin(pi2 * 120.0 * (k / SR)) for k in range(n)]
    seg = ffmpeg_af(pcm_to_seg(buf), "highpass=f=380:poles=2,lowpass=f=2800:poles=2")
    return seg.apply_gain(level_dbfs - seg.dBFS) if seg.dBFS > -80 else seg


def apply_telephone_earpiece(seg: AudioSegment, target_dbfs: float, gentle: bool = False) -> AudioSegment:
    if gentle:
        af = (
            "highpass=f=185:poles=1,"
            "lowpass=f=4500:poles=1,"
            "equalizer=f=920:t=q:w=2.2:g=1.2,"
            "acompressor=threshold=-20dB:ratio=2.0:attack=10:release=90"
        )
        hiss_lvl = -47.5
    else:
        af = (
            "highpass=f=310:poles=2,"
            "lowpass=f=3200:poles=2,"
            "equalizer=f=1080:t=q:w=1.5:g=3.2,"
            "equalizer=f=2050:t=q:w=1.8:g=1.8,"
            "acompressor=threshold=-22dB:ratio=3.0:attack=5:release=60"
        )
        hiss_lvl = -45.5
    filtered = ffmpeg_af(seg, af)
    if filtered.dBFS > -60:
        gain = min(target_dbfs - filtered.dBFS, -1.5 - filtered.max_dBFS)
        filtered = filtered.apply_gain(gain)
    return make_pstn_line_hiss(len(filtered), level_dbfs=hiss_lvl).overlay(filtered)


def norm_voice(seg: AudioSegment, target_dbfs: float) -> AudioSegment:
    if seg.dBFS <= -60:
        return seg
    gain_needed = target_dbfs - seg.dBFS
    max_safe = -1.2 - seg.max_dBFS
    return seg.apply_gain(min(gain_needed, max_safe + 2.5))


def build_footstep_hits_v8(total_ms: int, step_times_ms: tuple[int, ...]) -> AudioSegment:
    """Place distinct clean outdoor damp stone-pavement sneaker steps 1-to-1 at visual foot-plant times."""
    src = load_real_wav("footsteps_2.wav")
    wet_src = load_real_wav("rain_07.wav")
    cloth_src = load_real_wav("cloth_1.wav")
    # Clean individual sole strikes (peak attack ~35ms after slice start, single transient per slice)
    slices = [
        src[240:440],
        src[805:1005],
        src[1345:1545],
        src[3030:3210],
        src[3610:3790],
    ]
    out = AudioSegment.silent(total_ms, frame_rate=SR)
    for idx, plant_ms in enumerate(step_times_ms):
        sl = slices[idx % len(slices)].fade_in(4).fade_out(55)
        # Outdoor stone-pavement sneaker timbre: cut muddy <110Hz indoor resonance, preserve rubber tread grip
        sole = ffmpeg_af(
            sl,
            "highpass=f=110:poles=2,lowpass=f=3600:poles=2,"
            "equalizer=f=380:t=q:w=1.4:g=-2.5,equalizer=f=1450:t=q:w=1.6:g=1.8,"
            "aecho=0.88:0.74:34:0.05",
        )
        target_db = -19.5 - (0.8 if idx % 2 == 1 else 0.0)
        sole = sole.apply_gain(target_db - sole.max_dBFS if sole.max_dBFS > -60 else 0.0)

        scuff = wet_src[420 + idx * 170 : 495 + idx * 170].fade_in(5).fade_out(35)
        scuff = ffmpeg_af(scuff, "highpass=f=480:poles=2,lowpass=f=2400:poles=2")
        scuff = scuff.apply_gain(-30.5 - scuff.max_dBFS if scuff.max_dBFS > -60 else 0.0)

        swish = cloth_src[1500 + idx * 130 : 1620 + idx * 130].fade_in(16).fade_out(45)
        swish = ffmpeg_af(swish, "highpass=f=260:poles=2,lowpass=f=2100:poles=2")
        swish = swish.apply_gain(-33.5 - swish.max_dBFS if swish.max_dBFS > -60 else 0.0)

        pos_sole = max(0, plant_ms - 34)
        out = out.overlay(sole, position=pos_sole)
        out = out.overlay(scuff, position=pos_sole + 6)
        out = out.overlay(swish, position=max(0, pos_sole - 12))
    return out


def _build_suppressed_thump(first_shot: bool, muffled: bool = False) -> AudioSegment:
    """Layer distant suppressed air puff + tight sub-bass chest thud + cotton snap."""
    supp_raw = load_real_wav("sniper_supp.wav")
    whip = supp_raw[555:835] if first_shot else supp_raw[3330:3530]
    whip_af = "highpass=f=160:poles=2,lowpass=f=1850:poles=2" if muffled else "highpass=f=180:poles=2,lowpass=f=4200:poles=2"
    whip = ffmpeg_af(whip.fade_in(2).fade_out(70), whip_af)
    whip = whip.apply_gain((-14.5 if muffled else -5.5) - whip.max_dBFS)

    in_supp = load_real_wav("indoor_supp.wav")
    pffft = in_supp[1745:2010] if first_shot else in_supp[3540:3760]
    pffft_af = "highpass=f=110:poles=2,lowpass=f=1450:poles=2" if muffled else "highpass=f=130:poles=2,lowpass=f=2400:poles=2"
    pffft = ffmpeg_af(pffft.fade_in(2).fade_out(65), pffft_af)
    pffft = pffft.apply_gain((-5.8 if muffled else -7.2) - pffft.max_dBFS)

    # Ultra-short sub-bass chest thump ONLY (<190Hz, zero wooden box formant!)
    flesh_punch = load_real_wav("wood_thud.wav")[540:635].fade_in(2).fade_out(70)
    flesh_punch = ffmpeg_af(flesh_punch, "highpass=f=46:poles=1,lowpass=f=185:poles=2")
    flesh_punch = flesh_punch.apply_gain((-4.5 if muffled else -5.0) - flesh_punch.max_dBFS)

    cloth_rip = load_real_wav("cloth_1.wav")[1520:1700].fade_in(3).fade_out(60)
    cloth_rip = ffmpeg_af(cloth_rip, "highpass=f=360:poles=2,lowpass=f=2600:poles=2")
    cloth_rip = cloth_rip.apply_gain(-8.5 - cloth_rip.max_dBFS)

    out = AudioSegment.silent(340 if muffled else 390, frame_rate=SR)
    out = (
        out.overlay(whip, position=0)
        .overlay(pffft, position=3)
        .overlay(flesh_punch, position=8)
        .overlay(cloth_rip, position=10)
    )
    return ffmpeg_af(out, "alimiter=limit=0.90:attack=1:release=30")


def synth_sfx(name: str) -> AudioSegment:
    if name in ("thump_1", "thump_2"):
        return _build_suppressed_thump(first_shot=(name == "thump_1"), muffled=False)

    if name in ("thump_1_v9", "thump_2_v9"):
        return _build_suppressed_thump(first_shot=(name == "thump_1_v9"), muffled=True)

    if name == "fall_fast_v9":
        # Tight ~0.46s gravity drop: knee buckle cloth/scuff at 0ms -> realistic stone+cloth deadweight slam at 250ms (no resonant bass drum!)
        scuff = ffmpeg_af(load_real_wav("footsteps_2.wav")[1895:2035].fade_in(4).fade_out(55), "highpass=f=220:poles=2,lowpass=f=2800:poles=2")
        scuff = scuff.apply_gain(-15.5 - scuff.max_dBFS)
        cloth_drop = ffmpeg_af(load_real_wav("cloth_1.wav")[1480:1820].fade_in(6).fade_out(80), "highpass=f=200:poles=2,lowpass=f=2600:poles=2")
        cloth_drop = cloth_drop.apply_gain(-11.0 - cloth_drop.max_dBFS)

        torso_sub = ffmpeg_af(load_real_wav("wood_thud.wav")[542:605].fade_in(3).fade_out(45), "highpass=f=50,lowpass=f=150:poles=2")
        torso_sub = torso_sub.apply_gain(-11.0 - torso_sub.max_dBFS)
        torso_grit = ffmpeg_af(load_real_wav("footsteps_2.wav")[805:965].fade_in(4).fade_out(65), "highpass=f=240:poles=2,lowpass=f=2200:poles=2")
        torso_grit = torso_grit.apply_gain(-8.5 - torso_grit.max_dBFS)
        torso_slump = ffmpeg_af(load_real_wav("footsteps_2.wav")[3035:3165].fade_in(5).fade_out(70), "highpass=f=140:poles=2,lowpass=f=1100:poles=2")
        torso_slump = torso_slump.apply_gain(-9.5 - torso_slump.max_dBFS)
        torso_cloth = ffmpeg_af(load_real_wav("cloth_2.wav")[200:520].fade_in(6).fade_out(90), "highpass=f=240:poles=2,lowpass=f=3200:poles=2")
        torso_cloth = torso_cloth.apply_gain(-10.5 - torso_cloth.max_dBFS)

        out = AudioSegment.silent(560, frame_rate=SR)
        out = (
            out.overlay(scuff, position=0)
            .overlay(cloth_drop, position=15)
            .overlay(torso_sub, position=250)
            .overlay(torso_grit, position=252)
            .overlay(torso_slump, position=254)
            .overlay(torso_cloth, position=256)
        )
        return out.fade_out(65)

    if name == "fall_stone_v8":
        # 0ms (1.72s): sneaker skid/scuff on wet stone
        # 140ms (1.86s, f35): knees drop onto wet stone steps (stone scuff + deep damped <190Hz knee weight)
        # 620ms (2.34s, f54): heavy sweatshirt torso + forearms collapse onto upper stone step (cloth slumping + dull stone thump)
        scuff = ffmpeg_af(load_real_wav("footsteps_2.wav")[1890:2110].fade_in(5).fade_out(70), "highpass=f=160:poles=2,lowpass=f=3200:poles=2")
        scuff = scuff.apply_gain(-13.5 - scuff.max_dBFS)

        knee_sub = ffmpeg_af(load_real_wav("wood_thud.wav")[542:625].fade_in(4).fade_out(65), "highpass=f=45,lowpass=f=185:poles=2")
        knee_sub = knee_sub.apply_gain(-10.0 - knee_sub.max_dBFS)
        knee_stone = ffmpeg_af(load_real_wav("footsteps_2.wav")[805:965].fade_in(4).fade_out(70), "highpass=f=220:poles=2,lowpass=f=1400:poles=2")
        knee_stone = knee_stone.apply_gain(-13.5 - knee_stone.max_dBFS)

        torso_sub = ffmpeg_af(load_real_wav("wood_thud.wav")[538:640].fade_in(6).fade_out(85), "highpass=f=42,lowpass=f=155:poles=2")
        torso_sub = torso_sub.apply_gain(-7.5 - torso_sub.max_dBFS)
        torso_slump = ffmpeg_af(load_real_wav("footsteps_2.wav")[3030:3200].fade_in(10).fade_out(95), "highpass=f=120:poles=2,lowpass=f=750:poles=2")
        torso_slump = torso_slump.apply_gain(-13.0 - torso_slump.max_dBFS)
        cloth = ffmpeg_af(load_real_wav("cloth_1.wav")[1480:2220].fade_in(15).fade_out(120), "highpass=f=180:poles=2,lowpass=f=2200:poles=2")
        cloth = cloth.apply_gain(-15.0 - cloth.max_dBFS)

        out = AudioSegment.silent(1080, frame_rate=SR)
        out = (
            out.overlay(scuff, position=0)
            .overlay(knee_sub, position=140)
            .overlay(knee_stone, position=142)
            .overlay(cloth, position=150)
            .overlay(torso_sub, position=620)
            .overlay(torso_slump, position=625)
        )
        return out.fade_out(90)

    if name == "phone_moscow_jcut":
        ring1 = load_real_wav("ring_01b.wav")[0:1280].fade_out(80)
        ring2 = load_real_wav("ring_01b.wav")[0:1050].fade_out(40)
        ext_seq = ring1 + AudioSegment.silent(760, frame_rate=SR) + ring2
        ext_muf = ffmpeg_af(ext_seq, "highpass=f=280:poles=2,lowpass=f=1350:poles=2,aecho=0.8:0.78:48|96:0.22|0.10")
        ext_muf = ext_muf.apply_gain(-15.5 - ext_muf.max_dBFS)
        pick = load_real_wav("phone_pickup_1.wav")[90:520].fade_in(8).fade_out(45)
        pick = pick.apply_gain(-6.5 - pick.max_dBFS)
        out = AudioSegment.silent(len(ext_muf) + 460, frame_rate=SR)
        out = out.overlay(ext_muf, position=0).overlay(pick, position=len(ext_muf) - 30)
        return out

    if name == "hook":
        hk = load_real_wav("phone_hook_btn.wav")[0:420].fade_out(50)
        return hk.apply_gain(-5.5 - hk.max_dBFS)

    if name == "tv_off":
        sw = load_real_wav("switch_1.wav")[15:280].fade_out(40)
        return sw.apply_gain(-5.5 - sw.max_dBFS)

    if name == "dtmf_ny":
        digits = ["8", "1", "0", "1", "2", "1", "2", "5", "8"]
        kbd = load_real_wav("kbd_1.wav")
        key_slices = [
            kbd[35:145], kbd[235:345], kbd[485:595], kbd[635:745],
            kbd[935:1045], kbd[1135:1245], kbd[235:345], kbd[635:745], kbd[485:595],
        ]
        gaps_ms = [165, 220, 180, 240, 160, 155, 185, 165, 135]
        out = AudioSegment.silent(0, frame_rate=SR)
        for d, ks, g_ms in zip(digits, key_slices, gaps_ms):
            click = ks.fade_in(4).fade_out(25).apply_gain(-10.5 - ks.max_dBFS)
            caf_p = MAC_DTMF_DIR / f"dtmf-{d}.caf"
            if caf_p.exists():
                tone = AudioSegment.from_file(caf_p).set_frame_rate(SR).set_channels(1)[:100].fade_in(8).fade_out(14)
                tone = ffmpeg_af(tone, "highpass=f=480:poles=2,lowpass=f=2600:poles=2")
                tone = tone.apply_gain(-21.5 - tone.max_dBFS)
                step_seg = AudioSegment.silent(max(len(click), len(tone) + 12), frame_rate=SR).overlay(click, position=0).overlay(tone, position=10)
            else:
                step_seg = click
            out += step_seg + AudioSegment.silent(max(45, g_ms - len(step_seg)), frame_rate=SR)
        return out

    if name == "ringback_us":
        rb = load_real_wav("phone_calling_1b.wav")[0:3050].fade_in(25).fade_out(60)
        return rb.apply_gain(-13.5 - rb.max_dBFS)

    if name == "ny_ring_pickup":
        # Ring 0..1120ms, physical cradle release clack right at 1120ms!
        ny_ring = load_real_wav("ring_04.wav")[0:1120].fade_out(20)
        ny_ring = ny_ring.apply_gain(-9.5 - ny_ring.max_dBFS)
        pick = load_real_wav("phone_pickup_2.wav")[40:480].fade_in(6).fade_out(50)
        pick = pick.apply_gain(-6.5 - pick.max_dBFS)
        out = AudioSegment.silent(1620, frame_rate=SR)
        return out.overlay(ny_ring, position=0).overlay(pick, position=1120)

    if name == "hook_soft":
        gentle = load_real_wav("phone_hangup_2a.wav")[20:620].fade_in(10).fade_out(90)
        return gentle.apply_gain(-11.0 - gentle.max_dBFS)

    if name == "revolver_load_synced":
        # Synced to clip_10a_v7 (5-finger hand sliding bullet smoothly f15..f65 -> flush chamber seat f68..f72):
        #   0.38s..1.45s: brass cartridge sliding into open chamber (f15->f65)
        #   1.65s..1.98s: subtle mechanical seat & latch click as bullet rests flush (f68..f72)
        ins1 = load_real_wav("rev_insert.wav")[6640:7420].fade_in(16).fade_out(65)
        ins1 = ins1.apply_gain(-13.0 - ins1.max_dBFS)
        seat_click = load_real_wav("rev_spin_cyl.wav")[540:860].fade_in(8).fade_out(65)
        seat_click = seat_click.apply_gain(-11.0 - seat_click.max_dBFS)
        out = AudioSegment.silent(2250, frame_rate=SR)
        return out.overlay(ins1, position=400).overlay(seat_click, position=1650)

    if name == "pen_two_lines":
        # Continuous fountain-pen nib writing from 0.12s to 3.80s (stops right when nib lifts at f52!)
        raw_p = load_real_wav("writing_sig.wav")
        s1 = raw_p[35:1180].fade_in(15).fade_out(40)
        s2 = raw_p[140:1290].fade_in(25).fade_out(40)
        s3 = raw_p[60:1060].fade_in(20).fade_out(70)
        s1 = s1.apply_gain(-16.5 - s1.max_dBFS)
        s2 = s2.apply_gain(-17.0 - s2.max_dBFS)
        s3 = s3.apply_gain(-17.5 - s3.max_dBFS)
        out = AudioSegment.silent(3900, frame_rate=SR)
        return out.overlay(s1, position=120).overlay(s2, position=1420).overlay(s3, position=2760)

    if name == "gunshot_revolver":
        g1 = load_real_wav("cinema_gun_1.wav").fade_out(180)
        g2 = load_real_wav("cinema_gun_2.wav").apply_gain(-3.0).fade_out(180)
        rev_crack = load_real_wav("rev_shot_prep.wav")[780:1900].apply_gain(4.5).fade_out(200)
        raw_blast = g1.overlay(g2, position=4).overlay(rev_crack, position=0)
        indoor_blast = ffmpeg_af(
            raw_blast,
            "aecho=0.88:0.84:21|49|98|175:0.30|0.19|0.11|0.05,"
            "equalizer=f=95:t=q:w=1.0:g=3.0,"
            "alimiter=limit=0.95:attack=1:release=45",
        )
        desk_slump = ffmpeg_af(load_real_wav("wood_thud.wav")[475:1180], "lowpass=f=720:poles=2").apply_gain(-4.0)
        desk_rattle = load_real_wav("wood_knock.wav")[40:250].fade_out(70).apply_gain(-13.5)
        cloth_slump = load_real_wav("cloth_1.wav")[1480:2200].apply_gain(3.5)
        out = AudioSegment.silent(2150, frame_rate=SR)
        return out.overlay(indoor_blast, position=0).overlay(desk_slump, position=720).overlay(desk_rattle, position=745).overlay(cloth_slump, position=730).fade_out(160)

    if name in ("drip_seq_synced", "drip_single"):
        rain_splash = load_real_wav("rain_07.wav")
        pi2 = 2.0 * math.pi

        def make_blood_drop(seed_off: int, pk_db: float) -> AudioSegment:
            sp = rain_splash[300 + seed_off : 338 + seed_off].fade_in(2).fade_out(18)
            sp = ffmpeg_af(sp, "highpass=f=900:poles=2,lowpass=f=4200:poles=2")
            sp = sp.apply_gain((pk_db - 4.0) - sp.max_dBFS)
            n = int(SR * 0.036)
            f0 = 460.0 + (seed_off % 37)
            buf = [0.45 * math.sin(pi2 * (f0 + 115.0 * (k / n)) * (k / SR)) * math.exp(-(k / SR) * 115.0) for k in range(n)]
            plink = pcm_to_seg(buf).apply_gain(pk_db - pcm_to_seg(buf).max_dBFS)
            drop = AudioSegment.silent(180, frame_rate=SR).overlay(sp, position=0).overlay(plink, position=3)
            return ffmpeg_af(drop, "aecho=0.8:0.75:26:0.14")

        if name == "drip_single":
            return make_blood_drop(15, -21.0) + AudioSegment.silent(360, frame_rate=SR)
        # Exact frame-locked impacts for clip_12b_v3 over 3.85s (f14=0.68s, f40=1.95s, f74=3.61s)
        out = AudioSegment.silent(3850, frame_rate=SR)
        for pos_ms, s_off, pk_db in ((680, 0, -18.0), (1950, 120, -19.5), (3610, 260, -21.0)):
            out = out.overlay(make_blood_drop(s_off, pk_db), position=pos_ms)
        return out

    raise ValueError(f"Unknown sfx: {name}")


def make_ambience(kind: str, dur_ms: int) -> AudioSegment:
    if kind == "silence":
        return AudioSegment.silent(dur_ms, frame_rate=SR)
    if kind == "moscow_street":
        raw_air = load_real_wav("rain_07.wav")
        loops = raw_air * (dur_ms // len(raw_air) + 2)
        bed = ffmpeg_af(loops[:dur_ms], "highpass=f=65,lowpass=f=420:poles=2")
        return bed.apply_gain(-35.0 - bed.dBFS)
    n = int(SR * dur_ms / 1000.0)
    rng = random.Random(hash(kind) & 0xFFFF)
    lvl = {
        "paris_night": 0.016,
        "moscow_room": 0.010,
        "moscow_dead_quiet": 0.003,
        "moscow_aftermath": 0.00055,
        "ny_day_room": 0.007,
    }.get(kind, 0.008)
    buf = []
    acc = 0.0
    pi2 = 2.0 * math.pi
    for k in range(n):
        acc = 0.985 * acc + 0.015 * rng.gauss(0, 1)
        val = acc * lvl * 3.0
        if kind == "moscow_room":
            val += 0.003 * math.sin(pi2 * 50.0 * (k / SR))
        buf.append(val)
    return pcm_to_seg(buf)


def find_split_silence_ms(seg: AudioSegment, approx_ratio: float = 0.45, search_ms: int = 1200) -> int:
    center = int(len(seg) * approx_ratio)
    lo = max(400, center - search_ms)
    hi = min(len(seg) - 400, center + search_ms)
    best_ms = center
    best_db = 999.0
    for ms in range(lo, hi, 40):
        db = seg[ms : ms + 80].dBFS
        if db < best_db:
            best_db = db
            best_ms = ms
    return best_ms


# ==============================================================================
# Stage 1: Prepare Audio Mix, Curves & 25fps LatentSync Bundle for 05a & 05c
# ==============================================================================
def prepare_v10():
    tv_bed = ffmpeg_af(
        load_voice_mp3("tv_gorbachev_19910824.mp3"),
        "highpass=f=380:poles=2,lowpass=f=3100:poles=2,equalizer=f=1250:t=q:w=1.5:g=3.0",
    ) - 18.5
    tv_cursor_ms = 0

    def add_tv(bed: AudioSegment, cutoff_ms: int = None, boost_db: float = 0.0) -> AudioSegment:
        nonlocal tv_cursor_ms
        total_ms = len(bed)
        need = cutoff_ms if cutoff_ms is not None else total_ms
        loops = tv_bed * ((tv_cursor_ms + need) // len(tv_bed) + 2)
        sl = loops[tv_cursor_ms : tv_cursor_ms + need]
        if boost_db != 0.0:
            sl = sl.apply_gain(boost_db)
        tv_cursor_ms = (tv_cursor_ms + need) % len(tv_bed)
        if cutoff_ms is not None:
            return bed[:cutoff_ms].overlay(sl) + make_ambience("moscow_dead_quiet", total_ms - cutoff_ms)
        return bed.overlay(sl)

    ye_line = norm_voice(load_voice_mp3("line_02_3.mp3"), -17.0)
    luo_05a = norm_voice(load_voice_mp3("line_05a_1.mp3"), -17.0)
    kug_1 = apply_telephone_earpiece(load_voice_mp3("line_05a_2.mp3"), -18.8, gentle=False)
    kug_2 = apply_telephone_earpiece(load_voice_mp3("line_05b_0.mp3"), -18.8, gentle=False)
    luo_05c = norm_voice(load_voice_mp3("line_05b_2.mp3"), -17.0)
    luo_06 = norm_voice(load_voice_mp3("line_06_1.mp3"), -17.0)
    su_full = load_voice_mp3("su_continuous_2.mp3")
    su_08 = norm_voice(su_full[:2420].fade_out(60), -17.3)
    su_09 = apply_telephone_earpiece(su_full[2780:].fade_in(30).fade_out(90), -17.6, gentle=True)
    luo_10 = norm_voice(load_voice_mp3("line_10_4.mp3"), -18.0)
    luo_11 = norm_voice(load_voice_mp3("line_11_1.mp3"), -18.0)

    k1_split = find_split_silence_ms(kug_1, 0.56, 800)
    kug_1a, kug_1b = kug_1[:k1_split], kug_1[k1_split:]

    k2_split = find_split_silence_ms(kug_2, 0.70, 800)
    kug_2a, kug_2b = kug_2[:k2_split], kug_2[k2_split:]

    l10_split = find_split_silence_ms(luo_10, 0.30, 900)
    luo_10a, luo_10b = luo_10[:l10_split], luo_10[l10_split:]

    l11_split = find_split_silence_ms(luo_11, 0.50, 1200)
    luo_11a, luo_11b = luo_11[:l11_split], luo_11[l11_split:]

    shots_spec = []
    stems_to_export: dict[str, tuple[AudioSegment, float]] = {}

    def reg(
        sid: str,
        clip_src: str,
        kind: str,
        fg: AudioSegment,
        amb: str,
        subs: list,
        curve: list[tuple[float, float]] | None = None,
        tv: bool = False,
        tv_boost_db: float = 0.0,
        tv_cut_ms: int | None = None,
        fade_in: bool = False,
        fade_out: bool = False,
        crt_off_ms: int | None = None,
        jolt_ms: int | None = None,
        gunflash_ms: int | None = None,
        zoom_pct: float = 0.0,
        lipsync_dur_sec: float | None = None,
        speaker_stem: AudioSegment | None = None,
        card_lines: list[str] | None = None,
        chain_hit: dict | None = None,
    ):
        total_ms = len(fg)
        dur_sec = round(total_ms / 1000.0, 3)
        bed = make_ambience(amb, total_ms)
        if tv:
            bed = add_tv(bed, cutoff_ms=tv_cut_ms, boost_db=tv_boost_db)
        mixed = apply_true_peak_limiter(bed.overlay(fg), ceiling_db=-1.5)
        if sid == "13":
            mixed = mixed.fade_out(300)
        mixed.export(AUD_DIR / f"shot_{sid}.wav", format="wav")

        if lipsync_dur_sec is not None and speaker_stem is not None:
            stems_to_export[sid] = (speaker_stem, lipsync_dur_sec)

        entry = {
            "id": sid,
            "clip": clip_src,
            "kind": kind,
            "dur": dur_sec,
            "subs": subs,
            "curve": curve,
            "fade_in": fade_in,
            "fade_out": fade_out,
            "crt_off_ms": crt_off_ms,
            "jolt_ms": jolt_ms,
            "gunflash_ms": gunflash_ms,
            "zoom_pct": zoom_pct,
            "lipsync_dur_sec": lipsync_dur_sec,
            "card_lines": card_lines,
        }
        if chain_hit is not None:
            entry["chain_hit"] = chain_hit
        shots_spec.append(entry)
        print(f"[audio v0.11] shot_{sid:8s} dur={dur_sec:5.2f}s  max={mixed.max_dBFS:5.2f}  clip={clip_src}")

    # --- 1-1 Paris Cold Open (v0.13 physically coherent shot & collapse sequence) ---
    # 01: Exiting golden doorway in 100% sober straight walk (0..1.75s, ZERO footsteps) ->
    #   at 1.75s 1st muffled sniper "噗" hits front upper chest -> abrupt backward shock arrest ("微后仰急顿", 1.75..2.50s)
    fg01 = AudioSegment.silent(2500, frame_rate=SR).overlay(synth_sfx("thump_1_v9"), position=1750)
    d01 = len(fg01) / 1000.0
    reg(
        "01", "v11:clip_01_v11_walk.mp4", "video", fg01, "paris_night", [],
        curve=[(0.0, 0.0), (1.75, 32.0)],
        fade_in=True, jolt_ms=1750,
        chain_hit={
            "clip": "v13:clip_01_v13_hit.mp4",
            "switch_sec": 1.75,
            "tone_lock": "luma_v3",
            "hit_curve": [(1.75, 0.0), (1.92, 8.5), (2.20, 14.0), (d01, 17.5)],
        },
    )

    # 02a: Anchored to v0.4 warm Paris bistro bokeh -> starts with initial 1st-shot blood mark & rising hand (0..0.133s, f0..f2),
    #   then at 0.167s 2nd muffled "噗" impacts clean onto puckering cloth (f10 -> f32) blooming huge ~15cm crimson stain while palm presses directly ON blood
    gasp_02a = ffmpeg_af(ye_line[430:670].fade_in(15).fade_out(40), "highpass=f=180:poles=2,lowpass=f=2800:poles=2")
    gasp_02a = gasp_02a.apply_gain(-23.0 - gasp_02a.max_dBFS)
    fg02a = AudioSegment.silent(2100, frame_rate=SR).overlay(synth_sfx("thump_2_v9"), position=167).overlay(gasp_02a, position=900)
    d02a = len(fg02a) / 1000.0
    reg(
        "02a", "v13:clip_02a_v13.mp4", "video", fg02a, "paris_night", [],
        curve=[(0.0, 0.0), (0.133, 2.0), (0.167, 10.0), (0.48, 15.0), (1.15, 24.0), (d02a, 32.0)],
        jolt_ms=167,
    )

    # 02b1: Night exterior over-shoulder clearly seeing 6-story dense-windowed Parisian building ->
    #   looks up toward windows ("还真他妈抬举我。"), then visibly sags/drops head & shoulders as strength drains
    ye_ha = ye_line[160:370].fade_in(10).fade_out(25)
    ye_rem = ye_line[940:2180].fade_in(15).fade_out(25)
    fg02b1 = AudioSegment.silent(1700, frame_rate=SR).overlay(ye_ha, position=70).overlay(ye_rem, position=420)
    d02b1 = len(fg02b1) / 1000.0
    reg(
        "02b1", "v13:clip_02b1_v13.mp4", "video", fg02b1, "paris_night",
        [(0.40, 0.42 + len(ye_rem) / 1000.0, "还真他妈抬举我。")],
        curve=[(0.0, 0.0), (0.72, 16.0), (1.35, 29.0), (d02b1, 32.0)],
    )

    # 02b2: Halted wounded chest-clutched stance -> instant knees-buckle sideways-forward full-length flat sprawl onto dark pavement (NO squat, NO kowtow, NO steps)
    fg02b2 = AudioSegment.silent(1150, frame_rate=SR).overlay(synth_sfx("fall_fast_v9"), position=430)
    d02b2 = len(fg02b2) / 1000.0
    reg(
        "02b2", "v13:clip_02b2_v13.mp4", "video", fg02b2, "paris_night", [],
        curve=[(0.0, 6.5), (0.16, 10.5), (0.50, 16.5), (d02b2, 24.0)],
    )

    # 03: Time Card
    reg("03", "", "card", AudioSegment.silent(3400, frame_rate=SR), "silence", [], card_lines=["一年前", "1991年8月24日夜　莫斯科"])

    # --- 1-2 Moscow Midnight Street & 12F Office Crisis Call ---
    # 04: Exterior 12F lit window + muffled ring + J-cut snatch
    fg04 = AudioSegment.silent(450, frame_rate=SR) + synth_sfx("phone_moscow_jcut")
    d04 = len(fg04) / 1000.0
    reg("04", "v03:clip_04_v3.mp4", "video", fg04, "moscow_street", [], curve=[(0.0, 0.0), (d04, 80.0)])

    # 05a: Cold stern unsmiling pickup ("我是罗。") -> lip-synced via LatentSync-1.6, zero smirk while listening!
    t_luo_end = (180 + len(luo_05a)) / 1000.0
    t_k1a_s = t_luo_end + 0.18
    fg05a = AudioSegment.silent(180, frame_rate=SR) + luo_05a + AudioSegment.silent(180, frame_rate=SR) + kug_1a + AudioSegment.silent(80, frame_rate=SR)
    d05a = len(fg05a) / 1000.0
    stem05a = AudioSegment.silent(len(fg05a), frame_rate=SR).overlay(luo_05a, position=180)
    reg(
        "05a", "v07:clip_05a_v7.mp4", "video", fg05a, "moscow_room",
        [(0.18, t_luo_end, "我是罗。"), (t_k1a_s, d05a, "（电话）罗！秘密股东协议里的五个高官已经抓了三个！")],
        curve=[(0.0, 0.0), (d05a, 96.0)], tv=True,
        lipsync_dur_sec=d05a, speaker_stem=stem05a,
    )

    # 05_ins1: Overflowing ashtray cutaway (natural 1.1x smoke pace f00->f50)
    fg05_i1 = kug_1b + AudioSegment.silent(140, frame_rate=SR)
    d05_i1 = len(fg05_i1) / 1000.0
    reg(
        "05_ins1", "v03:clip_05_ins1.mp4", "video", fg05_i1, "moscow_room",
        [(0.0, len(kug_1b) / 1000.0, "（电话）另外两个高官公子傍晚跑去瑞士了！")],
        curve=[(0.0, 0.0), (d05_i1, 50.0)], tv=True,
    )

    # 05_ins2: 4-women NY '裕香阁' family photo cutaway (RIFE smooth optical-flow push-in f00->f43)
    fg05_i2 = kug_2a + AudioSegment.silent(60, frame_rate=SR)
    d05_i2 = len(fg05_i2) / 1000.0
    reg(
        "05_ins2", "v03:clip_05_ins2.mp4", "video", fg05_i2, "moscow_room",
        [(0.0, len(kug_2a) / 1000.0, "（电话）美国石油公司刚撤回了那150口油井的收购意向，明天一早检察院就来贴封条！")],
        curve=[(0.0, 0.0), (d05_i2, 43.0)], tv=True,
    )

    # 05c: Fixed cold open-eyed stoic listening (f00..f14 during 0..2.58s, ZERO sleepy eyes or slack open mouth!)
    #   2.83..7.15s: Calm downward gaze f14..f48 while speaking "知道了，库格列夫。明天再说吧。" (LatentSync-1.6)
    #   7.15..7.72s: Lower receiver calmly onto cradle (f48..f88), hook click right at 7.72s!
    t_k2b_end = len(kug_2b) / 1000.0
    t_l05c_s = t_k2b_end + 0.25
    t_l05c_e = t_l05c_s + len(luo_05c) / 1000.0  # ~7.154s
    fg05c = (
        kug_2b
        + AudioSegment.silent(250, frame_rate=SR)
        + luo_05c
        + AudioSegment.silent(570, frame_rate=SR)
        + synth_sfx("hook")
        + AudioSegment.silent(260, frame_rate=SR)
    )
    d05c = len(fg05c) / 1000.0
    t_hook = t_l05c_e + 0.57
    stem05c = AudioSegment.silent(int(round((t_l05c_e + 0.08) * 1000)), frame_rate=SR).overlay(
        luo_05c, position=int(round(t_l05c_s * 1000))
    )
    reg(
        "05c", "v07:clip_05c_v7.mp4", "video", fg05c, "moscow_room",
        [
            (0.0, t_k2b_end, "（电话）罗，我那6万美金口头暗股怎么办？！"),
            (t_l05c_s, t_l05c_e, "知道了，库格列夫。明天再说吧。"),
        ],
        curve=[(0.0, 0.0), (t_k2b_end, 14.0), (t_l05c_e, 48.0), (t_hook, 88.0), (d05c, 95.0)],
        tv=True,
        lipsync_dur_sec=round(t_l05c_e + 0.08, 3),
        speaker_stem=stem05c,
    )

    # --- 1-3 TV Gorbachev Criticism & Shutoff (Kuleshov + 180-deg Eye-Line Match: 06_tv -> 06a -> 06b) ---
    # 06_tv: Direct match cut from 05c telephone hangup -> dark wood-corner CRT TV showing Gorbachev speaking (ZERO hand!)
    fg06_tv = AudioSegment.silent(1900, frame_rate=SR)
    d06_tv = len(fg06_tv) / 1000.0
    reg(
        "06_tv", "v08:clip_06_tv_v8.mp4", "video", fg06_tv, "moscow_room", [],
        curve=[(0.0, 0.0), (d06_tv, 64.0)], tv=True, tv_boost_db=4.0,
    )

    # 06a: Luo on LEFT by midnight window, glowing blue CRT TV edge visible at RIGHT edge -> stares straight right
    #   at screen -> lip-synced "这个笨蛋！" (stops cleanly at f68 before cigarette lift/blink!)
    t_06_lead_ms = 550
    fg06a = AudioSegment.silent(t_06_lead_ms, frame_rate=SR) + luo_06 + AudioSegment.silent(450, frame_rate=SR)
    d06a = len(fg06a) / 1000.0
    stem06a = AudioSegment.silent(len(fg06a), frame_rate=SR).overlay(luo_06, position=t_06_lead_ms)
    reg(
        "06a", "v08:clip_06a_v8.mp4", "video", fg06a, "moscow_room",
        [(0.66, 1.66, "这个笨蛋！")],
        curve=[(0.0, 0.0), (d06a, 68.0)], tv=True,
        lipsync_dur_sec=d06a, speaker_stem=stem06a,
    )

    # 06b: Immediate reverse match cut back to exact CRT TV -> white-cuffed hand clicks power off at 0.95s (f26) -> black glass & dead silence!
    tv_click_ms = 950
    fg06b = AudioSegment.silent(tv_click_ms, frame_rate=SR) + synth_sfx("tv_off") + AudioSegment.silent(950, frame_rate=SR)
    d06b = len(fg06b) / 1000.0
    reg(
        "06b", "v03:clip_06b_v3.mp4", "video", fg06b, "moscow_room", [],
        curve=[(0.0, 2.0), (0.95, 26.0), (d06b, 45.0)],
        tv=True, tv_boost_db=3.5, tv_cut_ms=tv_click_ms + 45, crt_off_ms=tv_click_ms + 45,
    )

    # 07: Dialing NY (0.18..2.01s -> f00..f50) -> lifting receiver to ear (2.01..2.85s -> f50..f72) -> US ringback (2.85..5.90s -> f72..f96)
    dtmf_seg = synth_sfx("dtmf_ny")  # ~1830ms
    rb_seg = synth_sfx("ringback_us")  # 3050ms
    fg07 = AudioSegment.silent(180, frame_rate=SR) + dtmf_seg + AudioSegment.silent(840, frame_rate=SR) + rb_seg + AudioSegment.silent(150, frame_rate=SR)
    d07 = len(fg07) / 1000.0
    t_dial_end = (180 + len(dtmf_seg)) / 1000.0
    t_ear = t_dial_end + 0.84
    reg(
        "07", "v03:clip_07_v3.mp4", "video", fg07, "moscow_dead_quiet", [],
        curve=[(0.0, 0.0), (t_dial_end, 50.0), (t_ear, 72.0), (d07, 96.0)],
    )

    # 08a: Sunny NY side table -> rings 0.08..1.20s (f27..f39) -> pickup clack right at 1.20s (f39) -> lifts receiver (f39..f58)
    fg08a = AudioSegment.silent(80, frame_rate=SR) + synth_sfx("ny_ring_pickup") + AudioSegment.silent(350, frame_rate=SR)
    d08a = len(fg08a) / 1000.0
    reg(
        "08a", "v03:clip_08a_v3.mp4", "video", fg08a, "ny_day_room", [],
        curve=[(0.0, 27.0), (1.20, 39.0), (d08a, 58.0)],
    )

    # 08b: Su Yuping smiling warmly -> lip-synced "喂？是家明吗？"
    fg08b = AudioSegment.silent(220, frame_rate=SR) + su_08 + AudioSegment.silent(520, frame_rate=SR)
    d08b = len(fg08b) / 1000.0
    stem08b = AudioSegment.silent(len(fg08b), frame_rate=SR).overlay(su_08, position=220)
    reg(
        "08b", "v02:clip_08.mp4", "video", fg08b, "ny_day_room",
        [(0.22, 0.22 + len(su_08) / 1000.0, "喂？是家明吗？")],
        curve=[(0.0, 0.0), (d08b, 62.0)],
        lipsync_dur_sec=d08b, speaker_stem=stem08b,
    )

    # 09a: Luo Jiaming silent choked grief (RIFE v4.26 optical-flow micro-breathing on clean grief frames f00..f09 + 3.5% dolly-in, zero f20+ smile!)
    fg09a = AudioSegment.silent(200, frame_rate=SR) + su_09 + make_pstn_line_hiss(1150, level_dbfs=-44.5)
    d09a = len(fg09a) / 1000.0
    reg(
        "09a", "v03:clip_09a_v3.mp4", "video", fg09a, "moscow_dead_quiet",
        [(0.20, 0.20 + len(su_09) / 1000.0, "（电话）家明？是你吗？怎么不说话呀？")],
        curve=[(0.0, 0.0), (2.20, 9.0), (3.85, 2.0), (d09a, 8.8)], zoom_pct=0.035,
    )

    # 09b: Lowering black receiver onto cradle (f31 -> f18 at 1.48s = exact hook_soft clack -> f04 at 2.45s)
    fg09b = make_pstn_line_hiss(1480, level_dbfs=-44.5) + synth_sfx("hook_soft") + AudioSegment.silent(370, frame_rate=SR)
    d09b = len(fg09b) / 1000.0
    reg(
        "09b", "v03:clip_09b_v3.mp4", "video", fg09b, "moscow_dead_quiet", [],
        curve=[(0.0, 31.0), (1.48, 18.0), (d09b, 4.0)],
    )

    # --- 1-4 Revolver Loading, Suicide Note, '見路不走' & Gunshot ---
    # 10a: Clean 5-finger bare hand loading brass cartridge into single revolver cylinder (f02..f80) + inner VO
    rev_sfx = synth_sfx("revolver_load_synced")  # 2250ms
    fg10a = rev_sfx + luo_10a + AudioSegment.silent(220, frame_rate=SR)
    d10a = len(fg10a) / 1000.0
    t_10a_vo = len(rev_sfx) / 1000.0
    reg(
        "10a", "v07:clip_10a_v7.mp4", "video", fg10a, "moscow_dead_quiet",
        [(t_10a_vo, t_10a_vo + len(luo_10a) / 1000.0, "我撑不住了……")],
        curve=[(0.0, 2.0), (0.38, 15.0), (1.65, 65.0), (2.05, 72.0), (d10a, 80.0)],
        zoom_pct=0.025,
    )

    # 10b: Fountain pen writing two lines (0.0..3.85s = f00..f52 synced to pen_two_lines) -> lifts pen cleanly (f52..f66, ZERO f70 double-pen!)
    pen_sfx = synth_sfx("pen_two_lines")  # 3900ms, strokes end at 3.80s
    fg10b = AudioSegment.silent(320, frame_rate=SR) + luo_10b + AudioSegment.silent(360, frame_rate=SR)
    fg10b = fg10b.overlay(pen_sfx, position=0)
    d10b = len(fg10b) / 1000.0
    reg(
        "10b", "v03:clip_10b_v3.mp4", "video", fg10b, "moscow_dead_quiet",
        [(0.32, 0.32 + len(luo_10b) / 1000.0, "我不能请求原谅，这不是可以原谅的事。")],
        curve=[(0.0, 0.0), (3.85, 52.0), (d10b, 66.0)],
    )

    # 11a: Medium OTS gazing at '見路不走' scroll -> lip-synced whispered murmur part 1
    fg11a = AudioSegment.silent(420, frame_rate=SR) + luo_11a + AudioSegment.silent(200, frame_rate=SR)
    d11a = len(fg11a) / 1000.0
    stem11a = AudioSegment.silent(len(fg11a), frame_rate=SR).overlay(luo_11a, position=420)
    reg(
        "11a", "v03:clip_11a_v3.mp4", "video", fg11a, "moscow_dead_quiet",
        [(0.42, 0.42 + len(luo_11a) / 1000.0, "见路不走……可我现在能见到的，")],
        curve=[(0.0, 0.0), (d11a, 96.0)],
        lipsync_dur_sec=d11a, speaker_stem=stem11a,
    )

    # 11b: Tight hollow-eyed close-up -> lip-synced whispered murmur part 2
    fg11b = AudioSegment.silent(180, frame_rate=SR) + luo_11b + AudioSegment.silent(550, frame_rate=SR)
    d11b = len(fg11b) / 1000.0
    stem11b = AudioSegment.silent(len(fg11b), frame_rate=SR).overlay(luo_11b, position=180)
    reg(
        "11b", "v03:clip_11b_v3.mp4", "video", fg11b, "moscow_dead_quiet",
        [(0.18, 0.18 + len(luo_11b) / 1000.0, "只有一条死路……不走，也得走了……")],
        curve=[(0.0, 0.0), (d11b, 96.0)],
        lipsync_dur_sec=d11b, speaker_stem=stem11b,
    )

    # 12a: Slow push-in on '見路不走' scroll -> indoor revolver blast at 1.15s + subtle muzzle flash bounce & acoustic tremor!
    fg12a = AudioSegment.silent(1150, frame_rate=SR) + synth_sfx("gunshot_revolver") + AudioSegment.silent(200, frame_rate=SR)
    d12a = len(fg12a) / 1000.0
    reg(
        "12a", "v02:clip_12a.mp4", "video", fg12a, "moscow_dead_quiet", [],
        curve=[(0.0, 0.0), (d12a, 64.0)], gunflash_ms=1150,
    )

    # 12b: Blood dripping off mahogany desk edge (frame-locked to f14=0.68s, f40=1.95s, f74=3.61s!) + -58 dBFS aftermath room tone
    fg12b = synth_sfx("drip_seq_synced")
    d12b = len(fg12b) / 1000.0
    reg(
        "12b", "v03:clip_12b_v3.mp4", "video", fg12b, "moscow_aftermath", [],
        curve=[(0.0, 0.0), (d12b, 79.0)], fade_out=True,
    )

    # 13: Clean cinema title card with matching -58 dBFS aftermath room tone tapering cleanly at tail
    fg13 = synth_sfx("drip_single") + AudioSegment.silent(2400, frame_rate=SR)
    reg("13", "", "card", fg13, "moscow_aftermath", [], card_lines=["天 幕 红 尘"])

    (ROOT / "audio_meta_v13.json").write_text(json.dumps(shots_spec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[prepare_v13 READY] {len(shots_spec)} shots (v0.13 coherent shot-and-sprawl Paris cold open + cached v0.10 reuse; 0 GPU calls needed)")


# ==============================================================================
# Stage 2: Final 30fps RIFE Assembly + Cinema FX + Single Burned-In Subtitles
# ==============================================================================
def load_cjk_font(size: int, serif: bool = True) -> ImageFont.FreeTypeFont:
    candidates = (
        ["/System/Library/Fonts/Supplemental/Songti.ttc", "/System/Library/Fonts/STHeiti Medium.ttc", "/System/Library/Fonts/PingFang.ttc"]
        if serif
        else ["/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc", "/System/Library/Fonts/Supplemental/Songti.ttc"]
    )
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def render_card_png(lines: list[str], out_png: Path):
    img = Image.new("RGB", (W, H), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    sizes = [58] if len(lines) == 1 else ([50] + [32] * (len(lines) - 1))
    gap = 28
    total_h = sum(sizes) + gap * (len(lines) - 1)
    y = (H - total_h) // 2
    for text, sz in zip(lines, sizes):
        fnt = load_cjk_font(sz, serif=True)
        bbox = draw.textbbox((0, 0), text, font=fnt)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) / 2, y), text, font=fnt, fill=(232, 230, 224))
        y += sz + gap
    img.save(out_png)


def format_srt_ts(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, rem = divmod(ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def draw_subtitle_on_frame(img: Image.Image, text: str) -> Image.Image:
    lines = []
    cur = ""
    for idx_c, ch in enumerate(text):
        cur += ch
        rem = text[idx_c + 1 :].strip()
        has_real_rem = any(c not in "，。！？；—… ”’）" for c in rem)
        if len(cur) >= 20 and ch in "，。！？；" and has_real_rem:
            lines.append(cur.strip())
            cur = ""
    if cur.strip():
        lines.append(cur.strip())

    out = img.convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ov)
    fnt = load_cjk_font(28, serif=False)
    line_h = 38
    y0 = H - 54 - line_h * len(lines)
    for idx, ln in enumerate(lines):
        bbox = draw.textbbox((0, 0), ln, font=fnt)
        tw = bbox[2] - bbox[0]
        x = (W - tw) / 2
        y = y0 + idx * line_h
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-2, -1, 0, 1, 2):
                if dx or dy:
                    draw.text((x + dx, y + dy), ln, font=fnt, fill=(0, 0, 0, 220))
        draw.text((x, y), ln, font=fnt, fill=(244, 242, 236, 255))
    return Image.alpha_composite(out, ov).convert("RGB")


def apply_bullet_jolt_effect(im: Image.Image, dt_sec: float) -> Image.Image:
    """Visceral silenced-sniper impact punch (subtle damped micro zoom + tremor without hiding real actor recoil)."""
    if dt_sec < 0 or dt_sec > 0.30:
        return im
    env = math.exp(-dt_sec * 15.0) * math.sin(min(math.pi, dt_sec / 0.06 * (math.pi / 2)))
    z = 1.0 + 0.016 * env
    dy = int(round(4.5 * math.exp(-dt_sec * 16.0) * math.cos(dt_sec * 38.0)))
    cw, ch = int(round(W / z)), int(round(H / z))
    x0 = (W - cw) // 2
    y0 = max(0, min(H - ch, (H - ch) // 2 - dy))
    return im.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.Resampling.LANCZOS)


def apply_gunshot_flash_and_tremor(im: Image.Image, dt_sec: float) -> Image.Image:
    """Off-screen indoor .38 revolver muzzle flash warm wall bounce + subtle acoustic camera tremor."""
    if dt_sec < 0 or dt_sec > 0.30:
        return im
    out = im
    if dt_sec < 0.07:
        flash_str = 0.22 * (1.0 - dt_sec / 0.07)
        warm = Image.new("RGB", (W, H), (255, 198, 130))
        out = Image.blend(out, warm, flash_str)
    amp = 4.5 * math.exp(-dt_sec * 16.0)
    dx = int(round(amp * math.sin(dt_sec * 95.0)))
    dy = int(round(amp * math.cos(dt_sec * 78.0)))
    if dx != 0 or dy != 0:
        z = 1.012
        cw, ch = int(round(W / z)), int(round(H / z))
        x0 = max(0, min(W - cw, (W - cw) // 2 + dx))
        y0 = max(0, min(H - ch, (H - ch) // 2 + dy))
        out = out.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.Resampling.LANCZOS)
    return out


def build_perimeter_inner_mask(h: int, w: int, margin: int = 36) -> np.ndarray:
    """1.0 inside center of frame, smoothly ramping to 0.0 at the outer `margin` pixels to eliminate any affine-restore border halo."""
    wy = np.minimum(np.arange(h, dtype=np.float32), np.arange(h - 1, -1, -1, dtype=np.float32)) / float(margin)
    wx = np.minimum(np.arange(w, dtype=np.float32), np.arange(w - 1, -1, -1, dtype=np.float32)) / float(margin)
    wy = np.clip(wy, 0.0, 1.0)
    wx = np.clip(wx, 0.0, 1.0)
    # Smoothstep
    wy = wy * wy * (3.0 - 2.0 * wy)
    wx = wx * wx * (3.0 - 2.0 * wx)
    return (wy[:, None] * wx[None, :])[:, :, None]


VF_CINEMA = "noise=alls=4:allf=t+u,vignette=PI/6,eq=contrast=1.04:saturation=0.92:gamma=0.98"
AF_LIMITER = "alimiter=limit=0.84:attack=2:release=50:level=false"


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            blk = fh.read(1 << 20)
            if not blk:
                break
            h.update(blk)
    return h.hexdigest()


def resolve_clip_path(clip_spec: str, fast_mode: bool) -> Path:
    src_tag, clip_fn = clip_spec.split(":", 1)
    dir_map = {
        "v13": V13_CLIP_DIR,
        "v12": V12_CLIP_DIR,
        "v11": V11_CLIP_DIR,
        "v10": V10_CLIP_DIR,
        "v09": V09_CLIP_DIR,
        "v08": V08_CLIP_DIR,
        "v07": V07_CLIP_DIR,
        "v03": V03_CLIP_DIR,
        "v02": V02_CLIP_DIR,
    }
    base_dir = dir_map.get(src_tag, V02_CLIP_DIR)
    cand = base_dir / clip_fn
    if cand.exists() or src_tag not in ("v10", "v11", "v12", "v13"):
        return cand
    scout_map = {"v13": V13_SCOUT_DIR, "v12": V12_SCOUT_DIR, "v11": V11_SCOUT_DIR, "v10": V10_SCOUT_DIR}
    scout_dir = scout_map[src_tag]
    if fast_mode:
        for sc in (scout_dir / clip_fn, scout_dir / f"{cand.stem}_s1.mp4", *sorted(scout_dir.glob(f"{cand.stem}_s*.mp4"))):
            if sc.exists():
                return sc
    raise FileNotFoundError(f"Missing clip for shot spec `{clip_spec}` (checked {cand}" + (f" and {scout_dir}" if fast_mode else "") + ")")


def find_lipsync_mp4(sid: str) -> Path:
    for d in (LIP_OUT_DIR, V08_LIP_OUT_DIR, V07_LIP_OUT_DIR):
        p = d / f"sync_{sid}.mp4"
        if p.exists():
            return p
    return V04_LIP_OUT_DIR / f"sync_{sid}.mp4"


def stabilize_hit_exposure(raw_frames: list[bytes]) -> list[bytes]:
    """Stabilize Wan2.2 mid-clip exposure/warmth via shared monotonic luma curve + feathered surround stabilization without shifting neutral sweater chroma."""
    if len(raw_frames) < 3:
        return raw_frames

    frames = [np.frombuffer(buf, dtype=np.uint8).reshape(H, W, 3).astype(np.float32) for buf in raw_frames]

    def _luma(rgb: np.ndarray) -> np.ndarray:
        return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]

    def _stats(f: np.ndarray):
        b = f[50:380, 640:1200]
        pv = f[500:700, 640:1200]
        sw_box = f[240:340, 290:360]
        mask = sw_box.mean(axis=2) > 150.0
        sw = sw_box[mask].mean(axis=0) if np.any(mask) else np.array([215.0, 200.0, 180.0], dtype=np.float32)
        return float(_luma(b).mean()), float(_luma(pv).mean()), float(_luma(sw).mean()), pv.mean(axis=(0, 1)), sw

    def _smooth_box(coord: np.ndarray, c0: float, c1: float, pad: float = 40.0) -> np.ndarray:
        u_in = np.clip((coord - (c0 - pad)) / pad, 0.0, 1.0)
        u_out = np.clip(((c1 + pad) - coord) / pad, 0.0, 1.0)
        return np.minimum(u_in * u_in * (3.0 - 2.0 * u_in), u_out * u_out * (3.0 - 2.0 * u_out))

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    fig_mask3 = (_smooth_box(xx, 145.0, 575.0, 36.0) * _smooth_box(yy, 135.0, 695.0, 36.0))[..., None]
    a0, a1 = _stats(frames[0]), _stats(frames[-1])
    n_last = float(len(frames) - 1)
    out: list[bytes] = []

    for i, f in enumerate(frames):
        t = i / n_last
        cur_b, cur_pv_y, cur_sw_y, _, _ = _stats(f)
        tgt_b = (1.0 - t) * a0[0] + t * a1[0]
        tgt_pv_y = (1.0 - t) * a0[1] + t * a1[1]
        tgt_sw_y = (1.0 - t) * a0[2] + t * a1[2]
        tgt_pv_rgb = (1.0 - t) * a0[3] + t * a1[3]
        tgt_sw_rgb = (1.0 - t) * a0[4] + t * a1[4]

        pairs = [(0.0, 0.0), (cur_b, tgt_b), (cur_pv_y, tgt_pv_y), (cur_sw_y, tgt_sw_y), (255.0, 255.0)]
        pairs.sort(key=lambda p: p[0])
        xs, ys = [pairs[0][0]], [pairs[0][1]]
        for px, py in pairs[1:]:
            if px > xs[-1] + 2.0 and py >= ys[-1]:
                xs.append(px)
                ys.append(py)
        if xs[-1] < 255.0:
            xs.append(255.0)
            ys.append(255.0)

        y_old = _luma(f)
        y_new = np.interp(y_old, np.array(xs), np.array(ys))
        f_luma = np.clip(f * (y_new / np.maximum(y_old, 1.0))[..., None], 0.0, 255.0)

        pv_post = f_luma[500:700, 640:1200].mean(axis=(0, 1))
        sw_box_post = f_luma[240:340, 290:360]
        sw_mask = sw_box_post.mean(axis=2) > 140.0
        sw_post = sw_box_post[sw_mask].mean(axis=0) if np.any(sw_mask) else tgt_sw_rgb

        wb_mid = np.clip(tgt_pv_rgb / np.maximum(pv_post, 1.0), 0.85, 1.15)
        wb_mid /= 0.2126 * wb_mid[0] + 0.7152 * wb_mid[1] + 0.0722 * wb_mid[2]
        wb_hi = np.clip(tgt_sw_rgb / np.maximum(sw_post, 1.0), 0.90, 1.10)
        wb_hi /= 0.2126 * wb_hi[0] + 0.7152 * wb_hi[1] + 0.0722 * wb_hi[2]

        y_post = _luma(f_luma)
        w_hi = np.clip((y_post - 75.0) / 95.0, 0.0, 1.0)[..., None]
        w_tone = np.clip((y_post - 12.0) / 35.0, 0.0, 1.0)[..., None]
        wb_px = (1.0 - w_hi) * wb_mid[None, None, :] + w_hi * wb_hi[None, None, :]
        f_corr = f_luma * (1.0 - w_tone + w_tone * wb_px)

        bg_ref = (1.0 - t) * frames[0] + t * frames[-1]
        blended = fig_mask3 * f_corr + (1.0 - fig_mask3) * bg_ref
        out.append(np.clip(blended, 0.0, 255.0).astype(np.uint8).tobytes())
    return out


def render_shot_frames(s: dict, fast_mode: bool) -> list[np.ndarray]:
    """Render all RGB frames for a single shot when cache misses or shot spec changed."""
    sid = s["id"]
    dur = float(s["dur"])
    n_frames = max(1, int(round(dur * FPS_FINAL)))
    frames_rgb: list[np.ndarray] = []

    if s["kind"] == "card":
        card_png = STILL_DIR / f"card_{sid}.png"
        render_card_png(s["card_lines"], card_png)
        base_arr = np.array(Image.open(card_png).convert("RGB"), dtype=np.float32)
        for k in range(n_frames):
            fade_in_f = FPS_FINAL * 0.65
            fade_out_f = FPS_FINAL * 0.70
            fade = min(1.0, max(0.0, (k - FPS_FINAL * 0.25) / fade_in_f), (n_frames - 1 - k) / fade_out_f)
            frames_rgb.append((base_arr * max(0.0, fade)).astype(np.uint8))
        return frames_rgb

    rife = get_rife()
    inner_mask = build_perimeter_inner_mask(H, W, margin=36)
    clip_p = resolve_clip_path(s["clip"], fast_mode=fast_mode)
    raw_frames = decode_video_frames(clip_p)
    ls_mp4 = find_lipsync_mp4(sid)
    ls_dur = s.get("lipsync_dur_sec")

    if ls_dur is not None and ls_mp4.exists():
        ls_raw = decode_video_frames(ls_mp4)
        pos_base_all = [eval_curve(k / FPS_FINAL, s["curve"]) for k in range(n_frames)]
        rgb_base = rife.render_positions(raw_frames, pos_base_all)
        if abs(ls_dur - dur) < 0.15:
            positions_30 = [(k / FPS_FINAL) * FPS_LIPSYNC for k in range(n_frames)]
            rgb_ls = rife.render_positions(ls_raw, positions_30)
            for k in range(n_frames):
                clean_f = (rgb_ls[k].astype(np.float32) * inner_mask + rgb_base[k].astype(np.float32) * (1.0 - inner_mask)).astype(np.uint8)
                frames_rgb.append(clean_f)
        else:
            t_blend_s = ls_dur - 0.18
            t_blend_e = ls_dur - 0.03
            pos_ls = [min(len(ls_raw) - 1.0, (k / FPS_FINAL) * FPS_LIPSYNC) for k in range(n_frames)]
            rgb_ls = rife.render_positions(ls_raw, pos_ls)
            for k in range(n_frames):
                t_now = k / FPS_FINAL
                ls_clean = rgb_ls[k].astype(np.float32) * inner_mask + rgb_base[k].astype(np.float32) * (1.0 - inner_mask)
                if t_now <= t_blend_s:
                    frames_rgb.append(ls_clean.astype(np.uint8))
                elif t_now >= t_blend_e:
                    frames_rgb.append(rgb_base[k])
                else:
                    alpha = (t_now - t_blend_s) / (t_blend_e - t_blend_s)
                    blended = (ls_clean * (1.0 - alpha) + rgb_base[k].astype(np.float32) * alpha).astype(np.uint8)
                    frames_rgb.append(blended)
    else:
        if ls_dur is not None:
            print(f"[WARN] Missing {ls_mp4}, falling back to RIFE base clip for {sid}")
        if s.get("chain_hit"):
            ch = s["chain_hit"]
            sw_t = float(ch["switch_sec"])
            hit_p = resolve_clip_path(ch["clip"], fast_mode=fast_mode)
            hit_raw = decode_video_frames(hit_p)
            if ch.get("tone_lock"):
                hit_raw = stabilize_hit_exposure(hit_raw)
            walk_idxs = [k for k in range(n_frames) if (k / FPS_FINAL) <= sw_t + 0.04]
            hit_idxs = [k for k in range(n_frames) if (k / FPS_FINAL) >= sw_t - 0.01]
            walk_rgb = rife.render_positions(raw_frames, [eval_curve(k / FPS_FINAL, s["curve"]) for k in walk_idxs])
            hit_rgb = rife.render_positions(hit_raw, [eval_curve(k / FPS_FINAL, ch["hit_curve"]) for k in hit_idxs])
            walk_map = dict(zip(walk_idxs, walk_rgb))
            hit_map = dict(zip(hit_idxs, hit_rgb))
            for k in range(n_frames):
                t_now = k / FPS_FINAL
                if t_now < sw_t:
                    frames_rgb.append(walk_map[k])
                elif t_now <= sw_t + 0.035 and k in walk_map:
                    alpha = min(1.0, max(0.0, (t_now - sw_t) / 0.035))
                    blended = (walk_map[k].astype(np.float32) * (1.0 - alpha) + hit_map[k].astype(np.float32) * alpha).astype(np.uint8)
                    frames_rgb.append(blended)
                else:
                    frames_rgb.append(hit_map[k])
        else:
            positions_30 = [eval_curve(k / FPS_FINAL, s["curve"]) for k in range(n_frames)]
            frames_rgb = rife.render_positions(raw_frames, positions_30)

    if sid in ("05a", "05c"):
        frames_rgb = patch_05_photo_frames(sid, frames_rgb, INS2_STILL_PATH)
    elif sid == "10b":
        frames_rgb = remove_10b_right_watch(frames_rgb)
    elif sid == "11b":
        frames_rgb = darken_11b_midnight_window(frames_rgb)
    return frames_rgb


def assemble_v11(fast_mode: bool = False):
    t_start = time.monotonic()
    shots_spec = json.loads((ROOT / "audio_meta_v13.json").read_text(encoding="utf-8"))
    v10_meta_path = V10_ROOT / "audio_meta_v10.json"
    v10_spec_by_id: dict[str, dict] = {}
    if v10_meta_path.exists():
        v10_spec_by_id = {entry["id"]: entry for entry in json.loads(v10_meta_path.read_text(encoding="utf-8"))}
    v09_meta_path = V09_ROOT / "audio_meta_v09.json"
    v09_spec_by_id: dict[str, dict] = {}
    if v09_meta_path.exists():
        v09_spec_by_id = {entry["id"]: entry for entry in json.loads(v09_meta_path.read_text(encoding="utf-8"))}

    mode_tag = "fast" if fast_mode else "master"
    vf_args = [] if fast_mode else ["-vf", VF_CINEMA]
    enc_preset = "veryfast" if fast_mode else "medium"
    enc_crf = "20" if fast_mode else "17"

    seg_files: list[Path] = []
    srt_entries: list[tuple[float, float, str]] = []
    t_cursor = 0.0
    n_cached = 0
    n_reused_v10 = 0
    n_reused_v09 = 0
    n_rendered = 0

    for s in shots_spec:
        sid = s["id"]
        dur = float(s["dur"])
        n_frames = max(1, int(round(dur * FPS_FINAL)))
        seg_dur = n_frames / float(FPS_FINAL)
        wav_p = AUD_DIR / f"shot_{sid}.wav"
        out_seg = SHOT_DIR / f"seg_{mode_tag}_{sid}.mov"
        hash_p = SHOT_DIR / f"seg_{mode_tag}_{sid}.sha256"

        s_cmp = {k: v for k, v in s.items() if k != "chain_hit"}
        v10_seg_p = V10_ROOT / "shots" / f"seg_{mode_tag}_{sid}.mov"
        can_reuse_v10 = (
            "chain_hit" not in s
            and v10_seg_p.exists()
            and sid in v10_spec_by_id
            and v10_spec_by_id[sid] == s_cmp
        )
        v09_shot_p = V09_ROOT / "shots" / f"shot_{sid}.mp4"
        can_reuse_v09 = (
            not can_reuse_v10
            and "chain_hit" not in s
            and v09_shot_p.exists()
            and sid in v09_spec_by_id
            and v09_spec_by_id[sid] == s_cmp
        )

        hash_payload: dict[str, object] = {
            "v": 4,
            "mode": mode_tag,
            "spec": s,
            "seg_dur": seg_dur,
            "vf": "" if fast_mode else VF_CINEMA,
            "wav_sha256": file_sha256(wav_p),
        }
        if can_reuse_v10:
            st = v10_seg_p.stat()
            hash_payload["source"] = {"reuse": "v10", "size": st.st_size, "mtime_ns": st.st_mtime_ns}
        elif can_reuse_v09:
            st = v09_shot_p.stat()
            hash_payload["source"] = {"reuse": "v09", "size": st.st_size, "mtime_ns": st.st_mtime_ns}
        elif s["kind"] == "video":
            clip_p = resolve_clip_path(s["clip"], fast_mode=fast_mode)
            ls_mp4 = find_lipsync_mp4(sid)
            src_d: dict[str, object] = {
                "clip": str(clip_p),
                "clip_sha256": file_sha256(clip_p),
                "ls_sha256": file_sha256(ls_mp4) if (s.get("lipsync_dur_sec") is not None and ls_mp4.exists()) else "",
                "patch_sha256": file_sha256(INS2_STILL_PATH) if sid in ("05a", "05c") else "",
            }
            if s.get("chain_hit"):
                hp = resolve_clip_path(s["chain_hit"]["clip"], fast_mode=fast_mode)
                src_d["chain_hit_clip"] = str(hp)
                src_d["chain_hit_sha256"] = file_sha256(hp)
            hash_payload["source"] = src_d
        else:
            hash_payload["source"] = {"card": True}

        expected_hash = hashlib.sha256(json.dumps(hash_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

        if out_seg.exists() and hash_p.exists() and hash_p.read_text(encoding="utf-8").strip() == expected_hash:
            n_cached += 1
            status_tag = "CACHE HIT"
        elif can_reuse_v10:
            n_reused_v10 += 1
            status_tag = "REUSE v10"
            subprocess.run(
                [
                    "ffmpeg", "-y", "-v", "error",
                    "-i", str(v10_seg_p),
                    "-i", str(wav_p),
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-af", "apad",
                    "-c:v", "copy",
                    "-c:a", "pcm_s16le", "-ar", str(SR), "-ac", "2",
                    "-t", f"{seg_dur:.6f}", str(out_seg),
                ],
                check=True,
            )
            hash_p.write_text(expected_hash, encoding="utf-8")
        elif can_reuse_v09:
            n_reused_v09 += 1
            status_tag = "REUSE v09"
            if fast_mode:
                cmd = [
                    "ffmpeg", "-y", "-v", "error",
                    "-i", str(v09_shot_p),
                    "-i", str(wav_p),
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-af", "apad",
                    "-c:v", "copy",
                    "-c:a", "pcm_s16le", "-ar", str(SR), "-ac", "2",
                    "-t", f"{seg_dur:.6f}", str(out_seg),
                ]
            else:
                cmd = [
                    "ffmpeg", "-y", "-v", "error",
                    "-i", str(v09_shot_p),
                    "-i", str(wav_p),
                    "-map", "0:v:0", "-map", "1:a:0",
                    *vf_args,
                    "-af", "apad",
                    "-r", str(FPS_FINAL),
                    "-c:v", "libx264", "-preset", enc_preset, "-crf", enc_crf,
                    "-profile:v", "high", "-level:v", "3.1", "-bf", "2",
                    "-pix_fmt", "yuv420p", "-video_track_timescale", "15360",
                    "-c:a", "pcm_s16le", "-ar", str(SR), "-ac", "2",
                    "-t", f"{seg_dur:.6f}", str(out_seg),
                ]
            subprocess.run(cmd, check=True)
            hash_p.write_text(expected_hash, encoding="utf-8")
        else:
            n_rendered += 1
            status_tag = "RENDER"
            frames_rgb = render_shot_frames(s, fast_mode=fast_mode)
            subs = s["subs"]
            crt_off_sec = (s["crt_off_ms"] / 1000.0) if s.get("crt_off_ms") is not None else None
            jolt_sec = (s["jolt_ms"] / 1000.0) if s.get("jolt_ms") is not None else None
            gun_sec = (s["gunflash_ms"] / 1000.0) if s.get("gunflash_ms") is not None else None
            zoom_pct = float(s.get("zoom_pct") or 0.0)

            cmd = [
                "ffmpeg", "-y", "-v", "error",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS_FINAL), "-i", "-",
                "-i", str(wav_p),
                *vf_args,
                "-af", "apad",
                "-r", str(FPS_FINAL),
                "-c:v", "libx264", "-preset", enc_preset, "-crf", enc_crf,
                "-profile:v", "high", "-level:v", "3.1", "-bf", "2",
                "-pix_fmt", "yuv420p", "-video_track_timescale", "15360",
                "-c:a", "pcm_s16le", "-ar", str(SR), "-ac", "2",
                "-t", f"{seg_dur:.6f}", str(out_seg),
            ]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            for k, arr in enumerate(frames_rgb):
                t_now = k / FPS_FINAL
                prog = k / max(1, n_frames - 1)
                if crt_off_sec is not None and t_now >= crt_off_sec:
                    arr = apply_clean_crt_turnoff(arr, t_now - crt_off_sec)
                im = Image.fromarray(arr)
                if zoom_pct > 0.0:
                    z = 1.0 + zoom_pct * prog
                    cw, ch = int(round(W / z)), int(round(H / z))
                    x0, y0 = (W - cw) // 2, (H - ch) // 2
                    im = im.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.Resampling.LANCZOS)
                if jolt_sec is not None and t_now >= jolt_sec:
                    im = apply_bullet_jolt_effect(im, t_now - jolt_sec)
                if gun_sec is not None and t_now >= gun_sec:
                    im = apply_gunshot_flash_and_tremor(im, t_now - gun_sec)

                active_txt = None
                for a, b, txt in subs:
                    if a <= t_now <= b + 0.12:
                        active_txt = txt
                        break
                if active_txt:
                    im = draw_subtitle_on_frame(im, active_txt)

                if s.get("fade_in") and k < int(FPS_FINAL * 0.5):
                    im = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), im, k / (FPS_FINAL * 0.5))
                elif s.get("fade_out") and k > n_frames - int(FPS_FINAL * 0.55):
                    rem = max(0.0, (n_frames - 1 - k) / (FPS_FINAL * 0.55))
                    im = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), im, rem)

                proc.stdin.write(im.tobytes())
            proc.stdin.close()
            if proc.wait() != 0:
                raise RuntimeError(f"ffmpeg failed on shot {sid}")
            hash_p.write_text(expected_hash, encoding="utf-8")

        for a, b, txt in s["subs"]:
            srt_entries.append((t_cursor + a, t_cursor + b, txt))
        seg_files.append(out_seg)
        t_cursor += dur
        print(f"[{status_tag:9s} | {mode_tag}] shot_{sid:8s} ({dur:.2f}s)")

    concat_txt = ROOT / f"concat_v13_{mode_tag}.txt"
    concat_txt.write_text("".join(f"file '{p}'\n" for p in seg_files), encoding="utf-8")

    out_mp4 = (OUT_DIR / "preview_v0.13_fast.mp4") if fast_mode else get_next_version_mp4()
    if not fast_mode:
        archive_srt = OUT_DIR / f"{out_mp4.stem}_字幕归档.srt"
        srt_text = "".join(f"{i}\n{format_srt_ts(a)} --> {format_srt_ts(b)}\n{txt}\n\n" for i, (a, b, txt) in enumerate(srt_entries, 1))
        archive_srt.write_text(srt_text, encoding="utf-8")
        for legacy_srt in VIDEO_ROOT.glob(f"{PILOT_PREFIX}_v*.srt"):
            legacy_srt.unlink()
            print(f"[removed duplicate sidecar] {legacy_srt}")

    # Stream-copy H.264 video directly across pre-graded segments; run single-pass continuous AAC limiter (< 1s)!
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-f", "concat", "-safe", "0", "-i", str(concat_txt),
            "-c:v", "copy",
            "-af", AF_LIMITER,
            "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2",
            "-sn", "-movflags", "+faststart",
            str(out_mp4),
        ],
        check=True,
    )
    elapsed = time.monotonic() - t_start
    print(
        f"[V0.13 {mode_tag.upper()} READY in {elapsed:.2f}s] {out_mp4} "
        f"({out_mp4.stat().st_size / (1024*1024):.2f} MB, {t_cursor:.2f}s @ {FPS_FINAL}fps) | "
        f"cached={n_cached}, reused_v10={n_reused_v10}, reused_v09={n_reused_v09}, rendered={n_rendered}"
    )


if __name__ == "__main__":
    args = sys.argv[1:]
    fast_flag = "--fast" in args
    pos_args = [a for a in args if not a.startswith("--")]
    mode = pos_args[0] if pos_args else "all"
    if mode in ("prepare", "all"):
        prepare_v10()
    if mode in ("assemble", "all"):
        assemble_v11(fast_mode=fast_flag)
