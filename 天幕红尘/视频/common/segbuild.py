#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""段落成片通用流水线（从 ep01_p2/build_ep01_p2.py 抽出，行为不变）。

一段 = 一个目录（clips/ scout_clips/ audio_mix/ shots/ lipsync_in/ lipsync_out/ out/）。
  book = ShotBook(seg); book.add(...)         # 每镜：时长、素材、时间曲线、字幕、混音、口型 stem
  prepare(seg, book.specs, book.ls_stems)     # 25fps RIFE 预变速 → lipsync_in.tar.gz（A-LIPSYNC-CLEAN-STEM）
  assemble(seg, specs, final_mp4)             # 30fps RIFE + 口型内框融合 + 字幕/角标 → 母带
依赖 v13_fixes/build_v13.py（RIFE、字幕、滤镜常量）。须用 uv 的 torch 环境跑（见 build_ep01_p2.py 头注释）。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tarfile
from dataclasses import dataclass, field
from pathlib import Path

os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", "")

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from pydub import AudioSegment  # noqa: E402

VID_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频")
sys.path.insert(0, str(VID_ROOT / "v13_fixes"))
import build_v13 as bv13  # noqa: E402

SR = bv13.SR
W, H = bv13.W, bv13.H
FPS_FINAL = bv13.FPS_FINAL
FPS_LIPSYNC = bv13.FPS_LIPSYNC


@dataclass
class Seg:
    root: Path
    tag: str  # 例 "p2"：concat_<tag>_master.txt、preview_ep01_<tag>_fast.mp4
    scout_name: str = "scout_clips"
    clip_dir: Path = field(init=False)
    scout_dir: Path = field(init=False)
    mix_dir: Path = field(init=False)
    shot_dir: Path = field(init=False)
    ls_in: Path = field(init=False)
    ls_out: Path = field(init=False)
    out_dir: Path = field(init=False)

    def __post_init__(self):
        r = Path(self.root)
        self.clip_dir, self.scout_dir = r / "clips", r / self.scout_name
        self.mix_dir, self.shot_dir, self.out_dir = r / "audio_mix", r / "shots", r / "out"
        self.ls_in, self.ls_out = r / "lipsync_in", r / "lipsync_out"
        for d in (self.mix_dir, self.shot_dir, self.ls_in, self.ls_out, self.out_dir):
            d.mkdir(parents=True, exist_ok=True)


def draw_corner_stamp(img: Image.Image, text: str, alpha_scale: float = 1.0) -> Image.Image:
    """Subtle top-left location/time stamp matching v0.13 typography without touching bottom subtitle zone."""
    if alpha_scale <= 0.01:
        return img
    rgba = img.convert("RGBA")
    overlay = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = bv13.load_cjk_font(24, serif=True)
    x, y = 44, 34
    a_fill = int(round(235 * alpha_scale))
    a_shd = int(round(170 * alpha_scale))
    draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, a_shd))
    draw.text((x, y), text, font=font, fill=(242, 238, 228, a_fill))
    return Image.alpha_composite(rgba, overlay).convert("RGB")


def find_split_pause_ms(seg: AudioSegment, lo_ratio: float = 0.40, hi_ratio: float = 0.62) -> int:
    lo = int(len(seg) * lo_ratio)
    hi = int(len(seg) * hi_ratio)
    best_ms = (lo + hi) // 2
    best_db = 999.0
    for ms in range(lo, hi, 30):
        db = seg[ms : ms + 70].dBFS
        if db < best_db:
            best_db = db
            best_ms = ms + 35
    return best_ms


class ShotBook:
    """逐镜登记：写 audio_mix/shot_<id>.wav，收集 spec 和口型 stem。"""

    def __init__(self, seg: Seg):
        self.seg = seg
        self.specs: list[dict] = []
        self.ls_stems: list[tuple[str, AudioSegment]] = []

    def add(self, sid: str, dur: float, clip_name: str, curve: list[tuple[float, float]],
            subs: list[tuple[float, float, str]], mix: AudioSegment, ls_stem: AudioSegment | None = None,
            ls_dur: float | None = None, stamp: str | None = None, fade_in: bool = False, fade_out: bool = False,
            extra: dict | None = None):
        total_ms = int(round(dur * 1000))
        if len(mix) < total_ms:
            mix = mix + AudioSegment.silent(total_ms - len(mix), frame_rate=SR)
        elif len(mix) > total_ms:
            mix = mix[:total_ms]
        mix = mix.fade_in(10).fade_out(14)
        mix.export(self.seg.mix_dir / f"shot_{sid}.wav", format="wav")
        if ls_stem is not None:
            stem_ms = int(round((ls_dur if ls_dur is not None else dur) * 1000))
            st = ls_stem[:stem_ms] if len(ls_stem) >= stem_ms else (ls_stem + AudioSegment.silent(stem_ms - len(ls_stem), frame_rate=SR))
            self.ls_stems.append((sid, st))
        self.specs.append({"id": sid, "dur": dur, "clip": clip_name, "curve": curve, "subs": subs,
                           "lipsync_dur_sec": ls_dur, "stamp": stamp, "fade_in": fade_in, "fade_out": fade_out, **(extra or {})})


