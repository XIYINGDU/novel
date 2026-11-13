#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v0.3 Zero-Flaw 48kHz Cinema Audio Mixer & 35mm Film Editor for《天幕红尘》Ep01 Opening Pilot."""

import array
import json
import math
import os
import random
import subprocess
import sys
from pathlib import Path

os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")

from PIL import Image, ImageDraw, ImageFont
from pydub import AudioSegment

V02_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v02_pilot")
ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v03_pilot")
STILL_DIR = ROOT / "stills"
CLIP_DIR = ROOT / "clips"
AUD_DIR = ROOT / "audio"
SHOT_DIR = ROOT / "shots"
OUT_DIR = ROOT / "out"
SFX_DIR = V02_ROOT / "real_sfx"
V02_AUD_DIR = V02_ROOT / "audio"
V02_CLIP_DIR = V02_ROOT / "clips"
MAC_DTMF_DIR = Path("/System/Library/Components/CoreAudio.component/Contents/SharedSupport/SystemSounds/telephony")

for d in (STILL_DIR, CLIP_DIR, AUD_DIR, SHOT_DIR, OUT_DIR):
    d.mkdir(parents=True, exist_ok=True)

FINAL_MP4_V03 = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/第01集_开篇试片_v0.3.mp4")
FINAL_SRT_V03 = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/第01集_开篇试片_v0.3.srt")
# Also update the canonical pilot path so either link plays the latest zero-flaw cut
FINAL_MP4_CANON = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/第01集_开篇试片_v0.2.mp4")
FINAL_SRT_CANON = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/第01集_开篇试片_v0.2.srt")

W, H, FPS = 1280, 720, 24
SR = 48000


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
    p = AUD_DIR / fname if (AUD_DIR / fname).exists() else (V02_AUD_DIR / fname)
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
        # Ultra-natural cinema intercut earpiece: preserves 100% of mother's warm vocal identity across 08b -> 09a
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
        # Soft rubber-sole sneaker steps on damp Paris stone steps + subtle cotton sweatshirt rustle (ZERO hard-heel click!)
        raw_step = load_real_wav("footsteps_4.wav")[20:1620].fade_in(25).fade_out(70)
        sole = ffmpeg_af(
            raw_step,
            "highpass=f=65,lowpass=f=440:poles=2,equalizer=f=135:t=q:w=1.2:g=3.2,aecho=0.8:0.72:24:0.09",
        )
        sole = sole.apply_gain(-20.5 - sole.dBFS)
        # Subtle damp rubber sole scuff + soft cotton cloth rustle on each of the 3 casual steps (30ms, 630ms, 1280ms)
        wet_src = load_real_wav("rain_07.wav")
        cloth_src = load_real_wav("cloth_1.wav")
        out = AudioSegment.silent(len(sole), frame_rate=SR).overlay(sole)
        for idx, pos_ms in enumerate((28, 628, 1278)):
            scuff = wet_src[400 + idx * 180 : 455 + idx * 180].fade_in(8).fade_out(28)
            scuff = ffmpeg_af(scuff, "highpass=f=320:poles=2,lowpass=f=1150:poles=2")
            scuff = scuff.apply_gain(-31.5 - scuff.dBFS)
            swish = cloth_src[1500 + idx * 140 : 1630 + idx * 140].fade_in(18).fade_out(45)
            swish = ffmpeg_af(swish, "highpass=f=250,lowpass=f=2200:poles=2")
            swish = swish.apply_gain(-32.5 - swish.dBFS)
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
        # Two muffled exterior 12th-floor rings + J-cut interior snatch-up right at end of Shot 04!
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
        rb = load_real_wav("phone_calling_1b.wav")[0:3350].fade_in(25).fade_out(60)
        return rb.apply_gain(-13.5 - rb.max_dBFS)

    if name == "ny_ring_pickup":
        ny_ring = load_real_wav("ring_04.wav")[0:1150].fade_out(20)
        ny_ring = ny_ring.apply_gain(-9.5 - ny_ring.max_dBFS)
        pick = load_real_wav("phone_pickup_2.wav")[40:480].fade_in(6).fade_out(50)
        pick = pick.apply_gain(-6.5 - pick.max_dBFS)
        out = AudioSegment.silent(1620, frame_rate=SR)
        return out.overlay(ny_ring, position=0).overlay(pick, position=1120)

    if name == "hook_soft":
        gentle = load_real_wav("phone_hangup_2a.wav")[20:620].fade_in(10).fade_out(90)
        return gentle.apply_gain(-11.0 - gentle.max_dBFS)

    if name == "cylinder":
        ins = load_real_wav("rev_insert.wav")[6640:7060].fade_in(10).fade_out(40)
        ins = ins.apply_gain(-13.5 - ins.max_dBFS)
        close = load_real_wav("rev_close_cyl.wav")[740:1140].fade_in(8).fade_out(50)
        close = close.apply_gain(-7.5 - close.max_dBFS)
        spin = load_real_wav("rev_spin_cyl.wav")[540:1020].fade_in(8).fade_out(60)
        spin = spin.apply_gain(-10.0 - spin.max_dBFS)
        out = AudioSegment.silent(1550, frame_rate=SR)
        return out.overlay(ins, position=80).overlay(close, position=580).overlay(spin, position=1020)

    if name == "pen":
        p = load_real_wav("writing_sig.wav")[40:1280].fade_in(20).fade_out(80)
        return p.apply_gain(-16.0 - p.max_dBFS)

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

    if name in ("drip_seq", "drip_single"):
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
        out = AudioSegment.silent(3000, frame_rate=SR)
        for pos_ms, s_off, pk_db in ((260, 0, -18.0), (1380, 120, -19.5), (2520, 260, -21.0)):
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
    """Find quietest pause near approx_ratio of an audio segment for seamless 2-shot cinema cutaways."""
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


