#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local Mac audio synthesis (edge-tts + Foley SFX) & 35mm cinema assembly for《天幕红尘》Ep01 v0.2 Pilot (1-1 to 1-4)."""

import array
import asyncio
import json
import math
import os
import random
import subprocess
import sys
import time
from pathlib import Path

os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")

import edge_tts
from PIL import Image, ImageDraw, ImageFont
from pydub import AudioSegment

ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v02_pilot")
STILL_DIR = ROOT / "stills"
CLIP_DIR = ROOT / "clips"
AUD_DIR = ROOT / "audio"
SFX_DIR = ROOT / "real_sfx"
SHOT_DIR = ROOT / "shots"
OUT_DIR = ROOT / "out"
MAC_DTMF_DIR = Path("/System/Library/Components/CoreAudio.component/Contents/SharedSupport/SystemSounds/telephony")
for d in (STILL_DIR, CLIP_DIR, AUD_DIR, SFX_DIR, SHOT_DIR, OUT_DIR):
    d.mkdir(parents=True, exist_ok=True)

FINAL_MP4 = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/第01集_开篇试片_v0.2.mp4")
FINAL_SRT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/第01集_开篇试片_v0.2.srt")

W, H, FPS = 1280, 720, 24
SR = 48000

# Historically accurate Aug 24, 1991 statement: Gorbachev resigning as General Secretary of the CPSU CC
# (NOT President of the USSR, which happened Dec 25, 1991).
TV_TEXT_RU = (
    "Я слагаю с себя полномочия Генерального секретаря Центрального Комитета КПСС. "
    "Центральный Комитет КПСС должен принять трудное, но честное решение о самороспуске. "
    "Судьбу республиканских компартий и местных партийных организаций определят они сами."
)

VOICES = {
    "叶子农": ("zh-CN-YunjianNeural", "-16%", "-10Hz"),
    "罗家明": ("zh-CN-YunyangNeural", "-10%", "-8Hz"),
    "罗家明_耳语": ("zh-CN-YunyangNeural", "-18%", "-12Hz"),
    "库格列夫": ("zh-CN-YunxiNeural", "+18%", "+6Hz"),
    "苏玉平": ("zh-TW-HsiaoChenNeural", "-18%", "-16Hz"),
    "电视": ("ru-RU-DmitryNeural", "-6%", "-8Hz"),
}