def resolve_clip(seg: Seg, clip_base: str, fast_mode: bool) -> Path:
    if not fast_mode:
        cands = sorted(seg.clip_dir.glob(f"{clip_base}*.mp4"))
        if cands:
            return cands[0]
    cands = sorted(seg.scout_dir.glob(f"{clip_base}*.mp4"))
    if cands:
        return cands[0]
    if fast_mode:  # 没 Scout 直出 HD 的镜头（如 p3 7e/7n）：预览也用 HD
        cands = sorted(seg.clip_dir.glob(f"{clip_base}*.mp4"))
        if cands:
            return cands[0]
    raise FileNotFoundError(f"Missing video clip matching {clip_base} in {seg.clip_dir} or {seg.scout_dir}")


def prepare(seg: Seg, specs: list[dict], ls_stems: list[tuple[str, AudioSegment]], meta_path: Path,
            fast_mode: bool = False) -> Path:
    print(f"[prepare {seg.tag}] Mixing shot WAVs & preparing 25fps LatentSync inputs...", flush=True)
    meta_path.write_text(json.dumps(specs, ensure_ascii=False, indent=2), encoding="utf-8")
    stems_map = dict(ls_stems)
    rife = bv13.get_rife()
    for p in seg.ls_in.glob("*"):
        p.unlink()
    packed: list[Path] = []
    for s in specs:
        sid = s["id"]
        if s["lipsync_dur_sec"] is None:
            continue
        clip_p = resolve_clip(seg, s["clip"], fast_mode=fast_mode)
        raw_frames = bv13.decode_video_frames(clip_p)
        ls_dur = float(s["lipsync_dur_sec"])
        n25 = max(1, int(round(ls_dur * FPS_LIPSYNC)))
        pos25 = [bv13.eval_curve(k / FPS_LIPSYNC, s["curve"]) for k in range(n25)]
        frames25 = rife.render_positions(raw_frames, pos25)
        vid_out = seg.ls_in / f"vid_{sid}.mp4"
        bv13.encode_mp4_no_audio(frames25, vid_out, FPS_LIPSYNC)
        wav_out = seg.ls_in / f"stem_{sid}.wav"
        stems_map[sid][: int(n25 * 1000 / FPS_LIPSYNC)].export(wav_out, format="wav")
        packed.extend([vid_out, wav_out])
        print(f"  [ls_in] {sid}: {n25}f @ 25fps ({ls_dur:.2f}s) from {clip_p.name}", flush=True)
    tar_p = seg.root / "lipsync_in.tar.gz"
    with tarfile.open(tar_p, "w:gz") as tf:
        for p in packed:
            tf.add(p, arcname=p.name)
    print(f"[prepare OK] {len(specs)} shots, {len(stems_map)} LatentSync bundles -> {tar_p} ({tar_p.stat().st_size // 1024} KB)", flush=True)
    return tar_p


