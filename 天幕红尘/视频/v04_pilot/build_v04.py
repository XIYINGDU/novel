#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v0.4 Cinema Master Pipeline for《天幕红尘》Ep01 Opening Pilot:
1. Single clean cinema subtitle layer (eliminates same-name .srt auto-mount double subtitles).
2. RIFE v4.26 HD optical-flow arbitrary-timestep interpolation @ 30fps (eliminates 16->24fps Image.blend stutter & ghosting).
3. Frame-accurate piecewise time-warping & SFX alignment across all physical actions (bullet jolts, dialing, receiver lift/cradle, revolver loading, pen writing, blood drips).
4. Isolated speaker vocal stems + 25fps pre-warped clips for ByteDance LatentSync-1.6 512x512 lip-sync.
"""

import array
import json
import math
import os
import random
import subprocess
import sys
import tarfile
from pathlib import Path

os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw, ImageFont
from pydub import AudioSegment

V02_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v02_pilot")
V03_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v03_pilot")
ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v04_pilot")

RIFE_ROOT = ROOT / "rife_v426"
sys.path.insert(0, str(RIFE_ROOT))

AUD_DIR = ROOT / "audio"
LIP_IN_DIR = ROOT / "lipsync_in"
LIP_OUT_DIR = ROOT / "lipsync_out"
SHOT_DIR = ROOT / "shots"
OUT_DIR = ROOT / "out"
STILL_DIR = ROOT / "stills"

SFX_DIR = V02_ROOT / "real_sfx"
V02_AUD_DIR = V02_ROOT / "audio"
V03_AUD_DIR = V03_ROOT / "audio"
V02_CLIP_DIR = V02_ROOT / "clips"
V03_CLIP_DIR = V03_ROOT / "clips"
MAC_DTMF_DIR = Path("/System/Library/Components/CoreAudio.component/Contents/SharedSupport/SystemSounds/telephony")

for d in (AUD_DIR, LIP_IN_DIR, LIP_OUT_DIR, SHOT_DIR, OUT_DIR, STILL_DIR):
    d.mkdir(parents=True, exist_ok=True)

VIDEO_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频")
FINAL_MP4_V03 = VIDEO_ROOT / "第01集_开篇试片_v0.3.mp4"
FINAL_MP4_V02 = VIDEO_ROOT / "第01集_开篇试片_v0.2.mp4"
LEGACY_SRT_V03 = VIDEO_ROOT / "第01集_开篇试片_v0.3.srt"
LEGACY_SRT_V02 = VIDEO_ROOT / "第01集_开篇试片_v0.2.srt"
ARCHIVE_SRT = OUT_DIR / "第01集_开篇试片_v0.4_字幕归档.srt"

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
    p = V03_AUD_DIR / fname if (V03_AUD_DIR / fname).exists() else (V02_AUD_DIR / fname)
    return AudioSegment.from_file(p).set_frame_rate(SR).set_channels(1).set_sample_width(2)


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


def synth_sfx(name: str) -> AudioSegment:
    if name == "footsteps_stone":
        raw_step = load_real_wav("footsteps_4.wav")[20:1620].fade_in(25).fade_out(70)
        sole = ffmpeg_af(
            raw_step,
            "highpass=f=65,lowpass=f=440:poles=2,equalizer=f=135:t=q:w=1.2:g=3.2,aecho=0.8:0.72:24:0.09",
        )
        sole = sole.apply_gain(-20.5 - sole.dBFS)
        wet_src = load_real_wav("rain_07.wav")
        cloth_src = load_real_wav("cloth_1.wav")
        out = AudioSegment.silent(len(sole), frame_rate=SR).overlay(sole)
        for idx, pos_ms in enumerate((28, 628, 1278)):
            scuff = wet_src[400 + idx * 180 : 455 + idx * 180].fade_in(8).fade_out(28)
            scuff = ffmpeg_af(scuff, "highpass=f=320:poles=2,lowpass=f=1150:poles=2").apply_gain(-31.5 - scuff.dBFS)
            swish = cloth_src[1500 + idx * 140 : 1630 + idx * 140].fade_in(18).fade_out(45)
            swish = ffmpeg_af(swish, "highpass=f=250,lowpass=f=2200:poles=2").apply_gain(-32.5 - swish.dBFS)
            out = out.overlay(scuff, position=pos_ms).overlay(swish, position=max(0, pos_ms - 10))
        return out

    if name in ("thump_1", "thump_2"):
        in_supp = load_real_wav("indoor_supp.wav")
        pffft = in_supp[1475:1860] if name == "thump_1" else in_supp[7565:7960]
        pffft = ffmpeg_af(pffft.fade_in(2).fade_out(80), "highpass=f=120,lowpass=f=2100:poles=2")
        pffft = pffft.apply_gain(-4.5 - pffft.max_dBFS)

        supp_raw = load_real_wav("sniper_supp.wav")
        thwip = supp_raw[585:920] if name == "thump_1" else supp_raw[3285:3620]
        thwip = ffmpeg_af(thwip.fade_in(2).fade_out(70), "highpass=f=90,lowpass=f=1600:poles=2")
        thwip = thwip.apply_gain(-6.5 - thwip.max_dBFS)

        body_thud = load_real_wav("wood_thud.wav")[490:820].fade_in(2).fade_out(110)
        body_thud = ffmpeg_af(body_thud, "lowpass=f=310:poles=2,equalizer=f=85:t=q:w=1.0:g=5.5")
        body_thud = body_thud.apply_gain(-2.2 - body_thud.max_dBFS)

        cloth_hit = load_real_wav("cloth_1.wav")[1530:1820].fade_in(3).fade_out(70)
        cloth_hit = cloth_hit.apply_gain(-10.5 - cloth_hit.max_dBFS)

        out = AudioSegment.silent(540, frame_rate=SR)
        out = out.overlay(pffft, position=0).overlay(thwip, position=6).overlay(body_thud, position=14).overlay(cloth_hit, position=16)
        return ffmpeg_af(out, "alimiter=limit=0.92:attack=1:release=35")

    if name == "fall":
        scuff = load_real_wav("footsteps_2.wav")[1860:2220].fade_out(80).apply_gain(-8.0)
        knee_hit = ffmpeg_af(load_real_wav("wood_thud.wav")[480:830], "lowpass=f=650:poles=2").apply_gain(-5.0)
        torso_hit = ffmpeg_af(load_real_wav("wood_thud.wav")[780:1280], "lowpass=f=480:poles=2").apply_gain(-2.5)
        cloth = load_real_wav("cloth_1.wav")[1480:2250].apply_gain(5.0)
        out = AudioSegment.silent(880, frame_rate=SR)
        out = out.overlay(scuff, position=0).overlay(knee_hit, position=70).overlay(torso_hit, position=300).overlay(cloth, position=90)
        return out.fade_out(80)

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
        # Synced to clip_10a_v3 f24->f80:
        #   0.38s..1.15s: brass cartridge sliding into open chamber (f34->f60)
        #   1.52s..2.22s: thumb pushing cylinder inward & ratcheting click (f62->f76)
        ins1 = load_real_wav("rev_insert.wav")[6640:7180].fade_in(12).fade_out(45)
        ins1 = ins1.apply_gain(-12.5 - ins1.max_dBFS)
        close = load_real_wav("rev_close_cyl.wav")[740:1140].fade_in(8).fade_out(50)
        close = close.apply_gain(-7.5 - close.max_dBFS)
        idx_click = load_real_wav("rev_spin_cyl.wav")[540:880].fade_in(8).fade_out(60)
        idx_click = idx_click.apply_gain(-11.5 - idx_click.max_dBFS)
        out = AudioSegment.silent(2350, frame_rate=SR)
        return out.overlay(ins1, position=380).overlay(close, position=1520).overlay(idx_click, position=1890)

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
# Stage 1: Prepare Audio Mix, Frame-Locked Curves & LatentSync Inputs (25fps)
# ==============================================================================
def prepare_v04():
    tv_bed = ffmpeg_af(
        load_voice_mp3("tv_gorbachev_19910824.mp3"),
        "highpass=f=380:poles=2,lowpass=f=3100:poles=2,equalizer=f=1250:t=q:w=1.5:g=3.0",
    ) - 18.5
    tv_cursor_ms = 0

    def add_tv(bed: AudioSegment, cutoff_ms: int = None) -> AudioSegment:
        nonlocal tv_cursor_ms
        total_ms = len(bed)
        need = cutoff_ms if cutoff_ms is not None else total_ms
        loops = tv_bed * ((tv_cursor_ms + need) // len(tv_bed) + 2)
        sl = loops[tv_cursor_ms : tv_cursor_ms + need]
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
    ):
        total_ms = len(fg)
        dur_sec = round(total_ms / 1000.0, 3)
        bed = make_ambience(amb, total_ms)
        if tv:
            bed = add_tv(bed, cutoff_ms=tv_cut_ms)
        mixed = bed.overlay(fg)
        mixed.export(AUD_DIR / f"shot_{sid}.wav", format="wav")

        if lipsync_dur_sec is not None and speaker_stem is not None:
            stems_to_export[sid] = (speaker_stem, lipsync_dur_sec)

        shots_spec.append(
            {
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
        )
        print(f"[audio v0.4] shot_{sid:8s} dur={dur_sec:5.2f}s  clip={clip_src}")

    # --- 1-1 Paris Cold Open ---
    # 01: 3 synced sneaker footsteps (0.35s, 0.95s, 1.60s) -> 1st silenced bullet hits at 1.92s (f45) + jolt & arrest!
    steps_sfx = synth_sfx("footsteps_stone")  # 1600ms, steps at 28, 628, 1278ms
    fg01 = AudioSegment.silent(320, frame_rate=SR) + steps_sfx + synth_sfx("thump_1") + AudioSegment.silent(300, frame_rate=SR)
    d01 = len(fg01) / 1000.0  # 2.76s
    reg(
        "01", "v03:clip_01_v3.mp4", "video", fg01, "paris_night", [],
        curve=[(0.0, 0.0), (0.35, 7.0), (0.95, 22.0), (1.60, 39.0), (1.92, 45.0), (2.15, 48.2), (d01, 50.0)],
        fade_in=True, jolt_ms=1920,
    )

    # 02a: Chest macro -> 2nd silenced bullet hits at 0.26s (f06->f14 crimson bloom!) -> breathy chuckle
    fg02a = AudioSegment.silent(260, frame_rate=SR) + synth_sfx("thump_2") + AudioSegment.silent(420, frame_rate=SR) + ye_line[:650] + AudioSegment.silent(160, frame_rate=SR)
    d02a = len(fg02a) / 1000.0
    reg(
        "02a", "v03:clip_02a_v3.mp4", "video", fg02a, "paris_night", [],
        curve=[(0.0, 2.0), (0.26, 6.0), (0.65, 14.0), (d02a, 46.0)],
        jolt_ms=260,
    )

    # 02b: Kneeling on wet stone steps -> VO "还真他妈抬举我。" (0..1.59s) -> collapse synced to fall SFX (1.71s..2.59s)
    ye_rem = ye_line[650:]
    fg02b = ye_rem + AudioSegment.silent(120, frame_rate=SR) + synth_sfx("fall") + AudioSegment.silent(160, frame_rate=SR)
    d02b = len(fg02b) / 1000.0
    reg(
        "02b", "v03:clip_02b_v3.mp4", "video", fg02b, "paris_night",
        [(0.0, len(ye_rem) / 1000.0, "还真他妈抬举我。")],
        curve=[(0.0, 0.0), (1.59, 17.0), (1.78, 22.0), (2.15, 33.0), (d02b, 38.5)],
    )

    # 03: Time Card
    reg("03", "", "card", AudioSegment.silent(3400, frame_rate=SR), "silence", [], card_lines=["一年前", "1991年8月24日夜　莫斯科"])

    # --- 1-2 Moscow Midnight Street & 12F Office Crisis Call ---
    # 04: Exterior 12F lit window + muffled ring + J-cut snatch
    fg04 = AudioSegment.silent(450, frame_rate=SR) + synth_sfx("phone_moscow_jcut")
    d04 = len(fg04) / 1000.0
    reg("04", "v03:clip_04_v3.mp4", "video", fg04, "moscow_street", [], curve=[(0.0, 0.0), (d04, 80.0)])

    # 05a: Luo answers phone ("我是罗。") -> lip-synced via LatentSync-1.6!
    t_luo_end = (150 + len(luo_05a)) / 1000.0
    t_k1a_s = t_luo_end + 0.15
    fg05a = AudioSegment.silent(150, frame_rate=SR) + luo_05a + AudioSegment.silent(150, frame_rate=SR) + kug_1a + AudioSegment.silent(80, frame_rate=SR)
    d05a = len(fg05a) / 1000.0
    stem05a = AudioSegment.silent(len(fg05a), frame_rate=SR).overlay(luo_05a, position=150)
    reg(
        "05a", "v02:clip_05a.mp4", "video", fg05a, "moscow_room",
        [(0.15, t_luo_end, "我是罗。"), (t_k1a_s, d05a, "（电话）罗！秘密股东协议里的五个高官已经抓了三个！")],
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

    # 05c: Replaced static disembodied hand with full actor medium close-up (v02:clip_05b.mp4)!
    #   0.00..2.58s: Kuglev final plea (Luo listens stoically)
    #   2.83..7.15s: Luo calmly says "知道了，库格列夫。明天再说吧。" (Lip-synced via LatentSync-1.6!)
    #   7.15..7.72s: Luo lowers receiver from ear onto cradle (f58->f89), hook click right at 7.72s!
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
        "05c", "v02:clip_05b.mp4", "video", fg05c, "moscow_room",
        [
            (0.0, t_k2b_end, "（电话）罗，我那6万美金口头暗股怎么办？！"),
            (t_l05c_s, t_l05c_e, "知道了，库格列夫。明天再说吧。"),
        ],
        curve=[(0.0, 0.0), (t_l05c_e, 58.0), (t_hook, 89.0), (d05c, 95.0)],
        tv=True,
        lipsync_dur_sec=round(t_l05c_e + 0.08, 3),
        speaker_stem=stem05c,
    )

    # --- 1-3 Window Smoke, Switching Off CRT TV & Wordless Call to Mother in NY ---
    # 06a: Window smoke (f00..f24: cigarette hand down on windowsill, cold glance at TV) + lip-synced "这个笨蛋！"
    t_06_s = 1.20
    fg06a = AudioSegment.silent(1200, frame_rate=SR) + luo_06 + AudioSegment.silent(700, frame_rate=SR)
    d06a = len(fg06a) / 1000.0
    stem06a = AudioSegment.silent(len(fg06a), frame_rate=SR).overlay(luo_06, position=1200)
    reg(
        "06a", "v02:clip_06.mp4", "video", fg06a, "moscow_room",
        [(t_06_s, t_06_s + len(luo_06) / 1000.0, "这个笨蛋！")],
        curve=[(0.0, 0.0), (d06a, 24.0)], tv=True,
        lipsync_dur_sec=d06a, speaker_stem=stem06a,
    )

    # 06b: Hand clicks CRT TV power switch at 0.95s (f26) -> screen collapses to true dark glass & room goes dead silent!
    tv_click_ms = 950
    fg06b = AudioSegment.silent(tv_click_ms, frame_rate=SR) + synth_sfx("tv_off") + AudioSegment.silent(950, frame_rate=SR)
    d06b = len(fg06b) / 1000.0
    reg(
        "06b", "v03:clip_06b_v3.mp4", "video", fg06b, "moscow_room", [],
        curve=[(0.0, 2.0), (0.95, 26.0), (d06b, 45.0)],
        tv=True, tv_cut_ms=tv_click_ms + 45, crt_off_ms=tv_click_ms + 45,
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
    # 10a: Loading brass cartridge (0.38..1.15s = f34..f60) + closing cylinder (1.52..2.22s = f62..f76) + inner VO
    rev_sfx = synth_sfx("revolver_load_synced")  # 2350ms
    fg10a = rev_sfx + luo_10a + AudioSegment.silent(200, frame_rate=SR)
    d10a = len(fg10a) / 1000.0
    t_10a_vo = len(rev_sfx) / 1000.0
    reg(
        "10a", "v03:clip_10a_v3.mp4", "video", fg10a, "moscow_dead_quiet",
        [(t_10a_vo, t_10a_vo + len(luo_10a) / 1000.0, "我撑不住了……")],
        curve=[(0.0, 24.0), (0.38, 34.0), (1.25, 60.0), (1.52, 62.0), (2.25, 76.0), (d10a, 80.0)],
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

    # 12b: Blood dripping off mahogany desk edge (frame-locked to f14=0.68s, f40=1.95s, f74=3.61s!)
    fg12b = synth_sfx("drip_seq_synced")
    d12b = len(fg12b) / 1000.0
    reg(
        "12b", "v03:clip_12b_v3.mp4", "video", fg12b, "silence", [],
        curve=[(0.0, 0.0), (d12b, 79.0)], fade_out=True,
    )

    # 13: Clean cinema title card
    fg13 = synth_sfx("drip_single") + AudioSegment.silent(2400, frame_rate=SR)
    reg("13", "", "card", fg13, "silence", [], card_lines=["天 幕 红 尘"])

    (ROOT / "audio_meta_v04.json").write_text(json.dumps(shots_spec, ensure_ascii=False, indent=2), encoding="utf-8")

    # Render 25.0 fps RIFE-interpolated base clips + 16kHz isolated stems for LatentSync-1.6
    rife = get_rife()
    spec_by_id = {s["id"]: s for s in shots_spec}
    for sid, (stem_seg, ls_dur) in stems_to_export.items():
        s = spec_by_id[sid]
        src_tag, clip_fn = s["clip"].split(":", 1)
        clip_p = (V03_CLIP_DIR if src_tag == "v03" else V02_CLIP_DIR) / clip_fn
        raw_frames = decode_video_frames(clip_p)

        n_25 = max(1, int(round(ls_dur * FPS_LIPSYNC)))
        # Pad +3 tail frames and +120ms silent audio so LatentSync never loops or truncates by 1 frame
        positions = [eval_curve(k / FPS_LIPSYNC, s["curve"]) for k in range(n_25)]
        positions += [positions[-1]] * 3
        rgb_25 = rife.render_positions(raw_frames, positions)

        vid_in = LIP_IN_DIR / f"vid_{sid}.mp4"
        wav_in = LIP_IN_DIR / f"stem_{sid}.wav"
        encode_mp4_no_audio(rgb_25, vid_in, FPS_LIPSYNC)

        padded_stem = (stem_seg + AudioSegment.silent(160, frame_rate=SR)).set_frame_rate(16000).set_channels(1).set_sample_width(2)
        padded_stem.export(wav_in, format="wav")
        print(f"[lipsync_in ready] {sid}: {n_25}+3 frames @ 25fps ({ls_dur:.2f}s)")

    tar_in = ROOT / "lipsync_in.tar.gz"
    with tarfile.open(tar_in, "w:gz") as tf:
        for p in sorted(LIP_IN_DIR.glob("*")):
            tf.add(p, arcname=p.name)
    print(f"[PACKED] {tar_in} ({tar_in.stat().st_size / (1024*1024):.2f} MB)")


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


def apply_crt_turnoff_effect(arr: np.ndarray, dt_sec: float) -> np.ndarray:
    """True CRT phosphor collapse inside the Soviet TV glass screen (x=445..1075, y=82..552) + nocturnal room drop."""
    if dt_sec < 0:
        return arr
    out = arr.astype(np.float32)
    # Identify glowing blue-white phosphor screen pixels inside the CRT bezel region
    roi = out[80:556, 445:1080]
    lum = 0.2126 * roi[:, :, 0] + 0.7152 * roi[:, :, 1] + 0.0722 * roi[:, :, 2]
    screen_w = np.clip((lum - 36.0) / 38.0, 0.0, 1.0)[:, :, None]

    # Collapse glowing screen into dark curved glass rgb(6, 7, 9)
    collapse = min(1.0, dt_sec / 0.06) if dt_sec < 0.06 else 1.0
    dark_glass = np.array([6.0, 7.0, 9.0], dtype=np.float32)
    roi_after = roi * (1.0 - screen_w * collapse) + dark_glass * (screen_w * collapse)
    out[80:556, 445:1080] = roi_after

    # Drop surrounding room ambient spill once CRT light extinguishes
    room_dim = 1.0 - 0.86 * min(1.0, dt_sec / 0.07)
    out = out * room_dim

    # Brief white horizontal phosphor collapse line -> center dot during first 0.09s
    im = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
    if dt_sec < 0.09:
        draw = ImageDraw.Draw(im)
        p = dt_sec / 0.09
        cx, cy = 762, 315
        half_w = int(260 * max(0.03, (1.0 - p) ** 1.6))
        half_h = 2 if p < 0.5 else 1
        bri = int(245 * (1.0 - 0.45 * p))
        draw.rectangle([cx - half_w, cy - half_h, cx + half_w, cy + half_h], fill=(bri, min(255, bri + 10), 255))
    return np.array(im)


def apply_bullet_jolt_effect(im: Image.Image, dt_sec: float) -> Image.Image:
    """Visceral silenced-sniper chest impact recoil (subtle damped zoom punch + vertical torso jolt)."""
    if dt_sec < 0 or dt_sec > 0.36:
        return im
    env = math.exp(-dt_sec * 12.0) * math.sin(min(math.pi, dt_sec / 0.07 * (math.pi / 2)))
    z = 1.0 + 0.024 * env
    dy = int(round(7.0 * math.exp(-dt_sec * 14.0) * math.cos(dt_sec * 38.0)))
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


def assemble_v04():
    shots_spec = json.loads((ROOT / "audio_meta_v04.json").read_text(encoding="utf-8"))
    rife = get_rife()
    inner_mask = build_perimeter_inner_mask(H, W, margin=36)
    seg_files = []
    srt_entries = []
    t_cursor = 0.0

    for s in shots_spec:
        sid = s["id"]
        dur = float(s["dur"])
        n_frames = max(1, int(round(dur * FPS_FINAL)))
        wav_p = AUD_DIR / f"shot_{sid}.wav"
        out_seg = SHOT_DIR / f"shot_{sid}.mp4"

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
        else:
            src_tag, clip_fn = s["clip"].split(":", 1)
            clip_p = (V03_CLIP_DIR if src_tag == "v03" else V02_CLIP_DIR) / clip_fn
            raw_frames = decode_video_frames(clip_p)

            ls_mp4 = LIP_OUT_DIR / f"sync_{sid}.mp4"
            ls_dur = s.get("lipsync_dur_sec")

            if ls_dur is not None and ls_mp4.exists():
                ls_raw = decode_video_frames(ls_mp4)
                pos_base_all = [eval_curve(k / FPS_FINAL, s["curve"]) for k in range(n_frames)]
                rgb_base = rife.render_positions(raw_frames, pos_base_all)
                if abs(ls_dur - dur) < 0.15:
                    # Whole shot lip-synced @ 25fps -> resample smoothly via RIFE to 30fps & feather outer 36px border!
                    positions_30 = [(k / FPS_FINAL) * FPS_LIPSYNC for k in range(n_frames)]
                    rgb_ls = rife.render_positions(ls_raw, positions_30)
                    for k in range(n_frames):
                        clean_f = (rgb_ls[k].astype(np.float32) * inner_mask + rgb_base[k].astype(np.float32) * (1.0 - inner_mask)).astype(np.uint8)
                        frames_rgb.append(clean_f)
                else:
                    # Hybrid shot (05c: lip-synced 0..7.12s + RIFE hangup 7.12..8.40s with seamless 0.15s crossfade!)
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
                positions_30 = [eval_curve(k / FPS_FINAL, s["curve"]) for k in range(n_frames)]
                frames_rgb = rife.render_positions(raw_frames, positions_30)

        subs = s["subs"]
        crt_off_sec = (s["crt_off_ms"] / 1000.0) if s.get("crt_off_ms") is not None else None
        jolt_sec = (s["jolt_ms"] / 1000.0) if s.get("jolt_ms") is not None else None
        gun_sec = (s["gunflash_ms"] / 1000.0) if s.get("gunflash_ms") is not None else None
        zoom_pct = float(s.get("zoom_pct") or 0.0)

        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS_FINAL), "-i", "-",
            "-i", str(wav_p),
            "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2",
            "-t", f"{dur:.3f}", str(out_seg),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for k, arr in enumerate(frames_rgb):
            t_now = k / FPS_FINAL
            prog = k / max(1, n_frames - 1)
            if crt_off_sec is not None and t_now >= crt_off_sec:
                arr = apply_crt_turnoff_effect(arr, t_now - crt_off_sec)
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

        for a, b, txt in subs:
            srt_entries.append((t_cursor + a, t_cursor + b, txt))
        seg_files.append(out_seg)
        t_cursor += dur
        print(f"[assembled v0.4 @ {FPS_FINAL}fps] shot_{sid:8s} ({dur:.2f}s)")

    concat_txt = ROOT / "concat_v04.txt"
    concat_txt.write_text("".join(f"file '{p}'\n" for p in seg_files), encoding="utf-8")
    raw_mp4 = OUT_DIR / "pilot_v04_raw.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(raw_mp4)],
        check=True,
    )

    # Archive SRT ONLY inside v04_pilot/out/ and DELETE same-basename sidecar .srt files next to MP4s!
    srt_text = "".join(f"{i}\n{format_srt_ts(a)} --> {format_srt_ts(b)}\n{txt}\n\n" for i, (a, b, txt) in enumerate(srt_entries, 1))
    ARCHIVE_SRT.write_text(srt_text, encoding="utf-8")
    for legacy_srt in (LEGACY_SRT_V03, LEGACY_SRT_V02):
        if legacy_srt.exists():
            legacy_srt.unlink()
            print(f"[removed duplicate sidecar] {legacy_srt}")

    vf = "noise=alls=4:allf=t+u,vignette=PI/6,eq=contrast=1.04:saturation=0.92:gamma=0.98"
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", str(raw_mp4),
            "-vf", vf,
            "-r", str(FPS_FINAL),
            "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-sn", "-movflags", "+faststart",
            str(FINAL_MP4_V03),
        ],
        check=True,
    )
    FINAL_MP4_V02.write_bytes(FINAL_MP4_V03.read_bytes())
    print(f"[V0.4 FINAL READY] {FINAL_MP4_V03} ({FINAL_MP4_V03.stat().st_size / (1024*1024):.2f} MB, {t_cursor:.1f}s @ {FPS_FINAL}fps)")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("prepare", "all"):
        prepare_v04()
    if mode in ("assemble", "all"):
        assemble_v04()
