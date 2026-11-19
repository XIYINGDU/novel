#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage D-prep & Stage E Master Builder for Episode 1 Continuation (Scenes 1-5 & 1-6).

Usage:
  uv run --python 3.11 --with torch --with numpy --with pillow --with scipy --with pydub \
      python3 -u ep01_p2/build_ep01_p2.py prepare
  uv run --python 3.11 --with torch --with numpy --with pillow --with scipy --with pydub \
      python3 -u ep01_p2/build_ep01_p2.py assemble [--fast]
  ... all [--fast]
"""

import hashlib
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")

import numpy as np
from PIL import Image, ImageDraw
from pydub import AudioSegment

VID_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频")
V13_DIR = VID_ROOT / "v13_fixes"
P2_ROOT = VID_ROOT / "ep01_p2"
sys.path.insert(0, str(V13_DIR))

import build_v13 as bv13  # noqa: E402

sys.path.insert(0, str(VID_ROOT / "common"))
import segbuild as sb  # noqa: E402

SR = bv13.SR
W, H = bv13.W, bv13.H
FPS_FINAL = bv13.FPS_FINAL
FPS_LIPSYNC = bv13.FPS_LIPSYNC

AUD_IN = P2_ROOT / "audio"
SFX_CUSTOM = P2_ROOT / "sfx"
SCOUT_DIR = P2_ROOT / "scout_clips"
CLIP_DIR = P2_ROOT / "clips"
MIX_DIR = P2_ROOT / "audio_mix"
SHOT_DIR = P2_ROOT / "shots"
LS_IN_DIR = P2_ROOT / "lipsync_in"
LS_OUT_DIR = P2_ROOT / "lipsync_out"
OUT_DIR = P2_ROOT / "out"

SEG = sb.Seg(P2_ROOT, "p2")  # 目录与上面常量一致

META_PATH = P2_ROOT / "audio_meta_p2.json"
V13_FINAL_MP4 = VID_ROOT / "第01集_p1_1-1至1-4_v13.mp4"
P2_FINAL_MP4 = VID_ROOT / "第01集_p2_1-5至1-6_v3.mp4"  # v3: 21a/23/24a 返修 + -19.2 LUFS（2026-11-18）；v2 在 旧版/
COMBINED_FINAL_MP4 = VID_ROOT / "旧版" / "第01集_合片_1-1至1-6_v15.mp4"  # 已被 p3 合片取代


def load_p2_voice(fname: str) -> AudioSegment:
    p = AUD_IN / fname
    if not p.exists():
        raise FileNotFoundError(f"Missing ep01_p2 audio: {p}")
    return AudioSegment.from_file(p).set_frame_rate(SR).set_channels(1).set_sample_width(2)


def build_sfx_p2(kind: str) -> AudioSegment:
    if kind == "ring_short":
        r = bv13.load_real_wav("ring_04.wav")
        seg = bv13.ffmpeg_af(r[:460].fade_out(70), "highpass=f=320:poles=2,lowpass=f=4800:poles=2")
        return seg.apply_gain(-13.0 - seg.max_dBFS)
    if kind == "pickup":
        c = bv13.load_real_wav("phone_pickup_2.wav")
        seg = bv13.ffmpeg_af(c[:280].fade_out(40), "highpass=f=220,lowpass=f=5200")
        return seg.apply_gain(-12.5 - seg.max_dBFS)
    if kind == "handset_drop":
        return AudioSegment.from_file(SFX_CUSTOM / "handset_drop.wav").set_frame_rate(SR).set_channels(1)
    if kind == "glass_spill":
        return AudioSegment.from_file(SFX_CUSTOM / "glass_spill.wav").set_frame_rate(SR).set_channels(1)
    if kind == "cloth_quick":
        c = bv13.load_real_wav("cloth_1.wav")
        seg = bv13.ffmpeg_af(c[:420].fade_in(10).fade_out(90), "highpass=f=240,lowpass=f=3200")
        return seg.apply_gain(-22.0 - seg.max_dBFS)
    if kind == "cloth_slide":
        c = bv13.load_real_wav("cloth_2.wav")
        seg = bv13.ffmpeg_af(c[:950].fade_in(30).fade_out(140), "highpass=f=180,lowpass=f=2600")
        return seg.apply_gain(-24.0 - seg.max_dBFS)
    if kind == "body_thud":
        th = bv13.load_real_wav("wood_thud.wav")[:420].fade_in(5).fade_out(160)
        cl = bv13.load_real_wav("cloth_2.wav")[:380].fade_in(5).fade_out(140)
        th_f = bv13.ffmpeg_af(th, "highpass=f=45,lowpass=f=340:poles=2")
        cl_f = bv13.ffmpeg_af(cl, "highpass=f=140,lowpass=f=1800:poles=2")
        th_f = th_f.apply_gain(-6.5 - th_f.max_dBFS)
        cl_f = cl_f.apply_gain(-16.0 - cl_f.max_dBFS)
        return AudioSegment.silent(440, frame_rate=SR).overlay(cl_f, 0).overlay(th_f, 30)
    if kind == "er_switch":
        sw = bv13.load_real_wav("switch_1.wav")[:260].fade_out(50)
        seg = bv13.ffmpeg_af(sw, "highpass=f=350:poles=2,lowpass=f=6000:poles=2")
        return seg.apply_gain(-12.0 - seg.max_dBFS)
    if kind == "fist_tap":
        th = bv13.load_real_wav("wood_thud.wav")[20:220].fade_in(4).fade_out(90)
        seg = bv13.ffmpeg_af(th, "highpass=f=75,lowpass=f=420:poles=2")
        return seg.apply_gain(-19.5 - seg.max_dBFS)
    raise ValueError(f"Unknown p2 sfx: {kind}")


def make_p2_ambience(kind: str, dur_ms: int) -> AudioSegment:
    if kind == "ny_hospital":
        base = bv13.ffmpeg_af(bv13.make_ambience("moscow_room", dur_ms), "highpass=f=90,lowpass=f=520:poles=2")
        return base.apply_gain(-37.0 - base.dBFS)
    base = bv13.make_ambience("ny_day_room", dur_ms)
    return base.apply_gain(-38.5 - base.dBFS)


draw_corner_stamp = sb.draw_corner_stamp
find_split_pause_ms = sb.find_split_pause_ms


def build_p2_spec() -> tuple[list[dict], list[tuple[str, AudioSegment]]]:
    """Assemble exact 15-shot spec & audio stems matching Scenes 1-5 & 1-6 verbatim."""
    book = sb.ShotBook(SEG)
    specs, ls_stems, add_shot = book.specs, book.ls_stems, book.add

    # Shot 14: Hui listens on phone -> turns horrified (kug_15_panic_en_t2 = 4.48s)
    kug_panic = bv13.apply_telephone_earpiece(load_p2_voice("kug_15_panic_en_t2.mp3"), target_dbfs=-19.0, gentle=True)
    dur_14 = 5.05
    mix_14 = (
        make_p2_ambience("ny_day_room", int(dur_14 * 1000))
        .overlay(build_sfx_p2("ring_short"), position=20)
        .overlay(build_sfx_p2("pickup"), position=420)
        .overlay(kug_panic, position=540)
    )
    add_shot(
        "14", dur_14, "clip_14",
        [(0.0, 0.0), (0.65, 8.0), (2.2, 22.0), (3.8, 38.0), (dur_14, 48.0)],
        [(0.54, dur_14 - 0.12, "（电话）罗破产了！昨晚在莫斯科办公室开枪自杀了！")],
        mix_14, stamp="次日　1991年8月25日　纽约", fade_in=True,
    )

    # Shot 15: Hui screams '哥——!' -> handset drops on cord
    hui_15 = bv13.norm_voice(load_p2_voice("hui_15_v2_b.mp3"), -14.5)  # 1.12s "哥！"
    dur_15 = 2.40
    mix_15 = (
        make_p2_ambience("ny_day_room", int(dur_15 * 1000))
        .overlay(hui_15, position=180)
        .overlay(build_sfx_p2("handset_drop"), position=1320)
    )
    stem_15 = AudioSegment.silent(1500, frame_rate=SR).overlay(hui_15, position=180)
    add_shot(
        "15", dur_15, "clip_15",
        [(0.0, 0.0), (1.15, 16.0), (dur_15, 40.0)],
        [(0.15, 1.38, "哥——！")],
        mix_15, ls_stem=stem_15, ls_dur=1.45,
    )

    # Shot 16: Lin rushes out from kitchen & snatches dangling handset
    lin_16 = bv13.norm_voice(load_p2_voice("lin_16_ask_t1.mp3"), -14.5)  # 1.60s
    dur_16 = 2.55
    mix_16 = (
        make_p2_ambience("ny_day_room", int(dur_16 * 1000))
        .overlay(build_sfx_p2("cloth_quick"), position=120)
        .overlay(build_sfx_p2("pickup"), position=560)
        .overlay(lin_16, position=820)
    )
    stem_16 = AudioSegment.silent(int(dur_16 * 1000), frame_rate=SR).overlay(lin_16, position=820)
    add_shot(
        "16", dur_16, "clip_16",
        [(0.0, 0.0), (0.85, 22.0), (dur_16, 40.0)],
        [(0.80, dur_16 - 0.08, "喂？！到底怎么回事？！")],
        mix_16, ls_stem=stem_16, ls_dur=dur_16 - 0.05,
    )

    # Shot 17: Su hears leaked "开枪自杀、人没了" -> clutches sweater over chest (3.20s -> seamless cut into 18a!)
    kug_leak = bv13.apply_telephone_earpiece(load_p2_voice("kug_15_leak_en.mp3"), target_dbfs=-22.5, gentle=False)  # 2.88s
    su_gasp = bv13.norm_voice(load_p2_voice("su_17_v2_b.mp3")[:480].fade_out(80), -18.5)
    dur_17 = 3.20
    mix_17 = (
        make_p2_ambience("ny_day_room", int(dur_17 * 1000))
        .overlay(kug_leak, position=80)
        .overlay(su_gasp, position=1850)
        .overlay(build_sfx_p2("cloth_quick"), position=1950)
    )
    add_shot(
        "17", dur_17, "clip_17",
        [(0.0, 0.0), (1.3, 18.0), (dur_17, 48.0)],
        [(0.10, 2.80, "（电话漏音）开枪自杀……人没了！")],
        mix_17,
    )

    # Shot 18a: Start IS 17_end! Brisk gravity collapse backward + glass tumbler smashed spilling water
    dur_18a = 2.25
    mix_18a = (
        make_p2_ambience("ny_day_room", int(dur_18a * 1000))
        .overlay(build_sfx_p2("glass_spill"), position=1080)
        .overlay(build_sfx_p2("body_thud"), position=1180)
    )
    add_shot(
        "18a", dur_18a, "clip_18a",
        [(0.0, 0.0), (0.35, 3.0), (1.55, 34.0), (dur_18a, 40.0)],
        [],
        mix_18a,
    )

    # Shot 18b: Lin kneeling cradling unconscious Su screaming for pills/ambulance
    lin_18b = bv13.norm_voice(load_p2_voice("lin_18b_cry_t1.mp3"), -14.0)  # 3.68s
    dur_18b = 4.20
    mix_18b = (
        make_p2_ambience("ny_day_room", int(dur_18b * 1000))
        .overlay(build_sfx_p2("cloth_slide"), position=0)
        .overlay(lin_18b, position=260)
    )
    stem_18b = AudioSegment.silent(int(dur_18b * 1000), frame_rate=SR).overlay(lin_18b, position=260)
    add_shot(
        "18b", dur_18b, "clip_18b",
        [(0.0, 0.0), (dur_18b, 56.0)],
        [(0.25, dur_18b - 0.12, "妈——！慧娟！拿急救药！快叫救护车！！")],
        mix_18b, ls_stem=stem_18b, ls_dur=dur_18b - 0.08,
    )

    # Shot 19: Night hospital ER corridor -> red IN SURGERY sign snaps black OFF
    dur_19 = 2.15
    mix_19 = make_p2_ambience("ny_hospital", int(dur_19 * 1000)).overlay(build_sfx_p2("er_switch"), position=1200)
    add_shot(
        "19", dur_19, "clip_19",
        [(0.0, 0.0), (0.85, 6.0), (1.35, 22.0), (dur_19, 32.0)],
        [],
        mix_19, stamp="同日夜　纽约", fade_in=True,
    )

    # Shot 20: US ER Doctor exits, pulls down blue surgical mask, solemn silent head shake
    dur_20 = 3.10
    mix_20 = make_p2_ambience("ny_hospital", int(dur_20 * 1000)).overlay(build_sfx_p2("cloth_quick"), position=420)
    add_shot(
        "20", dur_20, "clip_20",
        [(0.0, 0.0), (1.35, 24.0), (dur_20, 48.0)],
        [],
        mix_20,
    )

    # Shot 21a: Hui slides helplessly down cold hospital wall weeping
    hui_21a = bv13.norm_voice(load_p2_voice("hui_21a_weep_t2.mp3"), -14.8)  # 3.68s
    dur_21a = 4.00
    mix_21a = (
        make_p2_ambience("ny_hospital", int(dur_21a * 1000))
        .overlay(build_sfx_p2("cloth_slide"), position=150)
        .overlay(hui_21a, position=180)
    )
    stem_21a = AudioSegment.silent(int(dur_21a * 1000), frame_rate=SR).overlay(hui_21a, position=180)
    add_shot(
        "21a", dur_21a, "clip_21a_v3s3",  # v3：首帧去笑 + AU 提示词（2026-11-18）
        [(0.0, 0.0), (1.6, 30.0), (dur_21a, 48.0)],
        [(0.18, dur_21a - 0.12, "一天工夫，哥没了，妈也没了！")],
        mix_21a, ls_stem=stem_21a, ls_dur=dur_21a - 0.08,
    )

    # Shot 21b: Tight low MCU Hui beating floor weakly crying
    hui_21b = bv13.norm_voice(load_p2_voice("hui_21b_weep_t2.mp3"), -14.8)  # 4.48s
    dur_21b = 4.75
    mix_21b = (
        make_p2_ambience("ny_hospital", int(dur_21b * 1000))
        .overlay(hui_21b, position=150)
        .overlay(build_sfx_p2("fist_tap"), position=1020)
        .overlay(build_sfx_p2("fist_tap"), position=2150)
    )
    stem_21b = AudioSegment.silent(int(dur_21b * 1000), frame_rate=SR).overlay(hui_21b, position=150)
    add_shot(
        "21b", dur_21b, "clip_21b",
        [(0.0, 0.0), (2.90, 38.0), (dur_21b, 64.0)],
        [(0.15, dur_21b - 0.12, "还欠着一百多万美金的债，咱们孤儿寡母怎么活啊？！")],
        mix_21b, ls_stem=stem_21b, ls_dur=2.45,
    )

    # Shot 22: Lin leans against cold wall biting lower lip -> locks jaw forcing tears back
    dur_22 = 2.85
    mix_22 = make_p2_ambience("ny_hospital", int(dur_22 * 1000)).overlay(build_sfx_p2("cloth_quick"), position=1350)
    add_shot(
        "22", dur_22, "clip_22",
        [(0.0, 0.0), (1.35, 24.0), (dur_22, 48.0)],
        [],
        mix_22,
    )

    # Shot 23: Lin bends & yanks sobbing Hui upright against hospital wall
    lin_23 = bv13.norm_voice(load_p2_voice("lin_23_iron_t2.mp3"), -14.5)  # 4.16s
    dur_23 = 4.55
    mix_23 = (
        make_p2_ambience("ny_hospital", int(dur_23 * 1000))
        .overlay(build_sfx_p2("cloth_quick"), position=250)
        .overlay(lin_23, position=280)
    )
    stem_23 = AudioSegment.silent(int(dur_23 * 1000), frame_rate=SR).overlay(lin_23, position=280)
    add_shot(
        "23", dur_23, "clip_23_v3s2",  # v3：慧娟改回长发圆领
        [(0.0, 0.0), (1.2, 24.0), (dur_23, 56.0)],
        [(0.28, dur_23 - 0.12, "别哭了！哭保不住曼哈顿的裕香阁饭店，更还不清债！")],
        mix_23, ls_stem=stem_23, ls_dur=dur_23 - 0.08,
    )

    # Shot 24a: Steely MCU Lin commanding news blackout & Aug 28 funeral
    lin_24a = bv13.norm_voice(load_p2_voice("lin_24a_plan_t1.mp3"), -14.5)  # 4.64s
    dur_24a = 4.95
    mix_24a = make_p2_ambience("ny_hospital", int(dur_24a * 1000)).overlay(lin_24a, position=160)
    stem_24a = AudioSegment.silent(int(dur_24a * 1000), frame_rate=SR).overlay(lin_24a, position=160)
    add_shot(
        "24a", dur_24a, "clip_24a_v3s3",  # v3：冷硬 AU 提示词
        [(0.0, 0.0), (dur_24a, 72.0)],
        [(0.16, dur_24a - 0.12, "听着，从现在起对外一律封锁死讯，妈的葬礼定在28号！")],
        mix_24a, ls_stem=stem_24a, ls_dur=dur_24a - 0.08,
    )

    # Shot 24b: Reverse OTS onto tear-rimmed stunned Hui listening (Lin VO -> NO LatentSync!)
    lin_24b = bv13.norm_voice(load_p2_voice("lin_24b_plan_t2.mp3"), -14.5)  # 7.52s
    split_s = find_split_pause_ms(lin_24b) / 1000.0
    dur_24b = 7.90
    mix_24b = make_p2_ambience("ny_hospital", int(dur_24b * 1000)).overlay(lin_24b, position=160)
    add_shot(
        "24b", dur_24b, "clip_24b",
        [(0.0, 0.0), (2.7, 36.0), (5.3, 68.0), (dur_24b, 80.0)],
        [
            (0.16, 0.16 + split_s - 0.05, "你马上给莫斯科的库格列夫回电话，"),
            (0.16 + split_s, dur_24b - 0.12, "求他务必在那边办完火化，27号把你哥的骨灰、遗书，"),
        ],
        mix_24b,
    )

    # Shot 24c: Final steely closer MCU Lin ('还有墙上挂着的那幅...' + '剩下的事交给我！') + held cold iron gaze fadeout
    lin_24c = bv13.norm_voice(load_p2_voice("lin_24c_plan_t1.mp3"), -14.5)  # 5.12s
    split_c = find_split_pause_ms(lin_24c, lo_ratio=0.58, hi_ratio=0.82) / 1000.0
    dur_24c = 5.95
    mix_24c = make_p2_ambience("ny_hospital", int(dur_24c * 1000)).overlay(lin_24c, position=160)
    stem_24c = AudioSegment.silent(int(dur_24c * 1000), frame_rate=SR).overlay(lin_24c, position=160)
    add_shot(
        "24c", dur_24c, "clip_24c",
        [(0.0, 0.0), (5.2, 68.0), (dur_24c, 80.0)],
        [
            (0.16, 0.16 + split_c - 0.05, "还有墙上挂着的那幅「见路不走」横幅一块儿带回纽约！"),
            (0.16 + split_c, 5.25, "剩下的事交给我！"),
        ],
        mix_24c, ls_stem=stem_24c, ls_dur=5.30, fade_out=True,
    )

    return specs, ls_stems


def resolve_p2_clip(clip_base: str, fast_mode: bool) -> Path:
    return sb.resolve_clip(SEG, clip_base, fast_mode)


def prepare(fast_mode: bool = False):
    specs, ls_stems = build_p2_spec()
    sb.prepare(SEG, specs, ls_stems, META_PATH, fast_mode=fast_mode)


def render_p2_shot_frames(s: dict, fast_mode: bool) -> list[np.ndarray]:
    return sb.render_shot_frames(SEG, s, fast_mode)


file_sha256 = sb.file_sha256


def assemble(fast_mode: bool = False):
    specs = json.loads(META_PATH.read_text(encoding="utf-8"))
    sb.assemble(SEG, specs, P2_FINAL_MP4, fast_mode=fast_mode,  # 合片改由 p3 统一拼 p1+p2+p3
                target_lufs=-19.2)  # A-MASTER-LOUDNESS：v2 为 -15.1，比 p1/p3 响 4 LU（defects loudness_mismatch）


if __name__ == "__main__":
    args = sys.argv[1:]
    fast = "--fast" in args
    pos = [a for a in args if not a.startswith("--")]
    mode = pos[0] if pos else "all"
    if mode in ("prepare", "all"):
        prepare(fast_mode=fast)
    if mode in ("assemble", "all"):
        assemble(fast_mode=fast)