def build_v03_timeline_and_audio():
    """Build 21 strictly forward-playing cinema shots (ZERO ping-pong loops, ZERO sound-image mismatches)."""
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

    # Pre-load & process key multi-shot dialogue tracks (unified Chinese dialogue + gentle matched mother voice)
    ye_line = norm_voice(load_voice_mp3("line_02_3.mp3"), -17.0)
    luo_05a = norm_voice(load_voice_mp3("line_05a_1.mp3"), -17.0)
    kug_1 = apply_telephone_earpiece(load_voice_mp3("line_05a_2.mp3"), -18.8, gentle=False)
    kug_2 = apply_telephone_earpiece(load_voice_mp3("line_05b_0.mp3"), -18.8, gentle=False)
    luo_05c = norm_voice(load_voice_mp3("line_05b_2.mp3"), -17.0)
    luo_06 = norm_voice(load_voice_mp3("line_06_1.mp3"), -17.0)
    # Slice BOTH mother lines from ONE single continuous VoxCPM2 take (su_continuous_2.mp3) -> 100% identical voice!
    su_full = load_voice_mp3("su_continuous_2.mp3")
    su_08 = norm_voice(su_full[:2420].fade_out(60), -17.3)
    su_09 = apply_telephone_earpiece(su_full[2780:].fade_in(30).fade_out(90), -17.6, gentle=True)
    luo_10 = norm_voice(load_voice_mp3("line_10_4.mp3"), -18.0)
    luo_11 = norm_voice(load_voice_mp3("line_11_1.mp3"), -18.0)

    # Split Kuglev's two Chinese phone bursts & Luo's two monologues cleanly across cutaways!
    k1_split = find_split_silence_ms(kug_1, 0.56, 800)
    kug_1a, kug_1b = kug_1[:k1_split], kug_1[k1_split:]

    k2_split = find_split_silence_ms(kug_2, 0.70, 800)
    kug_2a, kug_2b = kug_2[:k2_split], kug_2[k2_split:]

    l10_split = find_split_silence_ms(luo_10, 0.30, 900)
    luo_10a, luo_10b = luo_10[:l10_split], luo_10[l10_split:]

    l11_split = find_split_silence_ms(luo_11, 0.50, 1200)
    luo_11a, luo_11b = luo_11[:l11_split], luo_11[l11_split:]

    shots_spec = []

    def reg(sid: str, clip_src: str, kind: str, fg: AudioSegment, amb: str, subs: list, tv=False, tv_cut_ms=None, fade_in=False, fade_out=False, crt_off_ms=None, card_lines=None):
        total_ms = len(fg)
        bed = make_ambience(amb, total_ms)
        if tv:
            bed = add_tv(bed, cutoff_ms=tv_cut_ms)
        mixed = bed.overlay(fg)
        wav_p = AUD_DIR / f"shot_{sid}.wav"
        mixed.export(wav_p, format="wav")
        shots_spec.append(
            {
                "id": sid,
                "clip": clip_src,
                "kind": kind,
                "dur": round(total_ms / 1000.0, 3),
                "subs": subs,
                "fade_in": fade_in,
                "fade_out": fade_out,
                "crt_off_ms": crt_off_ms,
                "card_lines": card_lines,
            }
        )
        print(f"[audio v0.3] shot_{sid:8s} dur={total_ms/1000:5.2f}s  clip={clip_src}")

    # --- 1-1 Paris Cold Open ---
    # 01: Walking down restaurant steps facing dense-window building across street -> 1st silenced bullet hits
    fg01 = AudioSegment.silent(300, frame_rate=SR) + synth_sfx("footsteps_stone") + synth_sfx("thump_1") + AudioSegment.silent(950, frame_rate=SR)
    reg("01", "v03:clip_01_v3.mp4", "video", fg01, "paris_night", [], fade_in=True)

    # 02a: Chest macro below collarbone -> 2nd silenced bullet hits, blood spreads, hand touches chest
    fg02a = AudioSegment.silent(220, frame_rate=SR) + synth_sfx("thump_2") + AudioSegment.silent(420, frame_rate=SR) + ye_line[:650] + AudioSegment.silent(150, frame_rate=SR)
    reg("02a", "v03:clip_02a_v3.mp4", "video", fg02a, "paris_night", [])

    # 02b: Low-angle stone steps knees buckling -> VO "还真他妈抬举我。" -> heavy collapse -> HARD CUT TO BLACK!
    ye_rem = ye_line[650:]
    fg02b = ye_rem + AudioSegment.silent(180, frame_rate=SR) + synth_sfx("fall") + AudioSegment.silent(120, frame_rate=SR)
    reg("02b", "v03:clip_02b_v3.mp4", "video", fg02b, "paris_night", [(0.0, len(ye_rem) / 1000.0, "还真他妈抬举我。")], fade_out=False)

    # 03: Time Card (Silent black hard-cut entry!)
    reg("03", "", "card", AudioSegment.silent(3400, frame_rate=SR), "silence", [], card_lines=["一年前", "1991年8月24日夜　莫斯科"])

    # --- 1-2 Moscow Midnight Street & 12F Office Crisis Call (English + Chinese Subtitles) ---
    # 04: Exterior 12F lone lit window + muffled twin-bell phone + J-cut interior pickup at tail!
    fg04 = AudioSegment.silent(450, frame_rate=SR) + synth_sfx("phone_moscow_jcut")
    reg("04", "v03:clip_04_v3.mp4", "video", fg04, "moscow_street", [])

    # 05a: Inside office (receiver already at ear from J-cut!) -> "This is Luo." -> Kuglev part 1a
    t_luo_end = (150 + len(luo_05a)) / 1000.0
    t_k1a_s = t_luo_end + 0.15
    fg05a = AudioSegment.silent(150, frame_rate=SR) + luo_05a + AudioSegment.silent(150, frame_rate=SR) + kug_1a + AudioSegment.silent(80, frame_rate=SR)
    reg(
        "05a",
        "v02:clip_05a.mp4",
        "video",
        fg05a,
        "moscow_room",
        [(0.15, t_luo_end, "我是罗。"), (t_k1a_s, len(fg05a) / 1000.0, "（电话）罗！秘密股东协议里的五个高官已经抓了三个！")],
        tv=True,
    )

    # 05_ins1: Overflowing ashtray cutaway + blurred Gorbachev CRT TV -> Kuglev part 1b + Kuglev part 2a start
    fg05_i1 = kug_1b + AudioSegment.silent(140, frame_rate=SR)
    reg(
        "05_ins1",
        "v03:clip_05_ins1.mp4",
        "video",
        fg05_i1,
        "moscow_room",
        [(0.0, len(kug_1b) / 1000.0, "（电话）另外两个高官公子傍晚跑去瑞士了！")],
        tv=True,
    )

    # 05_ins2: 4-women NY '裕香阁' family photo frame cutaway -> Kuglev part 2a
    fg05_i2 = kug_2a + AudioSegment.silent(60, frame_rate=SR)
    reg(
        "05_ins2",
        "v03:clip_05_ins2.mp4",
        "video",
        fg05_i2,
        "moscow_room",
        [(0.0, len(kug_2a) / 1000.0, "（电话）美国石油公司刚撤回了那150口油井的收购意向，明天一早检察院就来贴封条！")],
        tv=True,
    )

    # 05c: Hand poised over telephone hook-switch -> Kuglev final plea -> Luo: "Got it, Kuglev. Let's talk tomorrow." -> presses hook switch!
    t_k2b_end = len(kug_2b) / 1000.0
    t_l05c_s = t_k2b_end + 0.25
    t_l05c_e = t_l05c_s + len(luo_05c) / 1000.0
    fg05c = kug_2b + AudioSegment.silent(250, frame_rate=SR) + luo_05c + AudioSegment.silent(120, frame_rate=SR) + synth_sfx("hook") + AudioSegment.silent(350, frame_rate=SR)
    reg(
        "05c",
        "v03:clip_05c_v3.mp4",
        "video",
        fg05c,
        "moscow_room",
        [
            (0.0, t_k2b_end, "（电话）罗，我那6万美金口头暗股怎么办？！"),
            (t_l05c_s, t_l05c_e, "知道了，库格列夫。明天再说吧。"),
        ],
        tv=True,
    )

    # --- 1-3 Window Smoke, Switching Off CRT TV & Wordless Call to Mother in NY ---
    # 06a: Window smoke & ash flick -> sideways cold glance -> "这个笨蛋！"
    t_06_s = 1.35
    fg06a = AudioSegment.silent(1350, frame_rate=SR) + luo_06 + AudioSegment.silent(550, frame_rate=SR)
    reg("06a", "v02:clip_06.mp4", "video", fg06a, "moscow_room", [(t_06_s, t_06_s + len(luo_06) / 1000.0, "这个笨蛋！")], tv=True)

    # 06b: Hand presses CRT TV power switch -> screen flashes to pitch black & room drops into dead silence!
    tv_click_ms = 920
    fg06b = AudioSegment.silent(tv_click_ms, frame_rate=SR) + synth_sfx("tv_off") + AudioSegment.silent(950, frame_rate=SR)
    reg("06b", "v03:clip_06b_v3.mp4", "video", fg06b, "moscow_room", [], tv=True, tv_cut_ms=tv_click_ms + 45, crt_off_ms=tv_click_ms + 45)

    # 07: Seated behind desk gazing at fixed 4-women family photo, pressing buttons & listening to US ringback
    fg07 = AudioSegment.silent(220, frame_rate=SR) + synth_sfx("dtmf_ny") + AudioSegment.silent(280, frame_rate=SR) + synth_sfx("ringback_us")
    reg("07", "v03:clip_07_v3.mp4", "video", fg07, "moscow_dead_quiet", [])

    # 08a: Sunny NY side table (water glass, pill box, invitation) -> Trimline phone rings & Su Yuping's hand lifts receiver!
    fg08a = AudioSegment.silent(120, frame_rate=SR) + synth_sfx("ny_ring_pickup") + AudioSegment.silent(120, frame_rate=SR)
    reg("08a", "v03:clip_08a_v3.mp4", "video", fg08a, "ny_day_room", [])

    # 08b: Su Yuping smiling warmly with receiver at ear -> "喂？是家明吗？"
    fg08b = AudioSegment.silent(220, frame_rate=SR) + su_08 + AudioSegment.silent(520, frame_rate=SR)
    reg("08b", "v02:clip_08.mp4", "video", fg08b, "ny_day_room", [(0.22, 0.22 + len(su_08) / 1000.0, "喂？是家明吗？")])

    # 09a: Tight close-up of Luo Jiaming in silent glistening-eyed grief -> Su Yuping earpiece voice + transatlantic line hiss
    fg09a = AudioSegment.silent(200, frame_rate=SR) + su_09 + make_pstn_line_hiss(1150, level_dbfs=-44.5)
    reg("09a", "v03:clip_09a_v3.mp4", "video", fg09a, "moscow_dead_quiet", [(0.20, 0.20 + len(su_09) / 1000.0, "（电话）家明？是你吗？怎么不说话呀？")])

    # 09b: Extreme close-up of trembling hand slowly cradling black receiver onto hook -> severs line into dead silence
    fg09b = make_pstn_line_hiss(1150, level_dbfs=-44.5) + synth_sfx("hook_soft") + AudioSegment.silent(850, frame_rate=SR)
    reg("09b", "v03:clip_09b_v3.mp4", "video", fg09b, "moscow_dead_quiet", [])

    # --- 1-4 Revolver Loading, Two-Line Suicide Note, '見路不走' & Gunshot ---
    # 10a: Loading brass cartridge into swung-open WWII revolver cylinder + closing/indexing cylinder + inner monologue start ("我撑不住了……")
    cyl = synth_sfx("cylinder")
    t_10a_vo = (200 + len(cyl) + 250) / 1000.0
    fg10a = AudioSegment.silent(200, frame_rate=SR) + cyl + AudioSegment.silent(250, frame_rate=SR) + luo_10a + AudioSegment.silent(150, frame_rate=SR)
    reg("10a", "v03:clip_10a_v3.mp4", "video", fg10a, "moscow_dead_quiet", [(t_10a_vo, t_10a_vo + len(luo_10a) / 1000.0, "我撑不住了……")])

    # 10b: Uncapped gold-nib fountain pen writing on white paper + inner monologue ("我不能请求原谅，这不是可以原谅的事。")
    pen_sfx = synth_sfx("pen")
    fg10b = AudioSegment.silent(300, frame_rate=SR) + luo_10b + AudioSegment.silent(550, frame_rate=SR)
    fg10b = fg10b.overlay(pen_sfx, position=120)
    reg("10b", "v03:clip_10b_v3.mp4", "video", fg10b, "moscow_dead_quiet", [(0.30, 0.30 + len(luo_10b) / 1000.0, "我不能请求原谅，这不是可以原谅的事。")])

    # 11a: Medium OTS looking up at pixel-locked '見路不走' scroll -> whispered monologue part 1
    fg11a = AudioSegment.silent(420, frame_rate=SR) + luo_11a + AudioSegment.silent(200, frame_rate=SR)
    reg("11a", "v03:clip_11a_v3.mp4", "video", fg11a, "moscow_dead_quiet", [(0.42, 0.42 + len(luo_11a) / 1000.0, "见路不走……可我现在能见到的，")])

    # 11b: Tight hollow-eyed close-up staring at wall -> whispered monologue part 2 ("只有一条死路……不走，也得走了……")
    fg11b = AudioSegment.silent(180, frame_rate=SR) + luo_11b + AudioSegment.silent(550, frame_rate=SR)
    reg("11b", "v03:clip_11b_v3.mp4", "video", fg11b, "moscow_dead_quiet", [(0.18, 0.18 + len(luo_11b) / 1000.0, "只有一条死路……不走，也得走了……")])

    # 12a: Slow ominous push-in on '見路不走' scroll -> thunderous indoor .38 revolver gunshot + body slumping onto desk!
    fg12a = AudioSegment.silent(1150, frame_rate=SR) + synth_sfx("gunshot_revolver") + AudioSegment.silent(200, frame_rate=SR)
    reg("12a", "v02:clip_12a.mp4", "video", fg12a, "moscow_dead_quiet", [])

    # 12b: Rim-lit vivid crimson blood dripping off mahogany desk corner + spotless white suicide note on phone behind
    fg12b = AudioSegment.silent(350, frame_rate=SR) + synth_sfx("drip_seq") + AudioSegment.silent(450, frame_rate=SR)
    reg("12b", "v03:clip_12b_v3.mp4", "video", fg12b, "silence", [], fade_out=True)

    # 13: Clean cinema title card (NO engineering version tag!)
    fg13 = synth_sfx("drip_single") + AudioSegment.silent(2400, frame_rate=SR)
    reg("13", "", "card", fg13, "silence", [], card_lines=["天 幕 红 尘"])

    (ROOT / "audio_meta_v03.json").write_text(json.dumps(shots_spec, ensure_ascii=False, indent=2), encoding="utf-8")
    tot = sum(x["dur"] for x in shots_spec)
    print(f"[v0.3 audio ready] {len(shots_spec)} shots, total runtime = {tot:.1f}s ({tot/60:.2f} min)")


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