# 14 editing units mapping cleanly onto the 13 storyboard shots (with 05 split into 05a/05b & 12 into 12a/12b)
SHOTS = [
    {
        "id": "01",
        "scene": "1-1",
        "kind": "video",
        "amb": "paris_night",
        "min": 4.5,
        "events": [
            ("gap", 0.35),
            ("sfx", "footsteps_stone"),
            ("sfx", "thump_1"),
            ("gap", 1.15),
        ],
    },
    {
        "id": "02",
        "scene": "1-1",
        "kind": "video",
        "amb": "paris_night",
        "min": 5.2,
        "events": [
            ("gap", 0.25),
            ("sfx", "thump_2"),
            ("gap", 0.55),
            ("line", "叶子农", "还真他妈抬举我。", {"file": "line_02_3.mp3"}),
            ("gap", 0.35),
            ("sfx", "fall"),
            ("gap", 0.85),
        ],
    },
    {
        "id": "03",
        "scene": "card",
        "kind": "card",
        "amb": "silence",
        "min": 3.6,
        "text": ["一年前", "1991年8月24日夜　莫斯科"],
        "events": [],
    },
    {
        "id": "04",
        "scene": "1-2",
        "kind": "video",
        "amb": "moscow_street",
        "min": 4.6,
        "events": [
            ("gap", 0.45),
            ("sfx", "phone_moscow_ext"),
            ("gap", 0.45),
        ],
    },
    {
        "id": "05a",
        "scene": "1-2",
        "kind": "video",
        "amb": "moscow_room",
        "tv": True,
        "min": 7.5,
        "events": [
            ("sfx", "moscow_ring_pickup"),
            ("line", "罗家明", "我是罗。", {"file": "line_05a_1.mp3"}),
            (
                "line",
                "库格列夫",
                "罗！秘密股东协议里的五个高官已经抓了三个！另外两个高官公子傍晚跑去瑞士了！",
                {"phone": True, "file": "line_05a_2.mp3"},
            ),
        ],
    },
    {
        "id": "05b",
        "scene": "1-2",
        "kind": "video",
        "amb": "moscow_room",
        "tv": True,
        "min": 8.5,
        "events": [
            (
                "line",
                "库格列夫",
                "美国石油公司刚撤回了那150口油井的收购意向，明天一早检察院就来贴封条！罗，我那6万美金口头暗股怎么办？！",
                {"phone": True, "file": "line_05b_0.mp3"},
            ),
            ("gap", 0.35),
            ("line", "罗家明", "知道了，库格列夫。明天再说吧。", {"file": "line_05b_2.mp3"}),
            ("sfx", "hook"),
            ("gap", 0.55),
        ],
    },
    {
        "id": "06",
        "scene": "1-3",
        "kind": "video",
        "amb": "moscow_room",
        "tv": True,
        "tv_cut_at_end": True,
        "min": 5.5,
        "events": [
            ("gap", 1.5),
            ("line", "罗家明", "这个笨蛋！", {"file": "line_06_1.mp3"}),
            ("gap", 0.55),
            ("sfx", "tv_off"),
            ("gap", 0.9),
        ],
    },
    {
        "id": "07",
        "scene": "1-3",
        "kind": "video",
        "amb": "moscow_dead_quiet",
        "min": 5.6,
        "events": [
            ("gap", 0.25),
            ("sfx", "dtmf_ny"),
            ("gap", 0.30),
            ("sfx", "ringback_us"),
        ],
    },
    {
        "id": "08",
        "scene": "1-3",
        "kind": "video",
        "amb": "ny_day_room",
        "min": 4.8,
        "events": [
            ("gap", 0.15),
            ("sfx", "ny_ring_pickup"),
            ("gap", 0.20),
            ("line", "苏玉平", "喂？是家明吗？", {"file": "line_08_3.mp3"}),
            ("gap", 0.50),
        ],
    },
    {
        "id": "09",
        "scene": "1-3",
        "kind": "video",
        "amb": "moscow_dead_quiet",
        "min": 6.8,
        "events": [
            ("gap", 0.20),
            ("line", "苏玉平", "家明？是你吗？怎么不说话呀？", {"phone": True, "file": "line_09_1.mp3", "trim_ms": 4380}),
            ("sfx", "phone_line_silence"),
            ("sfx", "hook_soft"),
            ("gap", 0.80),
        ],
    },
    {
        "id": "10",
        "scene": "1-4",
        "kind": "video",
        "amb": "moscow_dead_quiet",
        "min": 6.8,
        "events": [
            ("gap", 0.20),
            ("sfx", "cylinder"),
            ("gap", 0.25),
            ("sfx", "pen"),
            ("line", "罗家明_耳语", "我撑不住了。我不能请求原谅，这不是可以原谅的事。", {"file": "line_10_4.mp3"}),
            ("gap", 0.40),
        ],
    },
    {
        "id": "11",
        "scene": "1-4",
        "kind": "video",
        "amb": "moscow_dead_quiet",
        "min": 6.2,
        "events": [
            ("gap", 0.50),
            ("line", "罗家明_耳语", "见路不走……可我现在能见到的只有一条死路，不走也得走了……", {"file": "line_11_1.mp3"}),
            ("gap", 0.60),
        ],
    },
    {
        "id": "12a",
        "scene": "1-4",
        "kind": "video",
        "amb": "moscow_dead_quiet",
        "min": 3.4,
        "events": [
            ("gap", 1.15),
            ("sfx", "gunshot_revolver"),
            ("gap", 0.20),
        ],
    },
    {
        "id": "12b",
        "scene": "1-4",
        "kind": "video",
        "amb": "silence",
        "min": 3.8,
        "events": [
            ("gap", 0.35),
            ("sfx", "drip_seq"),
            ("gap", 0.40),
        ],
    },
    {
        "id": "13",
        "scene": "end",
        "kind": "card",
        "amb": "silence",
        "min": 3.2,
        "text": ["《天幕红尘》", "第一集 · 开篇试片（v0.2 校准版）"],
        "events": [
            ("sfx", "drip_single"),
            ("gap", 2.2),
        ],
    },
]


