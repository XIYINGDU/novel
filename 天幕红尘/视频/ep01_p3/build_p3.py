#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""第 01 集续段 p3（1-7 机场电话亭 + 1-8 摄影棚）成片。

  R="uv run --python 3.11 --with torch --with numpy --with pillow --with scipy --with pydub python3 -u"
  $R ep01_p3/build_p3.py plan            # 只排时间线：每镜时长、要几条续段、缺哪些（不渲染）
  $R ep01_p3/build_p3.py prepare         # 混音 + 25fps 口型输入 → lipsync_in.tar.gz（之后跑 common/lipsync.py）
  $R ep01_p3/build_p3.py assemble [--fast]
  $R ep01_p3/build_p3.py all [--fast]

时间线模型：台词放在全段时间轴上，可跨镜（画外/电话里续说）；每镜按素材切成若干「片」
（主镜 + 续段 _c1/_c2…，续段 = HD 末帧 I2V 续接，见 p3 下一步②）。单片最慢 1.3 倍速；
续段还没出时，主镜放慢/往返兜底并在 plan 里列为「需续段」（--fast 预览照样能看节奏）。
声音：同一空间全程一条 room tone（A-ROOM-TONE-CONTINUOUS）；1-7 对方声音一律走电话滤波；
口型 stem 只放画面内开口者（A-LIPSYNC-CLEAN-STEM）。
"""
from __future__ import annotations

import ast
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VID = HERE.parent
sys.path.insert(0, str(VID / "common"))
sys.path.insert(0, str(VID / "ep01_p2"))
sys.path.insert(0, str(VID.parent / "loop" / "tools"))

import segbuild as sb  # noqa: E402
from pydub import AudioSegment  # noqa: E402
from pydub.generators import Sine  # noqa: E402

bv13 = sb.bv13
import build_ep01_p2 as p2  # noqa: E402  只借音效（build_sfx_p2）

SR = sb.SR
SEG = sb.Seg(HERE, "p3", scout_name="scout")
AUD = HERE / "audio"
P3_FINAL_MP4 = VID / "第01集_p3_1-7至1-8_v2.mp4"  # v2: 整镜口型/8i 放大口型/8m 重出（2026-11-18）
PREV_SEGS = [VID / "第01集_p1_1-1至1-4_v13.mp4", VID / "第01集_p2_1-5至1-6_v3.mp4"]
COMBINED_MP4 = VID / "第01集_合片_1-1至1-8_v17.mp4"

CONT_FRAMES = 81                 # 续段一律 81 帧（5.06 s）
MAX_STRETCH = 1.3                # 单片最多放慢到 1.3 倍时长
_NF: dict[str, int] = {}


def n_frames(base: str, fast: bool) -> int:
    """素材真实帧数（各镜 33–81 帧不等）；续段还没出时按 CONT_FRAMES 算。"""
    key = f"{base}|{fast}"
    if key not in _NF:
        try:
            p = sb.resolve_clip(SEG, base, fast)
        except FileNotFoundError:
            return CONT_FRAMES
        import subprocess
        out = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries",
                              "stream=nb_read_packets", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout
        _NF[key] = int(out.strip() or CONT_FRAMES)
    return _NF[key]


def cap_s(frames: int) -> float:
    return frames / 16.0 * MAX_STRETCH
GAP = 0.32                       # 同一人两句之间

# ---------------------------------------------------------------- 台词文本（直接读 stageA 的字面量，不复制）
def _load_lines() -> dict[str, tuple[str, str]]:
    tree = ast.parse((HERE / "stageA_voices_p3.py").read_text(encoding="utf-8"))
    out: dict[str, tuple[str, str]] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "LINES":
            for fn, actor, _emo, text, _seed in ast.literal_eval(node.value):
                out[fn] = (actor, text)
    for node in tree.body:  # RETAKES 里新增的条目（表达式里有 LINES 引用，只取字面 list 部分）
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "RETAKES":
            right = node.value.right if isinstance(node.value, ast.BinOp) else node.value
            for fn, actor, _emo, text, _seed in ast.literal_eval(right):
                out[fn] = (actor, text)
    return out


LINES = _load_lines()
PICKS = {k: v["pick"] for k, v in json.loads((AUD / "picks.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}


def take(key: str) -> str:
    """台词键 → 选定的音频文件名（picks.json；没有候选的就是自身）。"""
    return PICKS.get(key, key)


# ---------------------------------------------------------------- 镜头表（与 分镜表.md 对应；clip = hd_plan 选定的 HD 名）
# cues: [(台词键, 前置停顿 s)]；split: (台词键, 比例) = 本镜在该句的气口处结束，后半句续到下一镜
# face: 画面内看得见嘴的人（只有 face == 说话人时进口型 stem）
SPEAKER_LOC = {"liang": "airport", "han": "airport", "dai": "corridor"}
PHONE_LOCS = {"airport", "corridor"}
PHONE_FROM = "7f"  # 7f 起电话接通，之后两地对方声音走听筒

SHOTS: list[dict] = [
    # ---- 1-7 机场出发大厅 / 电话亭 ⇄ 京都影视基地走廊
    dict(id="7a", clip="clip_s7a_s1", loc="airport", min=3.95, stamp="1991年8月27日下午　北京", fade_in=True),
    dict(id="7b", clip="clip_s7b_s2", loc="airport", min=3.0, sfx=[("pager", 0.45)]),
    dict(id="7c", clip="clip_s7c_s3", loc="airport", face="han", cues=[("han_7c", 0.25)], post=0.35),
    dict(id="7d", clip="clip_s7d_s1", loc="airport", min=3.9),
    dict(id="7e", clip="clip_s7e_s1", loc="airport", min=3.95, sfx=[("pickup", 1.1), ("dtmf", 1.5), ("ringback", 3.35)]),
    dict(id="7f", clip="clip_s7f_s2", loc="corridor", min=3.95, sfx=[("ring", 0.1), ("ring", 1.3), ("pickup", 2.5)]),
    dict(id="7g", clip="clip_s7g_s1", loc="airport", face="liang", cues=[("liang_7g", 0.2)]),
    dict(id="7h", clip="clip_s7h_s1", loc="corridor", face="dai", cues=[("dai_7h", 0.3)]),
    dict(id="7i", clip="clip_s7i_s2", loc="corridor", face="dai", cues=[("dai_7i", 0.45)], g=1.6),
    # 7j 怔住：先 1.2s 无声，之后戴梦岩在听筒里接着交代（原 7k 前半），他在听
    # s7j 重出 4 种子都在中段张 O 嘴（stunned 一词诱发）→ 选 s5，静音 stem 走 LatentSync 把嘴压闭（V-REPAIR-LOCAL-FIRST）；
    # 不出续段：无方向性的听电话脸，1.3 倍慢放 + 往回放看不出
    dict(id="7j", clip="clip_s7j_s5", loc="airport", face="liang", cues=[("dai_7k_a", 1.2)], post=0.4, ls_silent=True,
         g=1.3, no_cont=True),
    dict(id="7k", clip="clip_s7k_s1", loc="corridor", face="dai", cues=[("dai_7k_b", 0.3)]),
    dict(id="7l", clip="clip_s7l_s2", loc="airport", face="liang", cues=[("liang_7l_a", 0.25), ("liang_7l_b", 0.3)]),
    dict(id="7m", clip="clip_s7m_s1", loc="corridor", face="dai", cues=[("dai_7m_a", 0.35), ("dai_7m_b", 0.45)]),
    dict(id="7n", clip="clip_s7n_s1", loc="airport", face="liang", cues=[("liang_7n", 0.35)], min=3.95,
         sfx=[("hangup", 3.0)]),
    # ---- 1-8 摄影棚
    dict(id="8a", clip="clip_s8a_s1", loc="studio_out", min=4.4, stamp="稍后　京都影视基地", fade_in=True),
    dict(id="8b", clip="clip_s8b_s2", loc="studio_out", face="aying", cues=[("aying_8b", 0.3)]),
    dict(id="8c", clip="clip_s8c_s1", loc="studio", min=4.4),
    dict(id="8d", clip="clip_s8d_s1", loc="studio", min=3.8),
    dict(id="8e", clip="clip_s8e_s1", loc="studio", min=3.95),
    dict(id="8f", clip="clip_s8f_s1", loc="studio", min=3.3),
    dict(id="8g", clip="clip_s8g_s1", loc="studio", min=4.6, cues=[("director_8g", 0.4)]),
    dict(id="8h1", clip="clip_s8h1_s1", loc="studio", min=3.3),
    dict(id="8h2", clip="clip_s8h2_s1", loc="studio", min=3.8),
    dict(id="8i", clip="clip_s8i_s1", loc="studio", face="liang", cues=[("liang_8i", 0.3)]),
    dict(id="8j", clip="clip_s8j_s1", loc="studio", face="liang", cues=[("liang_8j_a", 0.25), ("liang_8j_b", 0.35)],
         split=("liang_8j_b", 0.42)),
    dict(id="8k", clip="clip_s8k_s2", loc="studio", face="dai", post=0.5),  # 梁画外续说债务明细，她翻到最后一页
    dict(id="8l1", clip="clip_s8l1_s2", loc="studio", face="dai", cues=[("dai_8l_a", 0.55)], split=("dai_8l_a", 0.16)),
    dict(id="8l2", clip="clip_s8l2_s1", loc="studio", face="dai", cues=[("dai_8l_b", 0.35)]),
    # 8m v2：s1 点烟时就开口、烟中途消失 → 重出 s5（点完烟夹指间到底），台词推到点完烟后（第 38 帧≈2.3s）
    dict(id="8m", clip="clip_s8m_s5", loc="studio", face="liang", cues=[("liang_8m", 2.4)]),
    dict(id="8n_dai", clip="clip_s8n_dai_s2", loc="studio", face="dai", cues=[("dai_8n", 0.35)]),
    dict(id="8n_liang", clip="clip_s8n_liang_s1", loc="studio", face="liang", cues=[("liang_8n", 0.3)]),
    dict(id="8o", clip="clip_s8o_s1", loc="studio", face="dai", cues=[("dai_8o", 0.4)]),
    dict(id="8p", clip="clip_s8p_s3", loc="studio", face="dai", cues=[("dai_8p", 0.6)], g=1.35),  # 声音轻下来：气声档
    dict(id="8q", clip="clip_s8q_s1", loc="studio", face="liang", cues=[("liang_8q", 0.4)], min=3.3, post=0.95,
         fade_out=True),
]

# 双人镜：只在画面一侧找脸（看首帧定，见 plan 输出的 roi_check 图）
ROI = {"8b": "left_0.50", "8i": "left_0.56"}  # 8b 阿英在左、梁在右；8i 梁在左、戴在右（2026-11-18 看首帧定）
DEFAULT_G = 1.65  # A-LIPSYNC-GUIDANCE-TIER 清晰吐字 1.6-1.8


# ---------------------------------------------------------------- 声音
_VCACHE: dict[str, AudioSegment] = {}


def voice(fn: str) -> AudioSegment:
    if fn not in _VCACHE:
        _VCACHE[fn] = AudioSegment.from_file(AUD / f"{fn}.mp3").set_frame_rate(SR).set_channels(1).set_sample_width(2)
    return _VCACHE[fn]


def room_bed(loc: str, dur_ms: int) -> AudioSegment:
    """每个空间一条连续底噪；按全段绝对时间切片，切回同一空间时底噪接得上。"""
    kind = {"airport": "p3_airport", "corridor": "p3_corridor", "studio": "p3_studio", "studio_out": "p3_studio_out"}[loc]
    base = bv13.make_ambience(kind, dur_ms)
    af, lvl = {
        "airport": ("highpass=f=70,lowpass=f=1900:poles=2,aecho=0.8:0.5:90|170:0.25|0.15", -35.5),  # 大厅：混响人声嗡
        "corridor": ("highpass=f=90,lowpass=f=900:poles=2", -41.0),
        "studio": ("highpass=f=95,lowpass=f=2600:poles=1,equalizer=f=180:t=q:w=1.2:g=5", -32.5),  # 鼓风机
        "studio_out": ("highpass=f=140,lowpass=f=3200:poles=1", -37.5),
    }[loc]
    bed = bv13.ffmpeg_af(base, af)
    return bed.apply_gain(lvl - bed.dBFS)


def sfx(kind: str) -> AudioSegment:
    if kind == "pager":  # 九十年代数字传呼机：三声短促高音
        b = Sine(2900).to_audio_segment(duration=85, volume=-24).fade_in(4).fade_out(10)
        gap = AudioSegment.silent(70, frame_rate=SR)
        return (b + gap + b + gap + b).set_frame_rate(SR).set_channels(1)
    if kind == "dtmf":
        d = Path(str(bv13.MAC_DTMF_DIR))
        out = AudioSegment.silent(0, frame_rate=SR)
        for ch in "8601234":  # 只是按键节奏，不对应真实号码
            k = AudioSegment.from_file(d / f"dtmf-{ch}.caf").set_frame_rate(SR).set_channels(1)[:110].fade_out(15)
            out += k.apply_gain(-27.0 - k.max_dBFS) + AudioSegment.silent(150, frame_rate=SR)
        return out
    if kind == "ringback":  # 听筒里的回铃音（只在 7e 尾巴露一点）
        t = (Sine(450).to_audio_segment(duration=900, volume=-34)).fade_in(20).fade_out(40).set_frame_rate(SR).set_channels(1)
        return bv13.ffmpeg_af(t, "highpass=f=300,lowpass=f=3000")
    if kind == "ring":
        return p2.build_sfx_p2("ring_short")
    if kind == "pickup":
        return p2.build_sfx_p2("pickup")
    if kind == "hangup":
        h = bv13.load_real_wav("phone_hangup_1.wav")[:520].fade_out(80)
        return h.apply_gain(-15.0 - h.max_dBFS)
    raise ValueError(kind)


def voiced(fn: str, actor: str, shot: dict) -> tuple[AudioSegment, bool]:
    """返回（处理后的声音, 是否电话音）。"""
    v = voice(fn)
    if actor == "director":  # 隔棚远场喊停
        far = bv13.ffmpeg_af(v, "highpass=f=200,lowpass=f=2600:poles=2,aecho=0.8:0.7:70|140:0.35|0.2")
        return far.apply_gain(-24.0 - far.dBFS), False
    on_call = shot["_after_call"] and shot["loc"] in PHONE_LOCS and actor in SPEAKER_LOC
    if on_call and SPEAKER_LOC[actor] != shot["loc"]:
        return bv13.apply_telephone_earpiece(v, target_dbfs=-21.5), True
    return bv13.norm_voice(v, -20.0), False


# ---------------------------------------------------------------- 字幕切卡
def cards(text: str, max_len: int = 18) -> list[str]:
    import re
    parts = [p for p in re.split(r"(?<=[。！？；])", text) if p.strip()]
    out: list[str] = []
    for p in parts:
        while len(p) > max_len:
            cut = max((p.rfind(c, 0, max_len + 1) for c in "，、——："), default=-1)
            cut = cut + 1 if cut > 4 else max_len
            out.append(p[:cut])
            p = p[cut:]
        if p:
            out.append(p)
    return [c.strip().rstrip("，、") for c in out if c.strip()]


# ---------------------------------------------------------------- 时间线
def build_timeline() -> tuple[list[dict], list[dict]]:
    """返回 (镜列表含绝对起止, 台词事件列表)。事件: {fn, actor, text, t0, t1, shot}"""
    t = 0.0
    events: list[dict] = []
    carry: dict | None = None  # 上一镜 split 出来、还没说完的那句
    after_call = False
    shots = []
    for sh in SHOTS:
        sh = dict(sh)
        after_call = after_call or sh["id"] == PHONE_FROM
        sh["_after_call"] = after_call
        sh["t0"] = t
        cursor = t
        if carry:  # 续说的后半句从镜头开头接着走
            cursor = carry["t1"]
            carry = None
        last_end = cursor
        end_override = None
        for key, pre in sh.get("cues", []):
            fn = take(key)
            actor, text = LINES[fn]
            dur = len(voice(fn)) / 1000.0
            st = max(cursor + (pre if cursor == t else GAP), t + pre)
            ev = dict(fn=fn, actor=actor, text=text, t0=st, t1=st + dur, shot=sh["id"])
            events.append(ev)
            cursor = last_end = ev["t1"]
            if sh.get("split") and sh["split"][0] == key:
                cut_ms = sb.find_split_pause_ms(voice(fn), lo_ratio=sh["split"][1] - 0.08, hi_ratio=sh["split"][1] + 0.12)
                end_override = st + cut_ms / 1000.0
                carry = ev
        if end_override is not None:
            sh["t1"] = end_override
        else:
            sh["t1"] = max(t + sh.get("min", 0.0), last_end + sh.get("post", 0.35))
        sh["dur"] = round(sh["t1"] - t, 3)
        sh["t1"] = t + sh["dur"]
        t = sh["t1"]
        shots.append(sh)
    return shots, events


def clip_exists(base: str, fast: bool) -> bool:
    try:
        sb.resolve_clip(SEG, base, fast)
        return True
    except FileNotFoundError:
        return False


def pieces_for(sh: dict, fast: bool) -> tuple[list[tuple[str, float, float, int]], list[str]]:
    """把一镜切成若干片 [(clip, 片起点, 片时长, 帧数)]，返回 (片, 缺的续段)。片时长按各片容量（帧数×1.3）摊。"""
    names, caps = [sh["clip"]], [cap_s(n_frames(sh["clip"], fast))]
    while sum(caps) < sh["dur"] - 1e-6 and not sh.get("no_cont"):
        names.append(f"{sh['clip']}_c{len(names)}")
        caps.append(cap_s(CONT_FRAMES))
    have = [names[0]]
    for nm in names[1:]:  # 续段必须连号（c2 依赖 c1 的末帧）
        if not clip_exists(nm, fast):
            break
        have.append(nm)
    missing = names[len(have):]
    nf = [n_frames(c, fast) for c in have]
    tot = sum(cap_s(f) for f in nf)
    out, t = [], 0.0
    for c, f in zip(have, nf):
        d = sh["dur"] * cap_s(f) / tot
        out.append((c, t, d, f))
        t += d
    return out, missing


def curve_for(d: float, frames: int, start: float = 0.0) -> list[tuple[float, float]]:
    last = float(frames - 1)
    if d <= cap_s(frames) + 1e-6:
        return [(0.0, start), (d, last)]
    # 兜底（缺续段）：1.3 倍慢放走到尾，再慢慢倒回去；只为预览节奏
    t_fwd = cap_s(frames)
    back = min(last * 0.85, (d - t_fwd) / t_fwd * last)
    return [(0.0, 0.0), (t_fwd, last), (d, last - back)]


def build_spec(fast: bool):
    shots, events = build_timeline()
    total_ms = int(round(shots[-1]["t1"] * 1000)) + 50
    beds = {loc: room_bed(loc, total_ms) for loc in {s["loc"] for s in shots}}
    book = sb.ShotBook(SEG, fast)
    missing_all: dict[str, list[str]] = {}
    lsjob = {"roi": {}, "guidance": {}, "default_g": DEFAULT_G, "steps": 20}

    for sh in shots:
        t0, t1 = sh["t0"], sh["t1"]
        ms0, ms1 = int(round(t0 * 1000)), int(round(t1 * 1000))
        mix = beds[sh["loc"]][ms0:ms1]
        stem = AudioSegment.silent(ms1 - ms0, frame_rate=SR)
        own_end = None
        subs: list[tuple[float, float, str]] = []
        for ev in events:
            if ev["t1"] <= t0 or ev["t0"] >= t1:
                continue
            a, phone = voiced(ev["fn"], ev["actor"], sh)
            off_ms = int(round((ev["t0"] - t0) * 1000))
            if off_ms < 0:
                a = a[-off_ms:]
                off_ms = 0
            mix = mix.overlay(a, position=off_ms)
            if sh.get("face") == ev["actor"]:  # 口型 stem：只放画内开口者的干声
                raw = bv13.norm_voice(voice(ev["fn"]), -20.0)
                raw = raw[max(0, int(round((t0 - ev["t0"]) * 1000))):]
                stem = stem.overlay(raw, position=off_ms)
                own_end = min(t1, ev["t1"]) - t0
            # 字幕：按字数把卡片摊在整句时长上，再截到本镜窗口
            cs = cards(ev["text"])
            n_chars = sum(len(c) for c in cs) or 1
            ct = ev["t0"]
            for c in cs:
                cd = (ev["t1"] - ev["t0"]) * len(c) / n_chars
                a0, b0 = max(ct, t0), min(ct + cd - 0.05, t1)
                if b0 - a0 > 0.25:
                    subs.append((round(a0 - t0, 3), round(b0 - t0, 3), ("（电话）" if phone else "") + c))
                ct += cd
        for kind, at in sh.get("sfx", []):
            mix = mix.overlay(sfx(kind), position=int(at * 1000))

        pcs, missing = pieces_for(sh, fast)
        if missing:
            missing_all[sh["id"]] = missing
        for i, (clip, p0, pd, nfr) in enumerate(pcs):
            pid = sh["id"] if i == 0 else f"{sh['id']}_c{i}"
            a_ms, b_ms = int(round(p0 * 1000)), int(round((p0 + pd) * 1000))
            p_subs = [(max(0.0, a - p0), min(pd, b - p0), txt) for a, b, txt in subs if b > p0 and a < p0 + pd]
            p_subs = [(round(a, 3), round(b, 3), x) for a, b, x in p_subs if b - a > 0.2]
            ls_stem, ls_dur = None, None
            if sh.get("ls_silent") and own_end is None:  # 不说话也走口型：静音 stem 把嘴压闭
                ls_dur, ls_stem = round(pd, 3), stem[a_ms:b_ms]
                lsjob["guidance"][pid] = sh.get("g", 1.3)
            elif own_end is not None and own_end > p0:
                ls_dur = round(min(pd, own_end - p0 + 0.35), 3)
                ls_stem = stem[a_ms:b_ms]
                lsjob["guidance"][pid] = sh.get("g", DEFAULT_G)
                if sh["id"] in ROI:
                    lsjob["roi"][pid] = ROI[sh["id"]]
            # 续段从 0 帧起（实测：起 1 帧接缝反而更跳 3.77 vs 2.4；无口型时 0 帧起接缝平滑 1.79）
            st = 0.0
            extra = None  # ls_fit 试过（首尾拉满），接缝不见好，不用；真因是口型分片各做各的
            book.add(pid, round(pd, 3), clip, curve_for(pd, nfr, st), p_subs, mix[a_ms:b_ms], ls_stem=ls_stem, ls_dur=ls_dur,
                     extra=extra,
                     stamp=sh.get("stamp") if i == 0 else None, fade_in=sh.get("fade_in", False) and i == 0,
                     fade_out=sh.get("fade_out", False) and i == len(pcs) - 1)
    return shots, book, missing_all, lsjob


def meta_path(fast: bool) -> Path:
    return HERE / f"audio_meta_p3_{'fast' if fast else 'master'}.json"


def plan(fast: bool):
    shots, events = build_timeline()
    print(f"{'镜':<9}{'起':>7}{'长':>7}  片数  缺续段")
    need_all = []
    for sh in shots:
        pcs, missing = pieces_for(sh, fast)
        need_all += missing
        print(f"{sh['id']:<9}{sh['t0']:7.2f}{sh['dur']:7.2f}  {len(pcs) + len(missing):>3}   {' '.join(missing)}")
    print(f"\n总长 {shots[-1]['t1']:.1f}s；需续段 {len(need_all)} 条：{need_all}")
    (HERE / "cont_plan.json").write_text(json.dumps(need_all, ensure_ascii=False, indent=1), encoding="utf-8")
    return need_all


def prepare(fast: bool = False):
    shots, book, missing, lsjob = build_spec(fast)
    if missing:
        print(f"[WARN] 缺续段，暂用慢放/往返兜底：{missing}", flush=True)
    (HERE / "lipsync_job.json").write_text(json.dumps(lsjob, ensure_ascii=False, indent=1), encoding="utf-8")
    sb.prepare(SEG, book.specs, book.ls_stems, meta_path(fast), fast_mode=fast)


def assemble(fast: bool = False):
    specs = json.loads(meta_path(fast).read_text(encoding="utf-8"))
    if fast and any("mix_sha256" not in s for s in specs):
        # Older fast manifests shared master WAV paths and may describe a previous edit.
        _, book, _, _ = build_spec(True)
        specs = book.specs
        meta_path(True).write_text(json.dumps(specs, ensure_ascii=False, indent=2), encoding="utf-8")
    out = sb.assemble(SEG, specs, P3_FINAL_MP4, fast_mode=fast, combine_with=PREV_SEGS, combined_mp4=COMBINED_MP4,
                      target_lufs=-19.2)
    if not fast:
        import hooks
        hooks.after_build("p3", "01", P3_FINAL_MP4)
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    fast = "--fast" in args
    pos = [a for a in args if not a.startswith("--")]
    mode = pos[0] if pos else "plan"
    if mode == "plan":
        plan(fast)
    if mode == "spec":  # 只重排时间线/混音/meta，不动 lipsync_in（口型已做好时用）
        _, book, missing, _ = build_spec(fast)
        meta_path(fast).write_text(json.dumps(book.specs, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[spec] {len(book.specs)} 片 → {meta_path(fast).name}；缺续段 {missing or '无'}")
    if mode in ("prepare", "all"):
        prepare(fast)
    if mode in ("assemble", "all"):
        assemble(fast)
