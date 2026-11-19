#!/usr/bin/env python3
"""Wan2.2 14B LightX2V（ComfyUI on EasyColab）共享调用，配合 colab_pool。
复用 v09/v10 已验证的图与提交逻辑；cfg=1，负向词无效（V-WAN-CFG1-NO-NEG）。

job = (id, mode "i2v"|"flf2v", start_png, end_png|None, frames(≤81, 16fps), seed, neg(忽略), prompt)
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

VID = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VID / "v09_fixes"))
sys.path.insert(0, str(VID / "v10_fixes"))
import stage2_clips_v09 as s2v9  # noqa: E402
import stage2_scout_hd_v10 as s2v10  # noqa: E402

SCOUT = (832, 480)
HD = (1280, 720)
FPS = 16


def setup(w):
    w.log("启动 ComfyUI / Wan2.2 ...")
    cf = s2v9.ensure_wan22_and_comfyui(w.base_gradio)
    w.ctx.update(cf_url=cf, use_vhs=s2v9.has_vhs_node(cf), client_id=uuid.uuid4().hex, uploaded={})
    w.log(f"ComfyUI ready {cf}")


def render(w, job, size: tuple[int, int], out_dir: Path, tag: str) -> Path:
    c = w.ctx
    out_dir.mkdir(parents=True, exist_ok=True)
    p = s2v10.submit_and_download(c["cf_url"], w.base_gradio, c["client_id"], c["use_vhs"], c["uploaded"],
                                  job, size[0], size[1], out_dir, tag)
    w.log(f"done {p.name}")
    return p


def frames_for(seconds: float, pad: float = 0.3) -> int:
    """台词秒数 → Wan 帧数（4n+1，≤81）。超过 81 帧的要拆段续接。"""
    n = int((seconds + pad) * FPS)
    n = max(33, min(81, n))
    return n - (n - 1) % 4