def pcm_to_seg(samples: list[float]) -> AudioSegment:
    arr = array.array("h", (max(-32767, min(32767, int(x * 32767.0))) for x in samples))
    return AudioSegment(arr.tobytes(), frame_rate=SR, sample_width=2, channels=1)


def ffmpeg_af(seg: AudioSegment, af: str) -> AudioSegment:
    """Run multi-pole ffmpeg studio DSP filter chain on an AudioSegment in memory."""
    raw_in = seg.set_frame_rate(SR).set_channels(1).set_sample_width(2).raw_data
    cmd = [
        "ffmpeg", "-v", "error",
        "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-",
        "-af", af,
        "-f", "s16le", "-ar", str(SR), "-ac", "1", "-",
    ]
    out_raw = subprocess.check_output(cmd, input=raw_in)
    return AudioSegment(out_raw, frame_rate=SR, sample_width=2, channels=1)


_SFX_CACHE: dict[str, AudioSegment] = {}


def load_real_wav(fname: str) -> AudioSegment:
    if fname not in _SFX_CACHE:
        p = SFX_DIR / fname
        _SFX_CACHE[fname] = AudioSegment.from_file(p).set_frame_rate(SR).set_channels(1).set_sample_width(2)
    return _SFX_CACHE[fname]


def make_pstn_line_hiss(dur_ms: int, level_dbfs: float = -45.0) -> AudioSegment:
    """Subtle authentic 1991 analog landline transducer hiss + 60Hz hum."""
    rng = random.Random(19910824)
    n = int(SR * dur_ms / 1000.0)
    pi2 = 2.0 * math.pi
    buf = [0.02 * rng.gauss(0, 1) + 0.004 * math.sin(pi2 * 120.0 * (k / SR)) for k in range(n)]
    seg = ffmpeg_af(pcm_to_seg(buf), "highpass=f=380:poles=2,lowpass=f=2800:poles=2")
    return seg.apply_gain(level_dbfs - seg.dBFS) if seg.dBFS > -80 else seg


def apply_telephone_earpiece(seg: AudioSegment, target_dbfs: float) -> AudioSegment:
    """Authentic 1991 landline telephone receiver acoustic response (4-pole telecom bandpass + carbon/electret resonance + PSTN line hiss)."""
    af = (
        "highpass=f=430:poles=2,"
        "lowpass=f=2750:poles=2,"
        "equalizer=f=1120:t=q:w=1.3:g=5.5,"
        "equalizer=f=2050:t=q:w=1.8:g=3.0,"
        "acompressor=threshold=-22dB:ratio=3.5:attack=4:release=60"
    )
    filtered = ffmpeg_af(seg, af)
    if filtered.dBFS > -60:
        gain = min(target_dbfs - filtered.dBFS, -1.5 - filtered.max_dBFS)
        filtered = filtered.apply_gain(gain)
    line_bed = make_pstn_line_hiss(len(filtered), level_dbfs=-45.5)
    return line_bed.overlay(filtered)


