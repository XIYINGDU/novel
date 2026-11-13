#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local Pillow VFX pass: lock 100% pixel-identical family photo (07_v3) & '見路不走' scroll (11a_v3)."""

from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter

V02_STILLS = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v02_pilot/stills")
V03_STILLS = Path("/Users/duxiying/Documents/novel/天幕红尘/视频/v03_pilot/stills")
V03_STILLS.mkdir(parents=True, exist_ok=True)


def find_quad_coeffs(dst_pts, src_pts):
    """Compute PIL.Image.PERSPECTIVE 8-parameter homography mapping dst_pts -> src_pts."""
    # Solve 8x8 linear system using pure Python Gaussian elimination (no numpy dependency needed!)
    A = []
    B = []
    for (x, y), (u, v) in zip(dst_pts, src_pts):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        B.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        B.append(v)
    n = 8
    M = [A[i] + [B[i]] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        M[col], M[piv] = M[piv], M[col]
        div = M[col][col]
        for j in range(col, n + 1):
            M[col][j] /= div
        for r in range(n):
            if r != col and M[r][col] != 0:
                factor = M[r][col]
                for j in range(col, n + 1):
                    M[r][j] -= factor * M[col][j]
    return [M[i][n] for i in range(n)]


def paste_perspective(base: Image.Image, patch: Image.Image, dst_quad: list[tuple[float, float]], feather: int = 3) -> Image.Image:
    w, h = base.size
    pw, ph = patch.size
    src_quad = [(0, 0), (pw, 0), (pw, ph), (0, ph)]
    coeffs = find_quad_coeffs(dst_quad, src_quad)
    warped = patch.convert("RGBA").transform((w, h), Image.PERSPECTIVE, coeffs, Image.BICUBIC)
    mask_src = Image.new("L", (pw, ph), 255)
    # Slight inner border inset so mask edges feather seamlessly
    warped_mask = mask_src.transform((w, h), Image.PERSPECTIVE, coeffs, Image.BILINEAR)
    if feather > 0:
        warped_mask = warped_mask.filter(ImageFilter.GaussianBlur(feather))
    out = base.copy().convert("RGBA")
    out.paste(warped, (0, 0), warped_mask)
    return out.convert("RGB")


def build_locked_stills():
    # 1. Lock 11a_v3: warp exact '見路不走' inner silk/xuan scroll from still_12a.png into the wooden frame of still_11.png
    s11 = Image.open(V02_STILLS / "still_11.png").convert("RGB")
    s12a = Image.open(V02_STILLS / "still_12a.png").convert("RGB")
    # Inner xuan-paper + silk mat region of still_12a.png (1280x720)
    scroll_crop = s12a.crop((148, 188, 1132, 424))
    scroll_crop = ImageEnhance.Brightness(scroll_crop).enhance(0.90)
    # Exact 4 inner corners of the wooden plaque mat in still_11.png (1280x720)
    dst_11 = [(522, 122), (1182, 85), (1186, 280), (524, 290)]
    s11_locked = paste_perspective(s11, scroll_crop, dst_11, feather=2)
    out_11a = V03_STILLS / "still_11a_v3.png"
    s11_locked.save(out_11a)
    print(f"[locked] {out_11a.name} <- exact '見路不走' scroll from still_12a.png")

    # 2. Lock 07_v3: warp exact 4-women family photo from still_05_ins2.png into the desk frame of still_07.png
    ins2_path = V03_STILLS / "still_05_ins2.png"
    if ins2_path.exists():
        s07 = Image.open(V02_STILLS / "still_07.png").convert("RGB")
        ins2 = Image.open(ins2_path).convert("RGB")
        # Center crop of the family portrait in still_05_ins2.png
        iw, ih = ins2.size
        photo_crop = ins2.crop((int(iw * 0.24), int(ih * 0.16), int(iw * 0.76), int(ih * 0.84)))
        photo_crop = ImageEnhance.Brightness(photo_crop).enhance(0.88)
        # Exact 4 inner corners of the desk photo frame in still_07.png (1280x720)
        dst_07 = [(968, 456), (1173, 474), (1134, 650), (938, 616)]
        s07_locked = paste_perspective(s07, photo_crop, dst_07, feather=2)
        out_07 = V03_STILLS / "still_07_v3.png"
        s07_locked.save(out_07)
        print(f"[locked] {out_07.name} <- exact 4-women family photo from still_05_ins2.png")


if __name__ == "__main__":
    build_locked_stills()
