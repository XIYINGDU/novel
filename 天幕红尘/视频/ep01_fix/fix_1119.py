#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ep01 p3 8i 修复批（2026-11-19，方案 B：梁士乔单人近景重出再对口型）。defects 见 loop/ledger/defects.jsonl #55/#72/#79。

背景：ep01 p3 原 8i 双人中景中梁士乔为低头 3/4 侧脸，LatentSync（含裁切放大 2× 重贴）带不动口型；
改为梁士乔单人近景重出，先出 i2i 关键帧，再出 4 个种子的 HD 镜头择优对口型。

  python3 ep01_fix/fix_1119.py stills          # Qwen i2i：以 k_liang_studio.png 为底图生成单人近景关键帧
  python3 ep01_fix/fix_1119.py wan [--n 2]     # Wan HD：读 picks_1119.json，出 clip_s8i1_s1..s4 → ep01_p3/clips/
  python3 ep01_fix/fix_1119.py cont            # 8i1 选中种子的续段（末帧 I2V，按需）

同名产物通过旁边的 .sha256 校验生成参数、输入和输出。过期候选归档到同目录 .fix1119_previous/。

规则（参照 loop/rules/*.yaml）：
- P-SHM-NO-MIX：Qwen-Image i2i 与 Wan2.2 分池分步运行，不在同一台 G4 混跑。
- P-COLAB-RESILIENCE / P-COLAB-DUAL-G4：沿用 ColabPool 保活，复用校验通过的产物，退出时核实本池实例已释放。
- V-WAN-CFG1-NO-NEG：Wan LightX2V cfg=1.0 不读负向词（neg 置空），负向词只在 Qwen i2i 阶段写；返修镜出 4 个种子择优。
- V-CONTINUITY-ADJACENT：继承 1-8 摄影棚角落同机位光线、深灰双排扣西装与金丝眼镜造型及木箱线缆背景（衔接 8h2/8j）；续段首帧=上游末帧。
- V-HAND-ANATOMY：手持传真处写明 five-finger bare right hand, four fingers + one thumb，Qwen 负向词排除多指/畸形手。
- V-TEXT-NO-SMALL-PRINT：热敏传真纸只表现模糊不可读手写笔迹，禁出可读小字或乱码汉字。
- V-QA-EVERY-FRAME / V-QA-FACE-METRIC：HD 完成后触发 hooks.after_render 量尺初筛，配合逐帧接触表做人眼 QA。
- A-LIPSYNC-CLEAN-STEM / A-LIPSYNC-GUIDANCE-TIER：抬头近正面单人近景保证嘴部清晰受光；有台词镜 Wan 提示词不写 lips closed。
- override V-SCOUT-THEN-HD：返修镜场景/造型已在 p3 验证，且同种子 Scout→HD 存在动作分叉（defects #47/#48），HD 直出 4 种子再做 QA。
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
VID = HERE.parent
sys.path.insert(0, str(VID / "common"))
import qwen  # noqa: E402
import wan  # noqa: E402
from colab_pool import ColabPool, hooks  # noqa: E402

REF = VID / "ref"
P3 = VID / "ep01_p3"
P3S = P3 / "stills"
FIX_STILLS = P3S / "fix1119"
PICKS = HERE / "picks_1119.json"  # {"8i1_start": "ep01_p3/stills/fix1119/8i1_start_k1.png", "8i1": "clip_s8i1_s1"}

STYLE_Q = qwen.STYLE
STYLE_W = " 1991 35mm film look, natural film grain, realistic, steady camera, subtle natural motion."
NEG_STUDIO = (
    qwen.NEG_PORTRAIT
    + ", six fingers, fused fingers, extra arm, three hands, extra limbs, readable text, readable signage, "
    "garbled chinese characters, printed font, bowed head, looking down, steep side profile, head turned away, "
    "broad smile, smiling, grin, laughing"
)
HANDS = " five-finger bare right hand, four fingers + one thumb."
TALK_M = " He speaks naturally, lips moving with the words, small natural head movements and blinks."

# ---------- 阶段 1：Qwen 关键帧（2 种子候选） ----------
STILLS = [
    dict(
        id=f"8i1_start_k{k + 1}",
        seed=seed,
        neg=NEG_STUDIO,
        prompt=(
            "STRICTLY KEEP THE EXACT SAME Hong Kong Chinese man in his early forties (same face, neatly combed short "
            "dark hair, thin gold-rimmed eyeglasses, tailored charcoal double-breasted suit, white shirt, muted silk "
            "tie, faint sweat at his temple) and the exact same dim corner of the hot 1991 Beijing film soundstage "
            "(old wooden crates, coiled cables, warm tungsten set light glaring far behind). Solo medium close-up, "
            "head upright and facing nearly toward camera (angled only slightly toward an off-screen listener on "
            "screen right, NEVER bowed down, NEVER steep 3/4 side profile), clear unobstructed view of his mouth and "
            "jaw, serious composed shrewd eyes, mouth closed. His right hand at lower-chest level holds three thin "
            "curling sheets of 1991 thermal fax paper with faint illegible handwriting only (no readable text)."
            + HANDS
            + " "
            + STYLE_Q
        ),
    )
    for k, seed in enumerate((7911, 7912))
]


def liang_studio_ref() -> Path:
    """优先读 ref/k_liang_studio.png；若磁盘上位于 ep01_p3/stills/k_liang_studio.png 则自动回退。"""
    cand = REF / "k_liang_studio.png"
    if cand.exists():
        return cand
    fallback = P3S / "k_liang_studio.png"
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"未找到底图：{cand} 或 {fallback}")


def resolve_path(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else (VID / path)


def file_sha(path: Path) -> str:
    with path.open("rb") as source:
        digest = hashlib.sha256()
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def recipe_sha(settings, job) -> str:
    # 参数中的 Path 都是输入素材。相同文件名换了内容也会得到新签名。
    data = json.dumps([settings, job], default=file_sha, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(data.encode()).hexdigest()


def cache_matches(out: Path, recipe: str) -> bool:
    stamp = out.with_suffix(out.suffix + ".sha256")
    if not stamp.is_file() or not out.is_file():
        return False
    fields = stamp.read_bytes().split()
    return len(fields) == 2 and fields[0] == recipe.encode() and fields[1] == file_sha(out).encode()


def run_batch(stage, n, jobs, settings, setup, render):
    pending = []
    for out, job in jobs.items():
        signature = recipe_sha(settings, job)
        if not cache_matches(out, signature):
            pending.append((out, job, signature))
    if not pending:
        print(f"[{stage}] {len(jobs)} 个产物均已核验，跳过", flush=True)
        return {}

    # 退出或只跑完部分任务时，候选目录只展示当前参数的结果。旧候选保留供复查。
    for out, _, _ in pending:
        if out.exists():
            archive = out.parent / ".fix1119_previous" / file_sha(out)
            archive.mkdir(parents=True, exist_ok=True)
            out.replace(archive / out.name)
            out.with_suffix(out.suffix + ".sha256").unlink(missing_ok=True)

    def work(worker, item):
        out, job, signature = item
        out.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=out.parent) as tmp:
            staged = render(worker, job, Path(tmp) / out.name)
            if not staged.is_file() or not staged.stat().st_size:
                raise RuntimeError(f"没有生成 {out.name}")
            stamp = Path(tmp) / "receipt"
            stamp.write_text(f"{signature} {file_sha(staged)}\n", encoding="ascii")
            staged.replace(out)
            stamp.replace(out.with_suffix(out.suffix + ".sha256"))
        return out

    with ColabPool(n=min(n, len(pending)), setup=setup, seg="p3", stage=stage) as pool:
        results, failed = pool.run(pending, work, key=lambda item: item[0].stem)
    for out, _, _ in pending:
        if out.stem not in results:
            failed.setdefault(out.stem, "缺少产物")
    if failed:
        raise SystemExit(f"[{stage}] 失败 {failed}")
    print(f"[{stage}] 完成 {len(results)} 个产物", flush=True)
    return results


def run_stills():
    ref_png = liang_studio_ref()
    jobs = {
        FIX_STILLS / f"{s['id']}.png": dict(mode="i2i_edit", ref=ref_png, width=1280, height=720,
                                            steps=30, seed=s["seed"], prompt=s["prompt"], neg=s["neg"])
        for s in STILLS
    }
    run_batch("stills_fix", 1, jobs, qwen.MODEL, qwen.setup,
              lambda worker, job, dst: qwen.render_job(worker, {**job, "out": dst}))


# ---------- 阶段 2：Wan HD（4 种子：clip_s8i1_s1 .. clip_s8i1_s4） ----------
def wan_jobs(picks: dict) -> list[tuple]:
    s8i1 = resolve_path(picks["8i1_start"])
    if not s8i1.exists():
        raise FileNotFoundError(f"关键帧不存在：{s8i1}（请先运行 stills 并更新 {PICKS.name}）")
    return [
        (
            f"s8i1_s{k + 1}",
            "i2v",
            s8i1,
            None,
            81,
            9480 + k,
            "",
            "Static solo medium close-up in the dim corner of a hot 1991 Beijing film soundstage. Keeping his head "
            "upright and his face turned nearly toward camera (looking slightly toward the listener just off-screen "
            "right, never bowing his head down), the man in the charcoal suit and gold-rimmed glasses holds and "
            "extends the three thin curling sheets of fax paper slightly forward at chest level with his right hand, "
            "speaking flatly and matter-of-factly."
            + HANDS
            + TALK_M
            + STYLE_W,
        )
        for k in range(4)
    ]


WAN_SETTINGS = ("wan2.2-lightx2v", wan.HD, wan.FPS)


def render_one(worker, job, dst):
    return wan.render(worker, job, wan.HD, dst.parent, "fix")


def run_wan(n: int):
    picks = json.loads(PICKS.read_text(encoding="utf-8"))
    jobs = {P3 / "clips" / f"clip_{j[0]}.mp4": j for j in wan_jobs(picks)}
    res = run_batch("hd", n, jobs, WAN_SETTINGS, wan.setup, render_one)
    if res:
        hooks.after_render("p3", "01", "hd", list(res.values()))


# ---------- 阶段 3：续段（按需，末帧 I2V） ----------
def last_frame(mp4: Path, png: Path) -> Path:
    png.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=png.parent) as tmp:
        staged = Path(tmp) / png.name
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-sseof", "-0.2", "-i", str(mp4), "-update", "1", "-q:v", "1", str(staged)],
            check=True,
        )
        staged.replace(png)
    return png


def run_cont():
    picks = json.loads(PICKS.read_text(encoding="utf-8"))
    base = picks["8i1"]  # e.g. clip_s8i1_s1
    src = P3 / "clips" / f"{base}.mp4"
    # 单独运行 cont 也要检查所选 HD 是否来自当前关键帧。
    hd_jobs = {f"clip_{j[0]}": j for j in wan_jobs(picks)}
    if base in hd_jobs and not cache_matches(src, recipe_sha(WAN_SETTINGS, hd_jobs[base])):
        raise SystemExit(f"[cont] {base} 与当前关键帧或渲染参数未匹配，请先运行 wan")
    png = last_frame(src, P3S / "cont" / f"{base}_last.png")
    job = (
        f"{base.removeprefix('clip_')}_c1",
        "i2v",
        png,
        None,
        81,
        9490,
        "",
        "Continuing the same shot from this exact frame: same framing, same upright head pose and background, no cut. "
        "Holding the curling fax sheets steadily at lower-chest level, he keeps speaking flatly and calmly."
        + HANDS
        + TALK_M
        + STYLE_W,
    )
    out = P3 / "clips" / f"clip_{job[0]}.mp4"
    run_batch("cont", 1, {out: job}, WAN_SETTINGS, wan.setup, render_one)


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("stills", "wan", "cont"):
        raise SystemExit("用法: python3 ep01_fix/fix_1119.py stills | wan [--n 2] | cont")
    n = int(a[a.index("--n") + 1]) if "--n" in a else 2
    # 同一修复批共用所选镜头的文件名，串行核验、发布。池内各个种子仍并行。
    with Path(__file__).open("rb") as batch_lock:
        fcntl.flock(batch_lock, fcntl.LOCK_EX)
        {"stills": run_stills, "wan": lambda: run_wan(n), "cont": run_cont}[a[0]]()