def synth_sfx(name: str) -> AudioSegment:
    """Assemble authentic studio-recorded Foley WAVs with scene-matched acoustic space."""
    if name == "footsteps_stone":
        # 3 relaxed sneaker/leather steps descending Paris stone stairs, stopping abruptly on step 3
        fs = load_real_wav("footsteps_2.wav")[120:1620].fade_in(20).fade_out(60)
        fs = ffmpeg_af(fs, "highpass=f=90,aecho=0.8:0.75:28|58:0.16|0.08")
        return fs.apply_gain(-18.5 - fs.dBFS)

    if name in ("thump_1", "thump_2"):
        # Silenced sniper round from across Paris street hitting chest ("噗！" — suppressed bullet whip + visceral flesh/cloth punch)
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
        out = out.overlay(pffft, position=0)
        out = out.overlay(thwip, position=6)
        out = out.overlay(body_thud, position=14)
        out = out.overlay(cloth_hit, position=16)
        return ffmpeg_af(out, "alimiter=limit=0.92:attack=1:release=35")

    if name == "fall":
        # Knees buckling & body slumping onto stone steps
        scuff = load_real_wav("footsteps_2.wav")[1860:2220].fade_out(80).apply_gain(-8.0)
        knee_hit = ffmpeg_af(load_real_wav("wood_thud.wav")[480:830], "lowpass=f=650:poles=2").apply_gain(-5.5)
        torso_hit = ffmpeg_af(load_real_wav("wood_thud.wav")[780:1280], "lowpass=f=480:poles=2").apply_gain(-3.0)
        cloth = load_real_wav("cloth_1.wav")[1480:2250].apply_gain(5.0)
        out = AudioSegment.silent(920, frame_rate=SR)
        out = out.overlay(scuff, position=0)
        out = out.overlay(knee_hit, position=70)
        out = out.overlay(torso_hit, position=310)
        out = out.overlay(cloth, position=90)
        return out.fade_out(120)

    if name == "phone_moscow_ext":
        # Real electromechanical twin-bell desk telephone heard muffled from outside the 12th-floor Moscow window
        ring1 = load_real_wav("ring_01b.wav")[0:1320].fade_out(90)
        ring2 = load_real_wav("ring_01b.wav")[0:1320].fade_out(90)
        seq = ring1 + AudioSegment.silent(820, frame_rate=SR) + ring2
        muffled = ffmpeg_af(seq, "highpass=f=280:poles=2,lowpass=f=1350:poles=2,aecho=0.8:0.78:48|96:0.22|0.10")
        return muffled.apply_gain(-16.5 - muffled.max_dBFS)

    if name == "moscow_ring_pickup":
        # Match-cut inside Moscow office: crisp brass-bell ring abruptly cut off by lifting heavy handset
        ring_tail = load_real_wav("ring_01b.wav")[120:520].fade_out(18)
        ring_tail = ffmpeg_af(ring_tail, "aecho=0.8:0.75:22:0.14").apply_gain(-8.5 - ring_tail.max_dBFS)
        pick = load_real_wav("phone_pickup_1.wav")[80:520].fade_in(8).fade_out(50)
        pick = pick.apply_gain(-6.5 - pick.max_dBFS)
        out = AudioSegment.silent(920, frame_rate=SR)
        out = out.overlay(ring_tail, position=40)
        out = out.overlay(pick, position=410)
        return out

    if name == "hook":
        # Firmly pressing down the telephone cradle switch-hook ("直接伸手按断了电话簧片")
        hk = load_real_wav("phone_hook_btn.wav")[0:420].fade_out(50)
        return hk.apply_gain(-6.0 - hk.max_dBFS)

    if name == "tv_off":
        # Crisp mechanical push-button switch turning off 1991 CRT TV
        sw = load_real_wav("switch_1.wav")[15:280].fade_out(40)
        return sw.apply_gain(-6.5 - sw.max_dBFS)

    if name == "dtmf_ny":
        # Pressing physical push-buttons on desk phone + faint DTMF feedback leaking from handset earpiece
        digits = ["8", "1", "0", "1", "2", "1", "2", "5", "8"]
        kbd = load_real_wav("kbd_1.wav")
        key_slices = [
            kbd[35:145], kbd[235:345], kbd[485:595], kbd[635:745],
            kbd[935:1045], kbd[1135:1245], kbd[235:345], kbd[635:745], kbd[485:595],
        ]
        gaps_ms = [170, 230, 185, 250, 165, 160, 195, 170, 140]
        out = AudioSegment.silent(0, frame_rate=SR)
        for d, ks, g_ms in zip(digits, key_slices, gaps_ms):
            click = ks.fade_in(4).fade_out(25)
            click = click.apply_gain(-10.5 - click.max_dBFS)
            caf_p = MAC_DTMF_DIR / f"dtmf-{d}.caf"
            if caf_p.exists():
                tone = AudioSegment.from_file(caf_p).set_frame_rate(SR).set_channels(1)[:105].fade_in(8).fade_out(14)
                tone = ffmpeg_af(tone, "highpass=f=480:poles=2,lowpass=f=2600:poles=2")
                tone = tone.apply_gain(-21.5 - tone.max_dBFS)
                step_seg = AudioSegment.silent(max(len(click), len(tone) + 12), frame_rate=SR)
                step_seg = step_seg.overlay(click, position=0).overlay(tone, position=10)
            else:
                step_seg = click
            out += step_seg + AudioSegment.silent(max(45, g_ms - len(step_seg)), frame_rate=SR)
        return out

    if name == "ringback_us":
        # Real recorded analog landline calling ringback tone (two rings with authentic transatlantic line hiss)
        rb = load_real_wav("phone_calling_1b.wav")[0:3450].fade_in(25).fade_out(60)
        return rb.apply_gain(-13.5 - rb.max_dBFS)

    if name == "ny_ring_pickup":
        # Sunny Manhattan apartment Trimline phone ringing once in room, cut off mid-ring by lifting handset
        ny_ring = load_real_wav("ring_04.wav")[0:1180].fade_out(20)
        ny_ring = ny_ring.apply_gain(-9.5 - ny_ring.max_dBFS)
        pick = load_real_wav("phone_pickup_2.wav")[40:480].fade_in(6).fade_out(50)
        pick = pick.apply_gain(-6.5 - pick.max_dBFS)
        out = AudioSegment.silent(1580, frame_rate=SR)
        out = out.overlay(ny_ring, position=0)
        out = out.overlay(pick, position=1140)
        return out

    if name == "phone_line_silence":
        # 1.65s of aching silent transatlantic telephone line hiss while Luo Jiaming chokes back tears wordlessly
        return make_pstn_line_hiss(1650, level_dbfs=-44.5)

    if name == "hook_soft":
        # Extremely slow, gentle placement of plastic handset back onto cradle, severing the line
        gentle = load_real_wav("phone_hangup_2a.wav")[20:620].fade_in(10).fade_out(90)
        return gentle.apply_gain(-11.5 - gentle.max_dBFS)

    if name == "cylinder":
        # Real .38 Special revolver: sliding brass cartridge in + closing loaded cylinder + crisp ratchet index click
        ins = load_real_wav("rev_insert.wav")[6640:7060].fade_in(10).fade_out(40)
        ins = ins.apply_gain(-14.0 - ins.max_dBFS)
        close = load_real_wav("rev_close_cyl.wav")[740:1140].fade_in(8).fade_out(50)
        close = close.apply_gain(-8.0 - close.max_dBFS)
        spin = load_real_wav("rev_spin_cyl.wav")[540:1020].fade_in(8).fade_out(60)
        spin = spin.apply_gain(-10.5 - spin.max_dBFS)
        out = AudioSegment.silent(1320, frame_rate=SR)
        out = out.overlay(ins, position=0)
        out = out.overlay(close, position=430)
        out = out.overlay(spin, position=830)
        return out

    if name == "pen":
        # Real fountain pen nib writing two short lines on paper
        p = load_real_wav("writing_sig.wav")[40:1220].fade_in(20).fade_out(80)
        return p.apply_gain(-16.5 - p.max_dBFS)

    if name == "gunshot_revolver":
        # Mastered cinema handgun blast + real .38 Special revolver crack inside closed wood-paneled office + body slump onto desk
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
        out = out.overlay(indoor_blast, position=0)
        out = out.overlay(desk_slump, position=720)
        out = out.overlay(desk_rattle, position=745)
        out = out.overlay(cloth_slump, position=730)
        return out.fade_out(160)

    if name in ("drip_seq", "drip_single"):
        # Viscous blood droplets falling onto small puddle below desk edge: micro wet splash + subtle 28ms liquid plink
        rain_splash = load_real_wav("rain_07.wav")
        pi2 = 2.0 * math.pi

        def make_blood_drop(seed_off: int, pk_db: float) -> AudioSegment:
            sp = rain_splash[300 + seed_off : 338 + seed_off].fade_in(2).fade_out(18)
            sp = ffmpeg_af(sp, "highpass=f=900:poles=2,lowpass=f=4200:poles=2")
            sp = sp.apply_gain((pk_db - 4.0) - sp.max_dBFS)
            # Ultra-short 32ms natural liquid droplet impulse (subtle, dark, never cartoonish)
            n = int(SR * 0.036)
            f0 = 460.0 + (seed_off % 37)
            buf = [
                0.45 * math.sin(pi2 * (f0 + 115.0 * (k / n)) * (k / SR)) * math.exp(-(k / SR) * 115.0)
                for k in range(n)
            ]
            plink = pcm_to_seg(buf)
            plink = plink.apply_gain(pk_db - plink.max_dBFS)
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
        # Real cold wet-street midnight air (heavily low-passed rain_07 air bed, zero synthetic tone)
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


