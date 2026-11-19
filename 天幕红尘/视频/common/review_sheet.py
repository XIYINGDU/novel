#!/usr/bin/env python3
"""选种总览：每镜一行，每个种子取 N 帧并排，便于横向比种。逐帧细看仍用 per-clip 接触表（V-QA-EVERY-FRAME）。
用法：uv run -q --with pillow --with opencv-python-headless python review_sheet.py <clip目录> <输出前缀> [--frames 5] [--rows 9]
clip 文件名形如 clip_<镜>_s<k>.mp4
"""
import argparse
import re
from collections import defaultdict
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont

ap = argparse.ArgumentParser()
ap.add_argument("clips"); ap.add_argument("out"); ap.add_argument("--frames", type=int, default=5); ap.add_argument("--rows", type=int, default=9)
a = ap.parse_args()
W, H = 192, 110
font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
groups = defaultdict(list)
for p in sorted(Path(a.clips).glob("clip_*.mp4")):
    m = re.match(r"clip_(.+)_s(\d+)$", p.stem)
    if m:
        groups[m[1]].append((int(m[2]), p))
shots = list(groups)


def grab(p, n):
    cap = cv2.VideoCapture(str(p)); tot = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1; out = []
    for i in range(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, round(i * (tot - 1) / max(1, n - 1)))
        ok, f = cap.read()
        if ok:
            out.append(Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)).resize((W, H)))
    cap.release()
    return out


maxs = max((len(v) for v in groups.values()), default=1)
for page in range(0, len(shots), a.rows):
    chunk = shots[page:page + a.rows]
    sheet = Image.new("RGB", (90 + maxs * (a.frames * W + 8), len(chunk) * (H + 4)), "black")
    d = ImageDraw.Draw(sheet)
    for r, shot in enumerate(chunk):
        y = r * (H + 4)
        d.text((4, y + H // 2 - 8), shot, fill="yellow", font=font)
        for c, (k, p) in enumerate(sorted(groups[shot])):
            x0 = 90 + c * (a.frames * W + 8)
            for i, im in enumerate(grab(p, a.frames)):
                sheet.paste(im, (x0 + i * W, y))
            d.rectangle([x0, y, x0 + 30, y + 20], fill="black"); d.text((x0 + 3, y + 1), f"s{k}", fill="cyan", font=font)
    out = Path(f"{a.out}_{page // a.rows + 1}.png")
    sheet.save(out)
    print(out)