def render_shot_frames(seg: Seg, s: dict, fast_mode: bool) -> list[np.ndarray]:
    sid = s["id"]
    dur = float(s["dur"])
    n_frames = max(1, int(round(dur * FPS_FINAL)))
    rife = bv13.get_rife()
    inner_mask = bv13.build_perimeter_inner_mask(H, W, margin=36)

    clip_p = resolve_clip(seg, s["clip"], fast_mode=fast_mode)
    raw_frames = bv13.decode_video_frames(clip_p)
    pos_base = [bv13.eval_curve(k / FPS_FINAL, s["curve"]) for k in range(n_frames)]
    rgb_base = rife.render_positions(raw_frames, pos_base)

    ls_dur = s.get("lipsync_dur_sec")
    ls_mp4 = seg.ls_out / f"sync_{sid}.mp4"
    frames_rgb: list[np.ndarray] = []
    if ls_dur is not None and ls_mp4.exists():
        ls_raw = bv13.decode_video_frames(ls_mp4)
        if s.get("ls_fit"):  # 口型片覆盖整片：首尾对齐拉满，避免尾帧被钳住→脸停一拍、接缝跳（p3 实测）
            pos_ls = [k * (len(ls_raw) - 1.0) / max(1, n_frames - 1) for k in range(n_frames)]
        else:
            pos_ls = [min(len(ls_raw) - 1.0, (k / FPS_FINAL) * FPS_LIPSYNC) for k in range(n_frames)]
        rgb_ls = rife.render_positions(ls_raw, pos_ls)
        if abs(float(ls_dur) - dur) < 0.15:
            for k in range(n_frames):
                f = (rgb_ls[k].astype(np.float32) * inner_mask + rgb_base[k].astype(np.float32) * (1.0 - inner_mask)).astype(np.uint8)
                frames_rgb.append(f)
        else:  # 口型段短于镜头：尾部 0.15s 交叉淡回原片（A-LIPSYNC-GUIDANCE-TIER tail_crossfade_s）
            t_bs = float(ls_dur) - 0.18
            t_be = float(ls_dur) - 0.03
            for k in range(n_frames):
                t_now = k / FPS_FINAL
                ls_clean = rgb_ls[k].astype(np.float32) * inner_mask + rgb_base[k].astype(np.float32) * (1.0 - inner_mask)
                if t_now <= t_bs:
                    frames_rgb.append(ls_clean.astype(np.uint8))
                elif t_now >= t_be:
                    frames_rgb.append(rgb_base[k])
                else:
                    a = (t_now - t_bs) / (t_be - t_bs)
                    frames_rgb.append((ls_clean * (1.0 - a) + rgb_base[k].astype(np.float32) * a).astype(np.uint8))
    else:
        if ls_dur is not None:
            print(f"[WARN] Missing {ls_mp4}, using base RIFE clip for {sid}", flush=True)
        frames_rgb = rgb_base
    return frames_rgb