async def tts_save(text: str, who: str, out_path: Path):
    voice, rate, pitch = VOICES[who]
    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(out_path))


def stage_tts():
    tv_mp3 = AUD_DIR / "tv_gorbachev_19910824.mp3"
    if not tv_mp3.exists() or tv_mp3.stat().st_size < 1000:
        asyncio.run(tts_save(TV_TEXT_RU, "电视", tv_mp3))
    tv_bed = ffmpeg_af(
        AudioSegment.from_file(tv_mp3).set_frame_rate(SR).set_channels(1),
        "highpass=f=380:poles=2,lowpass=f=3100:poles=2,equalizer=f=1250:t=q:w=1.5:g=3.0",
    ) - 18.5

    meta = {}
    tv_cursor_ms = 0
    for s in SHOTS:
        sid = s["id"]
        fg = AudioSegment.silent(0, frame_rate=SR)
        subs = []
        tv_off_ms = None

        for idx, ev in enumerate(s["events"]):
            etype = ev[0]
            if etype == "gap":
                fg += AudioSegment.silent(int(ev[1] * 1000), frame_rate=SR)
            elif etype == "sfx":
                sfx_name = ev[1]
                if sfx_name == "tv_off":
                    tv_off_ms = len(fg) + 45
                fg += synth_sfx(sfx_name).set_frame_rate(SR)
            elif etype == "line":
                _, who, text, opt = ev
                mp3_name = opt.get("file") or f"line_{sid}_{idx}.mp3"
                mp3_p = AUD_DIR / mp3_name
                if not mp3_p.exists() or mp3_p.stat().st_size < 800:
                    for attempt in range(4):
                        try:
                            asyncio.run(tts_save(text, who, mp3_p))
                            if mp3_p.stat().st_size > 800:
                                break
                        except Exception as e:
                            print(f"[retry tts] {sid}_{idx}: {e}")
                            time.sleep(2)
                seg = AudioSegment.from_file(mp3_p).set_frame_rate(SR).set_channels(1)
                if opt.get("trim_ms"):
                    seg = seg[: int(opt["trim_ms"])].fade_out(90)
                if opt.get("phone"):
                    # Authentic 1991 telephone receiver earpiece sound
                    target_dbfs = -19.5 if who == "库格列夫" else -21.0
                    seg = apply_telephone_earpiece(seg, target_dbfs=target_dbfs)
                else:
                    target_dbfs = -18.0 if "耳语" in who else -17.0
                    if seg.dBFS > -60:
                        gain_needed = target_dbfs - seg.dBFS
                        max_safe_gain = -1.2 - seg.max_dBFS
                        seg = seg.apply_gain(min(gain_needed, max_safe_gain + 2.5))
                t_start = len(fg) / 1000.0
                pad_after = 60 if (sid == "09" and opt.get("phone")) else 200
                fg += seg + AudioSegment.silent(pad_after, frame_rate=SR)
                t_end = (len(fg) - pad_after) / 1000.0
                clean_speaker = who.split("_")[0]
                sub_prefix = ""
                if clean_speaker in ("库格列夫", "苏玉平") and opt.get("phone"):
                    sub_prefix = "（电话）"
                subs.append((t_start, t_end, sub_prefix + text))

        dur_s = max(float(s["min"]), len(fg) / 1000.0 + 0.25)
        total_ms = int(round(dur_s * 1000))
        if len(fg) < total_ms:
            fg += AudioSegment.silent(total_ms - len(fg), frame_rate=SR)
        else:
            fg = fg[:total_ms]

        bed = make_ambience(s["amb"], total_ms)
        if s.get("tv"):
            needed_tv_ms = tv_off_ms if (s.get("tv_cut_at_end") and tv_off_ms is not None) else total_ms
            loops = tv_bed * ((tv_cursor_ms + needed_tv_ms) // len(tv_bed) + 2)
            tv_slice = loops[tv_cursor_ms : tv_cursor_ms + needed_tv_ms]
            tv_cursor_ms = (tv_cursor_ms + needed_tv_ms) % len(tv_bed)
            if s.get("tv_cut_at_end") and tv_off_ms is not None:
                # Room hum & TV broadcast cut sharply to dead quiet right when TV clicks off!
                quiet_tail = make_ambience("moscow_dead_quiet", total_ms - tv_off_ms)
                bed = bed[:tv_off_ms].overlay(tv_slice) + quiet_tail
            else:
                bed = bed.overlay(tv_slice)

        mixed = bed.overlay(fg)
        wav_p = AUD_DIR / f"shot_{sid}.wav"
        mixed.export(wav_p, format="wav")
        meta[sid] = {"dur": round(total_ms / 1000.0, 3), "subs": subs}
        print(f"[audio] shot_{sid}.wav  dur={meta[sid]['dur']:.2f}s  subs={len(subs)}")

    (ROOT / "audio_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    total_dur = sum(v["dur"] for v in meta.values())
    print(f"[audio done] Total pilot runtime = {total_dur:.1f}s ({total_dur/60:.2f} min)")


def load_cjk_font(size: int, serif: bool = True) -> ImageFont.FreeTypeFont:
    candidates = (
        [
            "/System/Library/Fonts/Supplemental/Songti.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/PingFang.ttc",
        ]
        if serif
        else [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/Supplemental/Songti.ttc",
        ]
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
    sizes = [50] + [32] * (len(lines) - 1)
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
    # Wrap long lines cleanly at major punctuation without leaving orphan trailing punctuation
    lines = []
    cur = ""
    n_txt = len(text)
    for idx_c, ch in enumerate(text):
        cur += ch
        rem = text[idx_c + 1 :].strip()
        # Only break if remaining text has real content (not just punctuation like '！' or '……')
        has_real_rem = any(c not in "，。！？；—… ”’）" for c in rem)
        if len(cur) >= 20 and ch in "，。！？；" and has_real_rem:
            lines.append(cur.strip())
            cur = ""
    if cur.strip():
        if len(cur) > 30 and not lines:
            # Find nearest comma/pause near middle, else midpoint
            mid = len(cur) // 2
            split_at = mid
            for off in range(10):
                for cand in (mid - off, mid + off):
                    if 4 < cand < len(cur) - 4 and cur[cand] in "，。！？；…":
                        split_at = cand + 1
                        break
                if split_at != mid:
                    break
            lines = [cur[:split_at].strip(), cur[split_at:].strip()]
        else:
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
        # Crisp cinema black outline + subtle drop shadow
        for dx in (-2, -1, 0, 1, 2):
            for dy in (-2, -1, 0, 1, 2):
                if dx or dy:
                    draw.text((x + dx, y + dy), ln, font=fnt, fill=(0, 0, 0, 220))
        draw.text((x, y), ln, font=fnt, fill=(244, 242, 236, 255))
    return Image.alpha_composite(out, ov).convert("RGB")


def decode_video_frames(mp4_path: Path) -> list[bytes]:
    cmd = [
        "ffmpeg", "-v", "error", "-i", str(mp4_path),
        "-vf", f"scale={W}:{H}:flags=lanczos",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"
    ]
    raw = subprocess.check_output(cmd)
    frame_sz = W * H * 3
    return [raw[i : i + frame_sz] for i in range(0, len(raw) - frame_sz + 1, frame_sz)]


def stage_assemble():
    meta = json.loads((ROOT / "audio_meta.json").read_text(encoding="utf-8"))
    seg_files = []
    srt_entries = []
    t_cursor = 0.0

    for s in SHOTS:
        sid = s["id"]
        dur = float(meta[sid]["dur"])
        n_frames = max(1, int(round(dur * FPS)))
        wav_p = AUD_DIR / f"shot_{sid}.wav"
        out_seg = SHOT_DIR / f"shot_{sid}.mp4"

        # Prepare base RGB frames for this shot
        frames_img: list[Image.Image] = []
        if s["kind"] == "card":
            card_png = STILL_DIR / f"card_{sid}.png"
            render_card_png(s["text"], card_png)
            base_im = Image.open(card_png).convert("RGB")
            for k in range(n_frames):
                fade = min(1.0, k / (FPS * 0.7), (n_frames - 1 - k) / (FPS * 0.7))
                if fade < 0.999:
                    frames_img.append(Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), base_im, max(0.0, fade)))
                else:
                    frames_img.append(base_im)
        else:
            clip_p = CLIP_DIR / f"clip_{sid}.mp4"
            still_id = "05" if sid == "05a" else sid
            still_p = STILL_DIR / f"still_{still_id}.png"
            if clip_p.exists() and clip_p.stat().st_size > 10000:
                raw_frames = decode_video_frames(clip_p)
                if sid == "09" and len(raw_frames) > 28:
                    # Trim strictly to frames 0..27 (pure glistening-eye silent grief before squint)
                    raw_frames = raw_frames[:28]
                # Probe source FPS
                probe = subprocess.check_output(
                    ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", str(clip_p)],
                    text=True,
                ).strip()
                num, den = (probe.split("/") + ["1"])[:2]
                src_fps = float(num) / max(1.0, float(den))
                src_dur = len(raw_frames) / max(1.0, src_fps)
                # Smooth slow-motion stretch (down to 0.58x) if shot audio is slightly longer than raw clip,
                # avoiding abrupt jumps; if still longer, gentle ping-pong tail.
                speed = max(0.55, min(1.0, src_dur / dur))
                base_indices = [
                    min(len(raw_frames) - 1, int(k * src_fps * speed / FPS))
                    for k in range(max(2, int(round(src_dur / speed * FPS))))
                ]
                pingpong = base_indices + base_indices[-2:0:-1]
                seq = []
                while len(seq) < n_frames:
                    seq.extend(base_indices if not seq else pingpong[len(base_indices):] or base_indices)
                for k in range(n_frames):
                    frames_img.append(Image.frombytes("RGB", (W, H), raw_frames[seq[k]]))
            else:
                # Fallback Ken Burns from keyframe if a clip is missing
                base_im = Image.open(still_p).convert("RGB").resize((W, H), Image.LANCZOS)
                for k in range(n_frames):
                    z = 1.0 + 0.06 * (k / max(1, n_frames - 1))
                    cw, ch = int(W / z), int(H / z)
                    x0, y0 = (W - cw) // 2, (H - ch) // 2
                    frames_img.append(base_im.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.BICUBIC))

        # Burn clean cinema subtitles directly onto frames using Pillow (no libass requirement!)
        subs = meta[sid]["subs"]
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
            active_txt = None
            for a, b, txt in subs:
                if a <= t_now <= b + 0.15:
                    active_txt = txt
                    break
            if active_txt:
                im = draw_subtitle_on_frame(im, active_txt)
            # Subtle fade-in on very first shot & fade-out before black cut in 02 / 12b
            if sid == "01" and k < int(FPS * 0.5):
                im = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), im, k / (FPS * 0.5))
            elif sid in ("02", "12b") and k > n_frames - int(FPS * 0.45):
                rem = max(0.0, (n_frames - 1 - k) / (FPS * 0.45))
                im = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), im, rem)
            proc.stdin.write(im.tobytes())
        proc.stdin.close()
        rc = proc.wait()
        if rc != 0:
            raise RuntimeError(f"ffmpeg failed on shot {sid}")

        for a, b, txt in subs:
            srt_entries.append((t_cursor + a, t_cursor + b, txt))
        seg_files.append(out_seg)
        t_cursor += dur
        print(f"[assembled] shot_{sid}.mp4  ({dur:.2f}s)")

    concat_txt = ROOT / "concat_list.txt"
    concat_txt.write_text("".join(f"file '{p}'\n" for p in seg_files), encoding="utf-8")
    raw_mp4 = OUT_DIR / "pilot_raw.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(raw_mp4)],
        check=True,
    )

    # Write standalone SRT
    with open(FINAL_SRT, "w", encoding="utf-8") as sf:
        for i, (a, b, txt) in enumerate(srt_entries, 1):
            sf.write(f"{i}\n{format_srt_ts(a)} --> {format_srt_ts(b)}\n{txt}\n\n")

    # Apply 35mm film grain, subtle anamorphic vignette & 1991 cinema color grade
    vf = "noise=alls=5:allf=t+u,vignette=PI/6,eq=contrast=1.04:saturation=0.92:gamma=0.98"
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", str(raw_mp4),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
            str(FINAL_MP4),
        ],
        check=True,
    )
    print(f"[FINAL READY] {FINAL_MP4} ({FINAL_MP4.stat().st_size / (1024*1024):.2f} MB, {t_cursor:.1f}s)")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "tts"
    if mode in ("tts", "all"):
        stage_tts()
    if mode in ("assemble", "all"):
        stage_assemble()
