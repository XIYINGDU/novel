#!/Users/duxiying/.local/share/uv/tools/google-colab-cli/bin/python
# -*- coding: utf-8 -*-
"""整镜口型 + 小脸放大口型（2026-11-18，p3 接缝 seam_pop / 8i lipsync_weak；11-19 按 Codex 审核加固）。

接缝跳：主镜和续段各自走 LatentSync，同一句话跨缝时脸部两次渲染接不上。这里把一镜的各片 ls_in
（vid_/stem_，25fps，帧数 = round(ls_dur*25)）按顺序拼成一条，整条对口型，再按输入帧数切回 sync_<片>.mp4。
LatentSync 输出比输入多 1-2 帧（尾部补帧），从头按帧数切即对齐（头部无偏移这一点尚未实测）。

小脸：双人镜里脸太小/侧脸，LatentSync 几乎不动嘴。把脸所在方框裁出来放大 2 倍再对口型，缩回原尺寸羽化贴回。

  .../python common/lipsync_group.py <段目录> merge [--groups 7h,7k,...] [--zoom "8i:240,0,448"]  # 只做本地准备
  .../python common/lipsync_group.py <段目录> run [--n 3]                                          # 开 G4 跑（花 CU）
  .../python common/lipsync_group.py <段目录> split                                                # 切回 / 贴回 lipsync_out/
  .../python common/lipsync_group.py <段目录> keep 8m:55                                           # 前 55 帧换回原画
工作目录 <段目录>/ls_group/（自带 lipsync_in/ lipsync_out/ lipsync_job.json，跑法同 common/lipsync.py）。

安全约定：
- merge 先校验全部参数再动文件；会清掉 ls_group/lipsync_out 里的旧结果（防止旧裁片贴到新坐标）。
- split 先预检全部结果（缺件 / 帧数不足 / 远端兜底拷回的原片 → 整体拒绝），每片先写临时文件、核帧数，再替换。
- lipsync_out_pieces/ 只备份「不是本工具生成的」原件，且只备份一次（记在 _generated.json）。
- keep 总是从未 keep 过的口型（sync_<片>.prekeep.mp4）重新渲染，可重复执行。
"""
from __future__ import annotations

import filecmp
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
FPS = 25
UP_CRF = "18"  # 上传件：与 segbuild 的 ls_in 同档（crf12 会大 6 倍，Colab 上传 >12MB 易 408）
OUT_CRF = "12"
DEFAULT_G = 1.55  # 与 common/lipsync.py、remote_latentsync.py 一致


# ---------- 小工具 ----------

def ff(*args: str):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def probe(path: Path, entries: str, stream: str = "v", count: bool = False) -> list[str]:
    cmd = ["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries", entries, "-of", "csv=p=0"]
    if count:
        cmd.insert(3, "-count_frames")
    r = subprocess.run([*cmd, str(path)], capture_output=True, text=True, check=True)
    return r.stdout.strip().split(",")


def nframes(mp4: Path) -> int:
    return int(probe(mp4, "stream=nb_read_frames", count=True)[0])


def load_job(seg: Path) -> dict:
    p = seg / "lipsync_job.json"
    job = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return {"roi": job.get("roi", {}), "guidance": job.get("guidance", {}),
            "default_g": float(job.get("default_g", DEFAULT_G)), "steps": int(job.get("steps", 20))}


def pieces(ls_in: Path, base: str) -> list[str]:
    """base + base_c1..cK，必须有 base 且续段编号连续，否则报错（不静默丢片）。"""
    if not (ls_in / f"vid_{base}.mp4").exists():
        raise SystemExit(f"[merge] 缺主片 vid_{base}.mp4")
    ks = sorted(int(m.group(1)) for p in ls_in.glob(f"vid_{base}_c*.mp4")
                if (m := re.fullmatch(rf"vid_{re.escape(base)}_c(\d+)\.mp4", p.name)))
    if ks != list(range(1, len(ks) + 1)):
        raise SystemExit(f"[merge] {base} 续段编号不连续：c{ks}")
    out = [base] + [f"{base}_c{k}" for k in ks]
    for p in out:
        if not (ls_in / f"stem_{p}.wav").exists():
            raise SystemExit(f"[merge] 缺配音 stem_{p}.wav")
    return out


def stem_fixed(wav: Path, n: int, dst: Path):
    """配音补齐/截到正好 n 帧时长（样本级），避免拼接后后面几段口型提前。"""
    sr = int(probe(wav, "stream=sample_rate", stream="a")[0])
    ns = round(n / FPS * sr)
    ff("-i", str(wav), "-af", f"apad=whole_len={ns},atrim=end_sample={ns}", "-c:a", "pcm_s16le", str(dst))