def file_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def assemble(seg: Seg, specs: list[dict], final_mp4: Path, fast_mode: bool = False,
             combine_with: list[Path] | None = None, combined_mp4: Path | None = None,
             combined_concat_name: str | None = None, target_lufs: float | None = None) -> Path:
    """渲染每镜（按内容哈希缓存）→ concat → 限幅母带。combine_with: 无损拼在本段之前的成片。"""
    mode_tag = "fast" if fast_mode else "master"
    vf_args = [] if fast_mode else ["-vf", bv13.VF_CINEMA]
    enc_preset = "veryfast" if fast_mode else "medium"
    enc_crf = "20" if fast_mode else "17"

    seg_files: list[Path] = []
    srt_entries: list[tuple[float, float, str]] = []
    t_cursor = 0.0
    for s in specs:
        sid = s["id"]
        dur = float(s["dur"])
        n_frames = max(1, int(round(dur * FPS_FINAL)))
        seg_dur = n_frames / float(FPS_FINAL)
        wav_p = seg.mix_dir / f"shot_{sid}.wav"
        out_seg = seg.shot_dir / f"seg_{mode_tag}_{sid}.mov"
        hash_p = seg.shot_dir / f"seg_{mode_tag}_{sid}.sha256"
        clip_p = resolve_clip(seg, s["clip"], fast_mode=fast_mode)
        ls_mp4 = seg.ls_out / f"sync_{sid}.mp4"
        expected_hash = hashlib.sha256(json.dumps({
            "v": 1, "mode": mode_tag, "spec": s, "clip_sha": file_sha256(clip_p),
            "ls_sha": file_sha256(ls_mp4) if (s.get("lipsync_dur_sec") is not None and ls_mp4.exists()) else "",
            "wav_sha": file_sha256(wav_p),
        }, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

        if out_seg.exists() and hash_p.exists() and hash_p.read_text().strip() == expected_hash:
            print(f"[CACHE HIT | {mode_tag}] shot_{sid}", flush=True)
        else:
            frames_rgb = render_shot_frames(seg, s, fast_mode=fast_mode)
            cmd = [
                "ffmpeg", "-y", "-v", "error",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS_FINAL), "-i", "-",
                "-i", str(wav_p), *vf_args, "-af", "apad", "-r", str(FPS_FINAL),
                "-c:v", "libx264", "-preset", enc_preset, "-crf", enc_crf,
                "-profile:v", "high", "-level:v", "3.1", "-bf", "2",
                "-pix_fmt", "yuv420p", "-video_track_timescale", "15360",
                "-c:a", "pcm_s16le", "-ar", str(SR), "-ac", "2",
                "-t", f"{seg_dur:.6f}", str(out_seg),
            ]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            stamp = s.get("stamp")
            subs = s.get("subs", [])
            for k, arr in enumerate(frames_rgb):
                t_now = k / FPS_FINAL
                im = Image.fromarray(arr)
                if stamp and t_now < min(dur - 0.15, 3.6):
                    a_s = min(1.0, t_now / 0.35, max(0.0, (min(dur - 0.15, 3.6) - t_now) / 0.45))
                    im = draw_corner_stamp(im, stamp, alpha_scale=a_s)
                active_txt = next((txt for a, b, txt in subs if a <= t_now <= b + 0.12), None)
                if active_txt:
                    im = bv13.draw_subtitle_on_frame(im, active_txt)
                if s.get("fade_in") and k < int(FPS_FINAL * 0.45):
                    im = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), im, k / (FPS_FINAL * 0.45))
                elif s.get("fade_out") and k > n_frames - int(FPS_FINAL * 0.65):
                    rem = max(0.0, (n_frames - 1 - k) / (FPS_FINAL * 0.65))
                    im = Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), im, rem)
                proc.stdin.write(im.tobytes())
            proc.stdin.close()
            if proc.wait() != 0:
                raise RuntimeError(f"ffmpeg failed on shot {sid}")
            hash_p.write_text(expected_hash, encoding="utf-8")
            print(f"[RENDER    | {mode_tag}] shot_{sid} ({dur:.2f}s)", flush=True)
        for a, b, txt in s.get("subs", []):
            srt_entries.append((t_cursor + a, t_cursor + b, txt))
        seg_files.append(out_seg)
        t_cursor += dur

    concat_txt = seg.root / f"concat_{seg.tag}_{mode_tag}.txt"
    concat_txt.write_text("".join(f"file '{p}'\n" for p in seg_files), encoding="utf-8")
    out_mp4 = (seg.out_dir / f"preview_ep01_{seg.tag}_fast.mp4") if fast_mode else final_mp4
    if not fast_mode:  # A-SUBTITLE-SINGLE-LAYER：.srt 只归档在 out/
        arch_srt = seg.out_dir / f"{final_mp4.stem}_字幕归档.srt"
        arch_srt.write_text("".join(f"{i}\n{bv13.format_srt_ts(a)} --> {bv13.format_srt_ts(b)}\n{t}\n\n"
                                    for i, (a, b, t) in enumerate(srt_entries, 1)), encoding="utf-8")
    af = bv13.AF_LIMITER
    if target_lufs is not None:  # A-MASTER-LOUDNESS：两遍 loudnorm（先测再线性校正），真峰 -1.5
        meas = subprocess.run(["ffmpeg", "-nostats", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-vn",
                               "-af", f"{bv13.AF_LIMITER},loudnorm=I={target_lufs}:TP=-1.5:LRA=11:print_format=json",
                               "-f", "null", "-"], capture_output=True, text=True).stderr
        m = json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])
        # 只需整体增益：用 volume 精确补（loudnorm linear 模式实测欠补 0.3 dB）；真峰不超 -1.5
        gain = min(target_lufs - float(m["input_i"]), -1.5 - float(m["input_tp"]))
        af = f"{bv13.AF_LIMITER},volume={gain:.2f}dB"
        print(f"[loudnorm] 实测 {m['input_i']} LUFS / TP {m['input_tp']} → 目标 {target_lufs}，增益 {gain:+.2f} dB", flush=True)
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
        "-c:v", "copy", "-af", af, "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2",
        "-sn", "-movflags", "+faststart", str(out_mp4),
    ], check=True)
    print(f"[{seg.tag.upper()} {mode_tag.upper()} READY] {out_mp4} ({out_mp4.stat().st_size / (1024*1024):.2f} MB, {t_cursor:.2f}s)", flush=True)

    if not fast_mode and combine_with and combined_mp4 and all(p.exists() for p in combine_with):
        comb_txt = seg.root / (combined_concat_name or f"concat_{seg.tag}_combined.txt")
        comb_txt.write_text("".join(f"file '{p}'\n" for p in [*combine_with, final_mp4]), encoding="utf-8")
        subprocess.run([
            "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(comb_txt),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-ac", "2",
            "-sn", "-movflags", "+faststart", str(combined_mp4),
        ], check=True)
        print(f"[COMBINED READY] {combined_mp4} ({combined_mp4.stat().st_size / (1024*1024):.2f} MB)", flush=True)
    return out_mp4
