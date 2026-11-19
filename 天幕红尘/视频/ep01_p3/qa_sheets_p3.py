#!/usr/bin/env python3
"""p3 母带逐帧（step=1）接触表，V-QA-EVERY-FRAME。
  python3 ep01_p3/qa_sheets_p3.py          → ep01_p3/sheets/qa_master/
- 整镜：7j（静音口型压嘴）、8b（侧脸口型）、8i（双人 ROI）、8m（烟）
- 接缝：每个续段接缝前后各 10 帧（共 21 帧一行）
"""
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
MASTER = HERE.parent / "第01集_p3_1-7至1-8_v2.mp4"
OUT = HERE / "sheets" / "qa_master"
FPS = 30
# 整镜：(镜头前缀, 裁切 w:h:x:y 比例, 说明)
WHOLE = {
    "7j": ((0.40, 0.55, 0.30, 0.05), "静音口型：嘴是否一直闭、边缘糊/闪"),
    "8b": ((0.45, 0.60, 0.05, 0.05), "阿英侧脸口型"),
    "8i": ((0.45, 0.60, 0.10, 0.05), "双人镜：动嘴的应是左边梁士乔"),
    "8m": ((1.0, 1.0, 0.0, 0.0), "烟是否连续"),
}


def starts():
    specs = json.loads((HERE / "audio_meta_p3_master.json").read_text(encoding="utf-8"))
    t, out = 0.0, []
    for s in specs:
        n = max(1, round(float(s["dur"]) * FPS))
        out.append((s["id"], t, n / FPS))
        t += n / FPS
    return out


def sheet(t0: float, n: int, crop, cols: int, width: int, png: Path):
    cw, ch, cx, cy = crop
    vf = (f"crop=iw*{cw}:ih*{ch}:iw*{cx}:ih*{cy},scale={width}:-2,"
          f"tile={cols}x{(n + cols - 1) // cols}")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.4f}", "-i", str(MASTER), "-frames:v", str(n),
                    "-vf", f"select='lt(n,{n})',{vf}", "-frames:v", "1", str(png)], check=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    st = starts()
    by = {sid: (t, d) for sid, t, d in st}
    for sid, (crop, note) in WHOLE.items():
        t = by[sid][0]
        d = sum(d for s, _, d in st if s == sid or s.startswith(sid + "_c"))
        n = round(d * FPS)
        p = OUT / f"whole_{sid}.png"
        sheet(t, n, crop, 20, 150 if crop[0] < 1 else 200, p)
        print(f"{p.name}: {sid} {t:.2f}s 起 {n} 帧 — {note}")
    seams = [(sid, t) for sid, t, _ in st if "_c" in sid]
    rows = []
    for sid, t in seams:
        p = OUT / f"seam_{sid}.png"
        sheet(max(0.0, t - 10 / FPS), 21, (1.0, 1.0, 0.0, 0.0), 21, 120, p)
        rows.append(p)
    allp = OUT / "seams_all.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *sum([["-i", str(r)] for r in rows], []),
                    "-filter_complex", f"vstack=inputs={len(rows)}", str(allp)], check=True)
    print(f"{allp.name}: {len(rows)} 个接缝 × 21 帧（第 11 列 = 续段第一帧）")


if __name__ == "__main__":
    main()