class Publisher:
    """lipsync_out/ 的写入：临时文件 → 核帧数 → 替换；非本工具生成的原件首次覆盖前备份到 lipsync_out_pieces/。"""

    def __init__(self, seg: Path):
        self.out = seg / "lipsync_out"
        self.bak = seg / "lipsync_out_pieces"
        self.out.mkdir(parents=True, exist_ok=True)
        self.bak.mkdir(exist_ok=True)
        self.log = self.bak / "_generated.json"
        self.generated = set(json.loads(self.log.read_text())) if self.log.exists() else set()

    def tmp(self, pid: str) -> Path:
        return self.out / f"sync_{pid}.tmp.mp4"

    def publish(self, pid: str, want: int):
        tmp, dst = self.tmp(pid), self.out / f"sync_{pid}.mp4"
        got = nframes(tmp)
        if got != want:
            tmp.unlink()
            raise SystemExit(f"[split] {pid}: 输出 {got}f ≠ 应有 {want}f，未替换")
        if dst.exists() and dst.name not in self.generated and not (self.bak / dst.name).exists():
            dst.rename(self.bak / dst.name)
        tmp.replace(dst)
        (self.out / f"sync_{pid}.prekeep.mp4").unlink(missing_ok=True)  # 新口型作废旧的 keep 底稿
        self.generated.add(dst.name)
        self.log.write_text(json.dumps(sorted(self.generated), ensure_ascii=False, indent=1))


# ---------- merge ----------

