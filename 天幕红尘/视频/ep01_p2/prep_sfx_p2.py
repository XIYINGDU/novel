#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build and audition realistic Foley effects for Ep01 Part 2 (1-5 & 1-6)."""

import array
import math
import os
import random
import subprocess
from pathlib import Path

from pydub import AudioSegment

os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")

SFX_DIR = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v02_pilot/real_sfx")
P2_SFX = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/ep01_p2/sfx")
P2_SFX.mkdir(parents=True, exist_ok=True)
SR = 48000


def ffmpeg_af(seg: AudioSegment, af: str) -> AudioSegment:
    raw_in = seg.set_frame_rate(SR).set_channels(1).set_sample_width(2).raw_data
    out_raw = subprocess.check_output(
        ["ffmpeg", "-v", "error", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-", "-af", af, "-f", "s16le", "-ar", str(SR), "-ac", "1", "-"],
        input=raw_in,
    )
    return AudioSegment(out_raw, frame_rate=SR, sample_width=2, channels=1)


def load_wav(fn: str) -> AudioSegment:
    return AudioSegment.from_file(SFX_DIR / fn).set_frame_rate(SR).set_channels(1).set_sample_width(2)


def pcm_to_seg(samples: list[float]) -> AudioSegment:
    arr = array.array("h", (max(-32767, min(32767, int(x * 32767.0))) for x in samples))
    return AudioSegment(arr.tobytes(), frame_rate=SR, sample_width=2, channels=1)


def synth_glass_shatter_and_spill() -> AudioSegment:
    """Grounded glass tumbler knocked off wooden table -> tumble thud + multi-shard crystal tinkle + water splash."""
    rng = random.Random(19910825)
    bump = ffmpeg_af(load_wav("wood_knock.wav")[35:190].fade_out(60), "highpass=f=120:poles=2,lowpass=f=2200:poles=2")
    bump = bump.apply_gain(-12.0 - bump.max_dBFS)

    # Glass initial crack + 7 small shard clinks settling across 420ms
    dur_g = 0.65
    n_g = int(SR * dur_g)
    buf = [0.0] * n_g
    hits = [
        (0.000, 0.55, [2180.0, 3420.0, 5190.0, 7420.0], 26.0),
        (0.032, 0.40, [2640.0, 4190.0, 6280.0], 34.0),
        (0.085, 0.25, [3150.0, 4920.0, 7100.0], 42.0),
        (0.145, 0.19, [2890.0, 4560.0], 48.0),
        (0.220, 0.14, [3780.0, 5810.0], 55.0),
        (0.310, 0.09, [4210.0, 6450.0], 64.0),
        (0.415, 0.05, [4850.0], 70.0),
    ]
    pi2 = 2.0 * math.pi
    for t0_s, amp, freqs, decay in hits:
        i0 = int(t0_s * SR)
        for k in range(i0, n_g):
            dt = (k - i0) / SR
            env = math.exp(-dt * decay)
            if env < 0.003:
                break
            val = 0.0
            for fi, f in enumerate(freqs):
                val += math.sin(pi2 * f * dt + fi * 0.7) / len(freqs)
            # tiny crisp transient noise burst right at impact
            if dt < 0.008:
                val += 0.6 * rng.gauss(0, 1) * (1.0 - dt / 0.008)
            buf[k] += amp * env * val

    glass = ffmpeg_af(pcm_to_seg(buf), "highpass=f=1450:poles=2,aecho=0.85:0.75:19|44:0.12|0.06")
    glass = glass.apply_gain(-8.5 - glass.max_dBFS)

    # Short crisp water splat (~280ms) right when half-full glass tips & breaks on wood floor
    splash_src = load_wav("rain_07.wav")[1320:1620].fade_in(6).fade_out(190)
    splash = ffmpeg_af(splash_src, "highpass=f=480:poles=2,lowpass=f=4400:poles=2")
    splash = splash.apply_gain(-13.0 - splash.max_dBFS)

    out = AudioSegment.silent(760, frame_rate=SR)
    out = out.overlay(bump, position=0).overlay(glass, position=40).overlay(splash, position=55)
    return out.fade_out(80)


def synth_handset_drop() -> AudioSegment:
    """Beige plastic corded handset slipping from palm & hitting table leg on cord."""
    drop_clack = ffmpeg_af(load_wav("phone_hangup_2a.wav")[15:310].fade_in(4).fade_out(65), "highpass=f=240:poles=2,lowpass=f=4200:poles=2")
    drop_clack = drop_clack.apply_gain(-9.0 - drop_clack.max_dBFS)
    bump2 = ffmpeg_af(load_wav("wood_knock.wav")[45:210].fade_out(60), "highpass=f=160:poles=2,lowpass=f=2600:poles=2")
    bump2 = bump2.apply_gain(-16.0 - bump2.max_dBFS)
    out = AudioSegment.silent(580, frame_rate=SR).overlay(drop_clack, position=140).overlay(bump2, position=265)
    return out


def main():
    g = synth_glass_shatter_and_spill()
    h = synth_handset_drop()
    g.export(P2_SFX / "glass_spill.wav", format="wav")
    h.export(P2_SFX / "handset_drop.wav", format="wav")
    aud = h + AudioSegment.silent(500, frame_rate=SR) + g
    scratch_p = Path("/Users/duxiying/.gemini/antigravity-cli/brain/a18da7f8-846f-4989-874d-c081bff5e532/scratch/p2_sfx_audition.mp3")
    aud.export(scratch_p, format="mp3", bitrate="192k")
    print(f"[sfx built] glass_spill={len(g)}ms handset_drop={len(h)}ms -> {scratch_p}")


if __name__ == "__main__":
    main()