def decode_video_frames(mp4_path: Path) -> list[bytes]:
    cmd = ["ffmpeg", "-v", "error", "-i", str(mp4_path), "-vf", f"scale={W}:{H}:flags=lanczos", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.check_output(cmd)
    frame_sz = W * H * 3
    return [raw[i : i + frame_sz] for i in range(0, len(raw) - frame_sz + 1, frame_sz)]


def apply_crt_turnoff_effect(im: Image.Image, dt_sec: float) -> Image.Image:
    """Authentic 1991 CRT phosphor collapse into dark room right when power switch clicks off."""
    if dt_sec < 0:
        return im
    dark_room = Image.new("RGB", (W, H), (4, 5, 7))
    if dt_sec < 0.08:
        # Brief horizontal white phosphor collapse line across center + rapid room darkening
        out = Image.blend(im, dark_room, min(0.92, dt_sec / 0.08 * 0.92)).copy()
        draw = ImageDraw.Draw(out)
        half_w = int(W * 0.28 * max(0.08, 1.0 - dt_sec / 0.08))
        cx, cy = int(W * 0.52), int(H * 0.46)
        draw.rectangle([cx - half_w, cy - 2, cx + half_w, cy + 2], fill=(220, 235, 255))
        return out
    return Image.blend(im, dark_room, 0.94)


def assemble_v03():
    shots_spec = json.loads((ROOT / "audio_meta_v03.json").read_text(encoding="utf-8"))
    seg_files = []
    srt_entries = []
    t_cursor = 0.0

    for s in shots_spec:
        sid = s["id"]
        dur = float(s["dur"])
        n_frames = max(1, int(round(dur * FPS)))
        wav_p = AUD_DIR / f"shot_{sid}.wav"
        out_seg = SHOT_DIR / f"shot_{sid}.mp4"

        frames_img: list[Image.Image] = []
        if s["kind"] == "card":
            card_png = STILL_DIR / f"card_{sid}.png"
            render_card_png(s["card_lines"], card_png)
            base_im = Image.open(card_png).convert("RGB")
            for k in range(n_frames):
                # Note: Shot 03 starts after 0.35s pure black silence following hard-cut from 02b!
                fade_in_f = FPS * 0.65
                fade_out_f = FPS * 0.70
                fade = min(1.0, max(0.0, (k - FPS * 0.25) / fade_in_f), (n_frames - 1 - k) / fade_out_f)
                frames_img.append(Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), base_im, max(0.0, fade)))
        else:
            src_tag, clip_fn = s["clip"].split(":", 1)
            clip_p = (CLIP_DIR if src_tag == "v03" else V02_CLIP_DIR) / clip_fn
            raw_frames = decode_video_frames(clip_p)
            # Director's frame-accurate trims to keep 100% clean action windows:
            if sid == "02b":
                raw_frames = raw_frames[:39]  # Pure collapse onto dark wet steps before tail lens-flare
            elif sid == "05_ins2":
                raw_frames = raw_frames[:44]  # Pure 4-women '裕香阁' portrait before camera tilts toward lamp bulb
            elif sid == "09a":
                raw_frames = raw_frames[:10]  # Stoic lip-sealed silent weeping (zero open-mouth grimace)
            elif sid == "09b":
                raw_frames = raw_frames[22::-1]  # Single monotonic downward lowering of handset onto cradle

            # Strictly monotonic single-direction frame mapping — NEVER ping-pong!
            for k in range(n_frames):
                prog = k / max(1, n_frames - 1)
                pos = prog * (len(raw_frames) - 1)
                idx_lo = min(len(raw_frames) - 1, int(pos))
                idx_hi = min(len(raw_frames) - 1, idx_lo + 1)
                frac = pos - idx_lo
                im_a = Image.frombytes("RGB", (W, H), raw_frames[idx_lo])
                if frac > 0.02 and idx_hi != idx_lo:
                    im_b = Image.frombytes("RGB", (W, H), raw_frames[idx_hi])
                    im_cur = Image.blend(im_a, im_b, frac)
                else:
                    im_cur = im_a
                if sid == "09a":
                    # Subtle 3.5% emotional slow push-in while lips remain pressed shut
                    z = 1.0 + 0.035 * prog
                    cw, ch = int(round(W / z)), int(round(H / z))
                    x0, y0 = (W - cw) // 2, (H - ch) // 2
                    im_cur = im_cur.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.Resampling.LANCZOS)
                frames_img.append(im_cur)

        subs = s["subs"]
        crt_off_sec = (s["crt_off_ms"] / 1000.0) if s.get("crt_off_ms") is not None else None
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
            "-i", str(wav_p),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2",
            "-t", f"{dur:.3f}", str(out_seg),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for k, im in enumerate(frames_img):
            t_now = k / FPS
            if crt_off_sec is not None and t_now >= crt_off_sec:
                im = apply_crt_turnoff_effect(im, t_now - crt_off_sec)
            active_txt = None
            for a, b, txt in subs:
                if a <= t_now <= b + 0.12:
                    active_txt = txt
                    break
            if active_txt:
                im = draw_subtitle_on_frame(im, active_txt)
            if s.get("fade_in") and k < int(FPS * 0.5):
                im = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), im, k / (FPS * 0.5))
            elif s.get("fade_out") and k > n_frames - int(FPS * 0.55):
                rem = max(0.0, (n_frames - 1 - k) / (FPS * 0.55))
                im = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), im, rem)
            proc.stdin.write(im.tobytes())
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg failed on shot {sid}")

        for a, b, txt in subs:
            srt_entries.append((t_cursor + a, t_cursor + b, txt))
        seg_files.append(out_seg)
        t_cursor += dur
        print(f"[assembled v0.3] shot_{sid:8s} ({dur:.2f}s)")

    concat_txt = ROOT / "concat_v03.txt"
    concat_txt.write_text("".join(f"file '{p}'\n" for p in seg_files), encoding="utf-8")
    raw_mp4 = OUT_DIR / "pilot_v03_raw.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(raw_mp4)], check=True)

    srt_text = "".join(f"{i}\n{format_srt_ts(a)} --> {format_srt_ts(b)}\n{txt}\n\n" for i, (a, b, txt) in enumerate(srt_entries, 1))
    FINAL_SRT_V03.write_text(srt_text, encoding="utf-8")
    FINAL_SRT_CANON.write_text(srt_text, encoding="utf-8")

    vf = "noise=alls=5:allf=t+u,vignette=PI/6,eq=contrast=1.04:saturation=0.92:gamma=0.98"
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", str(raw_mp4),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
            str(FINAL_MP4_V03),
        ],
        check=True,
    )
    # Sync canonical file too
    FINAL_MP4_CANON.write_bytes(FINAL_MP4_V03.read_bytes())
    print(f"[V0.3 FINAL READY] {FINAL_MP4_V03} ({FINAL_MP4_V03.stat().st_size / (1024*1024):.2f} MB, {t_cursor:.1f}s)")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("audio", "all"):
        build_v03_timeline_and_audio()
    if mode in ("assemble", "all"):
        assemble_v03()