def merge(seg: Path, groups: list[str], zooms: dict[str, tuple[int, int, int]]):
    if not groups and not zooms:
        raise SystemExit("[merge] 没有 --groups 也没有 --zoom")
    src_in, job = seg / "lipsync_in", load_job(seg)
    # 先全部校验，再动文件
    plan_groups = {}
    for base in groups:
        ps = pieces(src_in, base)
        if len(ps) < 2:
            print(f"[merge] {base}: 只有 {ps}，不用合并，跳过")
            continue
        plan_groups[f"{base}G"] = {"pieces": ps, "counts": [nframes(src_in / f"vid_{p}.mp4") for p in ps], "base": base}
    grouped = {p for g in plan_groups.values() for p in g["pieces"]}
    if dup := grouped & set(zooms):
        raise SystemExit(f"[merge] {sorted(dup)} 同时在 --groups 和 --zoom 里，两边会互相覆盖")
    for sid, (x, y, s) in zooms.items():
        v = src_in / f"vid_{sid}.mp4"
        if not v.exists() or not (src_in / f"stem_{sid}.wav").exists():
            raise SystemExit(f"[merge] 缺 {sid} 的 vid_/stem_")
        w, h = (int(t) for t in probe(v, "stream=width,height"))
        if s <= 0 or x < 0 or y < 0 or x + s > w or y + s > h or x % 2 or y % 2 or s % 2:
            raise SystemExit(f"[merge] {sid} 框 {s}@({x},{y}) 越界或非偶数（画面 {w}x{h}）")

    g = seg / "ls_group"
    gin, gout = g / "lipsync_in", g / "lipsync_out"
    for d in (gin, gout):
        d.mkdir(parents=True, exist_ok=True)
        for p in d.glob("*"):
            p.unlink()
    plan = {"groups": {}, "zoom": {}}
    gjob = {"roi": {}, "guidance": {}, "default_g": job["default_g"], "steps": job["steps"]}
    for gid, info in plan_groups.items():
        ps, counts, n = info["pieces"], info["counts"], len(info["pieces"])
        ff(*sum([["-i", str(src_in / f"vid_{p}.mp4")] for p in ps], []),
           "-filter_complex", "".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]", "-map", "[v]",
           "-r", str(FPS), "-c:v", "libx264", "-crf", UP_CRF, "-pix_fmt", "yuv420p", str(gin / f"vid_{gid}.mp4"))
        fixed = []
        for p, c in zip(ps, counts):
            fixed.append(gin / f"_stem_{p}.wav")
            stem_fixed(src_in / f"stem_{p}.wav", c, fixed[-1])
        ff(*sum([["-i", str(f)] for f in fixed], []),
           "-filter_complex", "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]", "-map", "[a]",
           str(gin / f"stem_{gid}.wav"))
        for f in fixed:
            f.unlink()
        got = nframes(gin / f"vid_{gid}.mp4")
        assert got == sum(counts), (gid, got, counts)
        plan["groups"][gid] = {"pieces": ps, "counts": counts}
        gjob["guidance"][gid] = job["guidance"].get(info["base"], job["default_g"])
        if info["base"] in job["roi"]:
            gjob["roi"][gid] = job["roi"][info["base"]]
        print(f"[merge] {gid}: {ps} {counts} → {got}f", flush=True)
    for sid, (x, y, s) in zooms.items():
        zid = f"{sid}Z"
        ff("-i", str(src_in / f"vid_{sid}.mp4"), "-vf", f"crop={s}:{s}:{x}:{y},scale={2 * s}:{2 * s}:flags=lanczos",
           "-r", str(FPS), "-c:v", "libx264", "-crf", UP_CRF, "-pix_fmt", "yuv420p", str(gin / f"vid_{zid}.mp4"))
        ff("-i", str(src_in / f"stem_{sid}.wav"), "-c", "copy", str(gin / f"stem_{zid}.wav"))
        plan["zoom"][zid] = {"sid": sid, "box": [x, y, s], "count": nframes(src_in / f"vid_{sid}.mp4")}
        gjob["guidance"][zid] = job["guidance"].get(sid, job["default_g"])  # 裁出来只剩一个人：不需要 roi
        print(f"[merge] {zid}: crop {s}x{s}@({x},{y}) ×2", flush=True)
    (g / "lipsync_job.json").write_text(json.dumps(gjob, ensure_ascii=False, indent=1), encoding="utf-8")
    (g / "group_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------- run ----------

def run(seg: Path, n: int):
    from lipsync import run_lipsync
    r = run_lipsync(seg / "ls_group", n=n, seg_tag=seg.name.removeprefix("ep01_"))
    bad = fallback_copies(seg / "ls_group")
    if bad:
        print(f"[run] 远端推理失败、拷回了原片：{bad}", flush=True)
    sys.exit(1 if r["failed"] or bad else 0)


def fallback_copies(g: Path) -> list[str]:
    """remote_latentsync 推理异常时把输入原样拷成 sync_*.mp4，字节相同即兜底件。"""
    return [p.name for p in (g / "lipsync_out").glob("sync_*.mp4")
            if (src := g / "lipsync_in" / f"vid_{p.stem.removeprefix('sync_')}.mp4").exists()
            and filecmp.cmp(p, src, shallow=False)]


# ---------- split ----------

def mask_expr(f: int) -> str:
    # 四边各 f 像素线性渐变；必须截到 [0,1]，否则 gray 平面 >255 回绕成条纹（11-19 Codex 审出，8i 首轮因此作废）
    return f"geq=lum='255*clip(min(min(X,W-1-X),min(Y,H-1-Y))/{f},0,1)'"


def paste_zoom(src: Path, sync: Path, box: list[int], count: int, dst: Path):
    x, y, s = box
    f = max(8, s // 12)  # 羽化宽度
    ff("-i", str(src), "-i", str(sync), "-filter_complex",
       f"[1:v]scale={s}:{s}:flags=lanczos,trim=end_frame={count},setpts=PTS-STARTPTS,format=yuva420p[z];"
       f"color=c=black:s={s}x{s}:r={FPS},format=gray,{mask_expr(f)},trim=end_frame={count},setpts=PTS-STARTPTS[m];"
       f"[z][m]alphamerge[za];[0:v][za]overlay={x}:{y}:eof_action=pass[v]",
       "-map", "[v]", "-frames:v", str(count), "-r", str(FPS), "-c:v", "libx264", "-crf", OUT_CRF,
       "-pix_fmt", "yuv420p", str(dst))


def split(seg: Path):
    g = seg / "ls_group"
    plan = json.loads((g / "group_plan.json").read_text(encoding="utf-8"))
    src_in = seg / "lipsync_in"
    # 预检：全部到齐、帧数够、不是兜底原片，否则一片都不动
    need = {gid: sum(i["counts"]) for gid, i in plan["groups"].items()} | {z: i["count"] for z, i in plan["zoom"].items()}
    errs = []
    fb = set(fallback_copies(g))
    for gid, want in need.items():
        sync = g / "lipsync_out" / f"sync_{gid}.mp4"
        if not sync.exists():
            errs.append(f"缺 {sync.name}")
        elif sync.name in fb:
            errs.append(f"{sync.name} 是远端兜底拷回的原片")
        elif (got := nframes(sync)) < want:
            errs.append(f"{sync.name} 只有 {got}f < {want}f")
    if errs:
        raise SystemExit("[split] 预检不过，未改任何文件：\n  " + "\n  ".join(errs))
    pub = Publisher(seg)
    for gid, info in plan["groups"].items():
        sync = g / "lipsync_out" / f"sync_{gid}.mp4"
        a = 0
        for pid, c in zip(info["pieces"], info["counts"]):
            ff("-i", str(sync), "-vf", f"trim=start_frame={a}:end_frame={a + c},setpts=PTS-STARTPTS", "-an",
               "-r", str(FPS), "-c:v", "libx264", "-crf", OUT_CRF, "-pix_fmt", "yuv420p", str(pub.tmp(pid)))
            pub.publish(pid, c)
            a += c
        print(f"[split] {gid} → {info['pieces']}（输出 {nframes(sync)}f / 输入 {a}f）", flush=True)
    for zid, info in plan["zoom"].items():
        sid = info["sid"]
        paste_zoom(src_in / f"vid_{sid}.mp4", g / "lipsync_out" / f"sync_{zid}.mp4", info["box"], info["count"],
                   pub.tmp(sid))
        pub.publish(sid, info["count"])
        print(f"[split] {zid} → sync_{sid}.mp4（贴回 {info['box'][2]}px@({info['box'][0]},{info['box'][1]})）", flush=True)


# ---------- keep ----------

def keep(seg: Path, sid: str, upto: int, xf: int = 5):
    """sync_<sid> 前 upto 帧换回口型输入原画（不说话、手/道具挡嘴的段落），之后 xf 帧过渡到口型
    （blend 的 N 从 1 起：第 upto+1..upto+xf 帧口型权重 1/xf..1，即 xf-1 帧真正混合）。
    总是从 sync_<sid>.prekeep.mp4（首次 keep 时存下的口型原件）渲染，重复执行结果不变。"""
    out = seg / "lipsync_out" / f"sync_{sid}.mp4"
    pre, src = out.with_suffix(".prekeep.mp4"), seg / "lipsync_in" / f"vid_{sid}.mp4"
    n = nframes(src)
    if not 0 <= upto < n:
        raise SystemExit(f"[keep] {sid}: upto={upto} 不在 0..{n - 1}")
    if not pre.exists():
        out.rename(pre)
    tmp = out.with_suffix(".tmp.mp4")
    a, b = upto, upto + xf
    ff("-i", str(src), "-i", str(pre), "-filter_complex",
       f"[0:v]setpts=PTS-STARTPTS[o];[1:v]setpts=PTS-STARTPTS[s];"
       f"[o][s]blend=all_expr='if(lte(N,{a}),A,if(gte(N,{b}),B,A+(B-A)*(N-{a})/{xf}))':shortest=1[v]",
       "-map", "[v]", "-frames:v", str(n), "-r", str(FPS), "-c:v", "libx264", "-crf", OUT_CRF,
       "-pix_fmt", "yuv420p", str(tmp))
    tmp.replace(out)
    print(f"[keep] {sid}: 前 {a} 帧原画，之后 {xf} 帧过渡到口型（底稿 {pre.name}）", flush=True)


# ---------- CLI ----------

def parse(argv: list[str]):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    seg, mode, rest = Path(argv[0]).resolve(), argv[1], argv[2:]
    if not (seg / "lipsync_in").is_dir():
        raise SystemExit(f"{seg} 下没有 lipsync_in/")
    opts: dict[str, str] = {}
    allowed = {"merge": {"--groups", "--zoom"}, "run": {"--n"}, "split": set(), "keep": set()}
    if mode not in allowed:
        raise SystemExit(f"未知模式 {mode}（merge/run/split/keep）")
    pos = []
    i = 0
    while i < len(rest):
        k = rest[i]
        if k.startswith("--"):
            if k not in allowed[mode] or i + 1 >= len(rest):
                raise SystemExit(f"{mode} 不认识参数 {k} 或缺值")
            opts[k] = rest[i + 1]
            i += 2
        else:
            pos.append(k)
            i += 1
    if mode == "merge":
        if pos:
            raise SystemExit(f"merge 多余参数 {pos}")
        groups = [s for s in opts.get("--groups", "").split(",") if s]
        zooms = {}
        for spec in filter(None, opts.get("--zoom", "").split(";")):
            sid, _, box = spec.partition(":")
            vals = box.split(",")
            if not sid or len(vals) != 3 or not all(re.fullmatch(r"\d+", v) for v in vals):
                raise SystemExit(f"--zoom 写法应为 片:x,y,s，收到 {spec!r}")
            zooms[sid] = tuple(int(v) for v in vals)
        return merge, (seg, groups, zooms)
    if mode == "run":
        n = opts.get("--n", "3")
        if pos or not n.isdigit() or int(n) < 1:
            raise SystemExit("run 用法：run [--n 正整数]")
        return run, (seg, int(n))
    if mode == "split":
        if pos:
            raise SystemExit(f"split 多余参数 {pos}")
        return split, (seg,)
    if len(pos) != 1 or not re.fullmatch(r"[^:]+:\d+", pos[0]):
        raise SystemExit("keep 用法：keep <片>:<帧数>，如 keep 8m:55")
    sid, n = pos[0].split(":")
    return keep, (seg, sid, int(n))


if __name__ == "__main__":
    fn, args = parse(sys.argv[1:])
    fn(*args)
