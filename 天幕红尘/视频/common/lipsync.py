#!/Users/duxiying/.local/share/uv/tools/google-colab-cli/bin/python
# -*- coding: utf-8 -*-
"""通用口型 Stage D：把 <段目录>/lipsync_in/ 的 vid_/stem_ 对分片到 N 台 G4，跑 common/remote_latentsync.py。

  .../google-colab-cli/bin/python common/lipsync.py <段目录> [--n 2] [--only s7c,s7g]
参数（ROI/guidance）读 <段目录>/lipsync_job.json（可无）：{"roi": {...}, "guidance": {...}, "default_g": 1.55, "steps": 20}
产物解到 <段目录>/lipsync_out/sync_<sid>.mp4。正式出片要花 CU：先告诉 xiying 再跑。
"""
from __future__ import annotations

import json
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from colab_pool import ColabPool  # noqa: E402
from remote_job import run_remote  # noqa: E402


def shard(items: list[str], n: int) -> list[list[str]]:
    """按顺序轮转分片（镜头时长相近，轮转足够均衡）。"""
    out = [[] for _ in range(n)]
    for i, it in enumerate(items):
        out[i % n].append(it)
    return [s for s in out if s]


def run_lipsync(seg_dir: Path, n: int = 1, only: set[str] | None = None, seg_tag: str | None = None) -> dict:
    seg_dir = Path(seg_dir)
    ls_in, ls_out = seg_dir / "lipsync_in", seg_dir / "lipsync_out"
    ls_out.mkdir(parents=True, exist_ok=True)
    sids = sorted(p.stem.removeprefix("vid_") for p in ls_in.glob("vid_*.mp4") if (ls_in / f"stem_{p.stem[4:]}.wav").exists())
    if only:
        sids = [s for s in sids if s in only]
    if not sids:
        raise SystemExit(f"{ls_in} 里没有成对的 vid_/stem_；先跑段的 prepare")
    job_p = seg_dir / "lipsync_job.json"
    base_job = json.loads(job_p.read_text(encoding="utf-8")) if job_p.exists() else {}
    # Colab contents API 传 ~40MB 会 408 超时（p3 2026-11-18）：按体积切小分片（≤~12MB），机器数仍是 n
    total = sum((ls_in / f"vid_{s}.mp4").stat().st_size + (ls_in / f"stem_{s}.wav").stat().st_size for s in sids)
    n_shards = max(n, -(-total // (12 << 20)))
    shards = shard(sids, max(1, min(n_shards, len(sids))))
    tmp = seg_dir / "lipsync_shards"
    tmp.mkdir(exist_ok=True)
    jobs = []
    for k, ss in enumerate(shards):
        tar_p = tmp / f"in_{k}.tar.gz"
        with tarfile.open(tar_p, "w:gz") as tf:
            for sid in ss:
                tf.add(ls_in / f"vid_{sid}.mp4", arcname=f"vid_{sid}.mp4")
                tf.add(ls_in / f"stem_{sid}.wav", arcname=f"stem_{sid}.wav")
        jp = tmp / f"job_{k}.json"
        jp.write_text(json.dumps({**base_job, "in": "/content/lipsync_in.tar.gz", "out": "/content/lipsync_out.tar.gz"},
                                 ensure_ascii=False), encoding="utf-8")
        jobs.append((k, ss, tar_p, jp))
    print(f"[lipsync] {len(sids)} 镜 → {len(shards)} 台：{[j[1] for j in jobs]}", flush=True)

    def work(w, job):
        k, ss, tar_p, jp = job
        out_local = tmp / f"out_{k}.tar.gz"
        run_remote(w, HERE / "remote_latentsync.py",
                   {tar_p: "/content/lipsync_in.tar.gz", jp: "/content/lipsync_job.json"},
                   "/content/lipsync_out.tar.gz", out_local, timeout_s=600 + 150 * len(ss), tag="lipsync")
        with tarfile.open(out_local, "r:gz") as tf:
            tf.extractall(ls_out)
        return ss

    tag = seg_tag or seg_dir.name.removeprefix("ep01_")
    with ColabPool(n=min(n, len(shards)), seg=tag, stage="lipsync") as pool:
        res, failed = pool.run(jobs, work, key=lambda j: f"shard{j[0]}")
    got = sorted(p.stem.removeprefix("sync_") for p in ls_out.glob("sync_*.mp4"))
    print(f"[lipsync] 完成 {sum(len(v) for v in res.values())} 镜；失败分片 {failed or '无'}；lipsync_out 现有 {len(got)} 条", flush=True)
    return {"ok": res, "failed": failed}


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0].startswith("-"):
        raise SystemExit(__doc__)
    n = int(args[args.index("--n") + 1]) if "--n" in args else 1
    only = set(args[args.index("--only") + 1].split(",")) if "--only" in args else None
    r = run_lipsync(Path(args[0]), n=n, only=only)
    sys.exit(1 if r["failed"] else 0)
