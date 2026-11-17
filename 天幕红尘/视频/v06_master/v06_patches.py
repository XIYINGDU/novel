#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Surgical, texture-preserving visual & audio helpers for《天幕红尘》Ep01 v0.6 master (built cleanly on v0.4)."""

import array
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from pydub import AudioSegment

SR = 48000
W, H = 1280, 720


def find_quad_coeffs(dst_pts: list[tuple[float, float]], src_pts: list[tuple[float, float]]) -> list[float]:
    """Compute PIL.Image.PERSPECTIVE 8-parameter homography mapping dst_pts -> src_pts."""
    a_rows, b_vals = [], []
    for (x, y), (u, v) in zip(dst_pts, src_pts):
        a_rows.append([x, y, 1.0, 0.0, 0.0, 0.0, -u * x, -u * y])
        b_vals.append(float(u))
        a_rows.append([0.0, 0.0, 0.0, x, y, 1.0, -v * x, -v * y])
        b_vals.append(float(v))
    mat = [a_rows[i] + [b_vals[i]] for i in range(8)]
    for col in range(8):
        piv = max(range(col, 8), key=lambda r: abs(mat[r][col]))
        mat[col], mat[piv] = mat[piv], mat[col]
        div = mat[col][col]
        for j in range(col, 9):
            mat[col][j] /= div
        for r in range(8):
            if r != col and mat[r][col] != 0.0:
                fac = mat[r][col]
                for j in range(col, 9):
                    mat[r][j] -= fac * mat[col][j]
    return [mat[i][8] for i in range(8)]


def _warp_patch_to_frame(
    frame_rgb: np.ndarray,
    patch: Image.Image,
    dst_quad: list[tuple[float, float]],
    feather: float = 2.0,
    preserve_bright_delta_from: np.ndarray | None = None,
) -> np.ndarray:
    """Warp `patch` smoothly into `dst_quad` on `frame_rgb`, optionally preserving cigarette smoke deltas."""
    h, w = frame_rgb.shape[:2]
    pw, ph = patch.size
    coeffs = find_quad_coeffs(dst_quad, [(0.0, 0.0), (float(pw), 0.0), (float(pw), float(ph)), (0.0, float(ph))])
    warped = np.array(
        patch.convert("RGB").transform((w, h), Image.PERSPECTIVE, coeffs, Image.BICUBIC),
        dtype=np.float32,
    )
    msrc = Image.new("L", (pw, ph), 255)
    wmask = msrc.transform((w, h), Image.PERSPECTIVE, coeffs, Image.BILINEAR)
    if feather > 0:
        wmask = wmask.filter(ImageFilter.GaussianBlur(feather))
    alpha = (np.array(wmask, dtype=np.float32) / 255.0)[:, :, None]
    out = warped * alpha + frame_rgb.astype(np.float32) * (1.0 - alpha)
    if preserve_bright_delta_from is not None:
        smoke = np.clip(frame_rgb.astype(np.float32) - preserve_bright_delta_from.astype(np.float32), 0.0, 65.0)
        out = out + smoke * alpha * 0.85
    return np.clip(out, 0, 255).astype(np.uint8)


def patch_05_photo_frames(sid: str, frames_rgb: list[np.ndarray], ins2_still_path: Path) -> list[np.ndarray]:
    """Replace the mismatched tabletop photo inside 05a and 05c with the exact 4-women '裕香阁' photo."""
    if sid not in ("05a", "05c") or not ins2_still_path.exists():
        return frames_rgb

    ins2 = Image.open(ins2_still_path).convert("RGB")
    iw, ih = ins2.size
    if sid == "05a":
        patch = ins2.crop((int(iw * 0.275), int(ih * 0.21), int(iw * 0.745), int(ih * 0.77)))
        patch = ImageEnhance.Brightness(patch).enhance(0.56).filter(ImageFilter.GaussianBlur(0.8))
        quad0 = [(948.0, 549.0), (1040.0, 555.0), (1024.0, 621.0), (937.0, 609.0)]
        ref0 = frames_rgb[0]
        return [_warp_patch_to_frame(fr, patch, quad0, feather=2.0, preserve_bright_delta_from=ref0) for fr in frames_rgb]

    from scipy.signal import fftconvolve

    patch = ins2.crop((int(iw * 0.305), int(ih * 0.21), int(iw * 0.740), int(ih * 0.785)))
    patch = ImageEnhance.Brightness(patch).enhance(0.75).filter(ImageFilter.GaussianBlur(0.6))
    quad0 = np.array([(1047.0, 491.0), (1114.0, 495.0), (1107.0, 597.0), (1035.0, 592.0)], dtype=np.float32)
    tmpl = frames_rgb[0][475:615, 1030:1135].mean(axis=2).astype(np.float32)
    tmpl -= tmpl.mean()
    tmpl_rev = tmpl[::-1, ::-1]
    out_frames: list[np.ndarray] = []
    origin_y, origin_x = 475 - 445, 1030 - 990
    for fr in frames_rgb:
        roi = fr[445:650, 990:1175].mean(axis=2).astype(np.float32)
        roi -= roi.mean()
        corr = fftconvolve(roi, tmpl_rev, mode="valid")
        my, mx = np.unravel_index(np.argmax(corr), corr.shape)
        dy, dx = float(my - origin_y), float(mx - origin_x)
        q = [(float(x + dx), float(y + dy)) for x, y in quad0]
        out_frames.append(_warp_patch_to_frame(fr, patch, q, feather=2.0))
    return out_frames


def patch_02b_sky_wedge(frames_rgb: list[np.ndarray]) -> list[np.ndarray]:
    """Melt ONLY the small cool-blue top sky wedge between buildings in clip_02b_v3 into nocturnal Paris facade darkness."""
    from scipy.ndimage import gaussian_filter

    xs = np.arange(W, dtype=np.float32)[None, :]
    ys = np.arange(H, dtype=np.float32)[:, None]
    # Generous spatial window around upper central alley gap (x=510..840, y=0..155); stones/warm walls unaffected
    wx = np.clip((xs - 505.0) / 35.0, 0.0, 1.0) * np.clip((845.0 - xs) / 35.0, 0.0, 1.0)
    wy = np.clip((160.0 - ys) / 38.0, 0.0, 1.0)
    spatial = wx * wy

    out = []
    for fr in frames_rgb:
        f32 = fr.astype(np.float32)
        # Cool dusk blue metric: B clearly exceeds R and green exceeds red
        blue_excess = f32[:, :, 2] - f32[:, :, 0]
        cool_w = np.clip((blue_excess - 6.0) / 18.0, 0.0, 1.0)
        # Dilate slightly via blur so sky-to-roofline fringe is completely absorbed without darkening hair/skin
        # Hair & beanie are very dark (<35 lum); warm buildings have R > B so cool_w == 0
        m = gaussian_filter(cool_w * spatial, sigma=2.2)[:, :, None]
        # Shift blue sky pixels to dark warm night shadow rgb ~ (10, 10, 11)
        night_tone = np.stack([f32[:, :, 0] * 0.18, f32[:, :, 0] * 0.17, f32[:, :, 0] * 0.16], axis=-1)
        night_tone = np.clip(night_tone, 4.0, 18.0)
        res = f32 * (1.0 - m) + night_tone * m
        out.append(np.clip(res, 0, 255).astype(np.uint8))
    return out


def darken_11b_midnight_window(frames_rgb: list[np.ndarray]) -> list[np.ndarray]:
    """Turn the cool grey-blue right window glass in 11b into pitch-black Moscow midnight without touching Luo."""
    xs = np.arange(W, dtype=np.float32)[None, :]
    ys = np.arange(H, dtype=np.float32)[:, None]
    mx = np.clip((xs - 1085.0) / 80.0, 0.0, 1.0)
    mx = mx * mx * (3.0 - 2.0 * mx)
    my = np.clip((455.0 - ys) / 70.0, 0.0, 1.0)
    my = my * my * (3.0 - 2.0 * my)
    mask = (mx * my)[:, :, None] * 0.85
    keep = 1.0 - mask
    dark_mul = mask * np.array([[[0.16, 0.16, 0.24]]], dtype=np.float32)
    out = []
    for fr in frames_rgb:
        f32 = fr.astype(np.float32)
        res = f32 * (keep + dark_mul)
        out.append(np.clip(res, 0, 255).astype(np.uint8))
    return out


def apply_clean_crt_turnoff(
    arr: np.ndarray,
    dt_sec: float,
    screen_box: tuple[int, int, int, int] = (456, 76, 928, 472),
) -> np.ndarray:
    """Clean CRT phosphor collapse inside the bezel: crisp thin horizontal beam -> dot -> dark glass, preserving room wood/hand."""
    from scipy.ndimage import gaussian_filter

    if dt_sec < 0.0:
        return arr
    sx0, sy0, sx1, sy1 = screen_box
    cx, cy = (sx0 + sx1) * 0.5, (sy0 + sy1) * 0.5
    sw, sh = sx1 - sx0, sy1 - sy0
    out = arr.astype(np.float32)

    ys_grid, xs_grid = np.mgrid[0:H, 0:W].astype(np.float32)
    nx = (xs_grid - cx) / (sw * 0.502)
    ny = (ys_grid - cy) / (sh * 0.502)
    r_screen = np.power(np.power(np.abs(nx), 5.0) + np.power(np.abs(ny), 5.0), 0.20)
    screen_alpha = np.clip((1.02 - r_screen) / 0.05, 0.0, 1.0)[:, :, None]

    # Very subtle dim of blue phosphor spill around bezel (keeps warm wooden wall panels & outstretched hand fully visible)
    halo = np.clip(1.0 - np.hypot((xs_grid - cx) / (sw * 0.95), (ys_grid - cy) / (sh * 0.95)), 0.0, 1.0)[:, :, None]
    spill_t = min(1.0, dt_sec / 0.12)
    out = out * (1.0 - halo * 0.14 * spill_t * np.array([[[0.25, 0.30, 0.50]]], dtype=np.float32))

    # True unpowered charcoal CRT glass with curved tube sheen (zero broadcast ghosting!)
    off_t = min(1.0, (dt_sec + 0.032) / 0.045)
    sheen = np.exp(-(((xs_grid - (cx - sw * 0.14)) / (sw * 0.48)) ** 2 + ((ys_grid - (cy - sh * 0.16)) / (sh * 0.52)) ** 2))
    dark_glass = (
        np.array([[[8.0, 9.0, 10.5]]], dtype=np.float32)
        + sheen[:, :, None] * np.array([[[11.0, 12.5, 15.0]]], dtype=np.float32)
    )
    out = out * (1.0 - screen_alpha * off_t) + dark_glass * (screen_alpha * off_t)

    # Crisp thin horizontal scanline collapse (zero overblown white screen fog!) -> center pinpoint dot -> off
    if dt_sec < 0.095:
        u = dt_sec / 0.095
        half_h = 2.3 - 0.7 * u
        half_w = sw * 0.49 * max(0.04, (1.0 - u) ** 1.45)
        band = np.exp(-0.5 * ((ys_grid - cy) / half_h) ** 2) * np.exp(-0.5 * ((xs_grid - cx) / half_w) ** 4)
        bri = 238.0 * (1.0 - 0.15 * u)
        glow = band[:, :, None] * np.array([[[bri * 0.90, bri * 0.96, 255.0]]], dtype=np.float32)
        out = np.maximum(out, out * (1.0 - screen_alpha * band[:, :, None] * 0.45) + glow * screen_alpha)
    elif dt_sec < 0.20:
        u = (dt_sec - 0.095) / 0.105
        radius = max(1.8, 7.0 * (1.0 - 0.7 * u))
        dot = np.exp(-((xs_grid - cx) ** 2 + (ys_grid - cy) ** 2) / (2.0 * radius * radius))
        fade = (1.0 - u) ** 1.8
        glow = dot[:, :, None] * np.array([[[190.0 * fade, 210.0 * fade, 240.0 * fade]]], dtype=np.float32)
        out = out + glow * screen_alpha

    return np.clip(out, 0, 255).astype(np.uint8)


def remove_10b_right_watch(frames_rgb: list[np.ndarray]) -> list[np.ndarray]:
    """Surgically replace the stainless-steel wristwatch & upper bezel crown on the right wrist in clip_10b_v3 with native forearm skin."""
    from scipy.ndimage import gaussian_filter, shift as nd_shift
    from scipy.signal import fftconvolve

    f0 = frames_rgb[0]
    # Track specifically on the prominent right shirt cuff fold + lower forearm edge (very stable texture)
    tmpl = f0[260:465, 1185:1270].mean(axis=2).astype(np.float32)
    tmpl -= tmpl.mean()
    tmpl_rev = tmpl[::-1, ::-1]
    orig_y, orig_x = 260 - 220, 1185 - 1140

    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    # Generous diagonal strap band (xL safely 18px left of strap edge so hand never clips strap left link!)
    x_l0 = 1096.0 + (ys - 220.0) * ((1078.0 - 1096.0) / 238.0)
    x_r0 = 1268.0 + (ys - 220.0) * ((1238.0 - 1268.0) / 238.0)
    # Clean dorsal wrist roofline interpolated from clean forearm at x=1110 (~y=234) sloping down gently toward cuff (~y=260)
    y_roof0 = 234.0 + np.clip((xs - 1105.0) / 145.0, 0.0, 1.0) * 26.0
    watch_y0 = np.clip((ys - (y_roof0 - 6.0)) / 10.0, 0.0, 1.0) * np.clip((462.0 - ys) / 14.0, 0.0, 1.0)
    watch_x0 = np.clip((xs - x_l0) / 16.0, 0.0, 1.0) * np.clip((x_r0 - xs) / 8.0, 0.0, 1.0)
    base_mask0 = watch_x0 * watch_y0

    # Upper crown mask: erases the protruding silver bezel bump above y_roof0 cleanly into dark mahogany wood (x=1115..1279)
    crown_mask0 = (
        np.clip((ys - 196.0) / 8.0, 0.0, 1.0)
        * np.clip(((y_roof0 + 6.0) - ys) / 8.0, 0.0, 1.0)
        * np.clip((xs - 1115.0) / 12.0, 0.0, 1.0)
        * np.clip((1279.0 - xs) / 4.0, 0.0, 1.0)
    )

    out = []
    for fr in frames_rgb:
        f32 = fr.astype(np.float32)
        roi = f32[220:495, 1140:1279].mean(axis=2)
        roi -= roi.mean()
        corr = fftconvolve(roi, tmpl_rev, mode="valid")
        my, mx = np.unravel_index(np.argmax(corr), corr.shape)
        dy, dx = float(my - orig_y), float(mx - orig_x)

        m_shifted = nd_shift(base_mask0, shift=(dy, dx), order=1, mode="constant", cval=0.0)
        c_shifted = nd_shift(crown_mask0, shift=(dy, dx), order=1, mode="constant", cval=0.0)

        r, g, b = f32[:, :, 0], f32[:, :, 1], f32[:, :, 2]
        lum = (r + g + b) / 3.0
        y_roof_shifted = 234.0 + dy + np.clip((xs - (1105.0 + dx)) / 145.0, 0.0, 1.0) * 26.0

        # Detect crisp cuff seam per row (only start searching below top cuff collar y >= 256+dy, right of strap)
        is_cuff = np.zeros((H, W), dtype=np.float32)
        y_active = np.where((m_shifted.max(axis=1) > 0.02) | (c_shifted.max(axis=1) > 0.02))[0]
        cuff_x_per_row: dict[int, int] = {}
        cuff_top_y = int(round(256.0 + dy))
        for y in y_active:
            if y < cuff_top_y:
                cuff_x_per_row[y] = 1279
                continue
            search_x0 = max(1178, int(round(1224.0 + dx - (y - (250.0 + dy)) * 0.14)))
            row_r = r[y, search_x0:]
            row_b = b[y, search_x0:]
            row_l = lum[y, search_x0:]
            cloth = (row_l > 80.0) & ((row_r - row_b) < 20.0)
            cx_edge = 1279
            for j in range(len(cloth) - 5):
                if np.all(cloth[j : j + 5]):
                    cx_edge = search_x0 + j
                    break
            cuff_x_per_row[y] = cx_edge
            is_cuff[y, cx_edge:] = 1.0

        cuff_keep = 1.0 - gaussian_filter(is_cuff, sigma=1.6)
        mask = np.clip(m_shifted * cuff_keep, 0.0, 1.0)
        crown_m = np.clip(c_shifted * cuff_keep, 0.0, 1.0)

        # Build 2D high-pass forearm skin pore texture from clean left forearm region [200:490, 955:1155]
        src_crop = f32[200:490, 955:1155]
        src_smooth = gaussian_filter(src_crop, sigma=(7.5, 7.5, 0.0))
        src_hp = src_crop - src_smooth

        synth = f32.copy()
        for y in y_active:
            wood_row = np.median(f32[max(195, min(230, y)) : max(195, min(230, y)) + 3, 1085:1115].reshape(-1, 3), axis=0)
            wood_row = np.minimum(wood_row, np.array([15.0, 8.0, 5.0], dtype=np.float32))
            if crown_m[y].max() > 0.03:
                c_cols = np.where(crown_m[y] > 0.03)[0]
                if len(c_cols):
                    synth[y, int(c_cols[0]) : int(c_cols[-1]) + 1] = wood_row[None, :]

            row_m = mask[y]
            cols = np.where(row_m > 0.03)[0]
            if len(cols) == 0:
                continue
            xl, xr = int(cols[0]), int(cols[-1])
            la0, la1 = max(950, xl - 26), max(955, xl - 5)
            y0s, y1s = max(0, y - 2), min(H, y + 3)
            left_rgb = np.median(f32[y0s:y1s, la0:la1].reshape(-1, 3), axis=0)
            right_rgb = left_rgb * 0.80

            cx_edge = cuff_x_per_row.get(y, xr + 1)
            xs_span = np.arange(xl, xr + 1, dtype=np.float32)
            u = (xs_span - xl) / max(1.0, float(xr - xl))
            cuff_shadow = 1.0 - 0.36 * np.exp(-np.maximum(0.0, float(cx_edge) - xs_span) / 9.0)
            base_grad = (left_rgb[None, :] * (1.0 - u[:, None]) + right_rgb[None, :] * u[:, None]) * cuff_shadow[:, None]

            sy_idx = max(0, min(src_hp.shape[0] - 1, y - 200))
            sx_starts = np.clip((xs_span.astype(np.int32) - 125) - 955, 0, src_hp.shape[1] - 1)
            detail = src_hp[sy_idx, sx_starts] * 0.90
            skin_vals = base_grad + detail
            roof_w = np.clip((float(y) - y_roof_shifted[y, xl : xr + 1]) / 8.0, 0.0, 1.0)[:, None]
            synth[y, xl : xr + 1] = wood_row[None, :] * (1.0 - roof_w) + skin_vals * roof_w

        # Erase ONLY chrome/bright watch lug highlights above y_roof_shifted while keeping existing dark mahogany untouched
        eff_crown = crown_m * np.clip((lum - 24.0) / 14.0, 0.0, 1.0)
        total_m = np.maximum(gaussian_filter(mask, sigma=2.4), gaussian_filter(eff_crown, sigma=2.4))[:, :, None]
        res = f32 * (1.0 - total_m) + synth * total_m
        out.append(np.clip(res, 0, 255).astype(np.uint8))

    return out


def apply_true_peak_limiter(seg: AudioSegment, ceiling_db: float = -1.5) -> AudioSegment:
    """Soft-knee lookahead peak limiter + hard ceiling clamp so 0 samples exceed `ceiling_db`."""
    from scipy.ndimage import gaussian_filter1d, maximum_filter1d

    arr = np.array(seg.set_frame_rate(SR).set_channels(1).set_sample_width(2).get_array_of_samples(), dtype=np.float32) / 32768.0
    ceiling = 10.0 ** (ceiling_db / 20.0)
    knee = ceiling * 0.88
    abs_arr = np.abs(arr)
    win = int(SR * 0.004)
    env = maximum_filter1d(abs_arr, size=max(3, win))
    env = gaussian_filter1d(env, sigma=max(1.0, win * 0.35))
    gain = np.ones_like(arr)
    over = env > knee
    if np.any(over):
        excess = env[over] - knee
        headroom = ceiling - knee
        compressed = knee + headroom * np.tanh(excess / max(1e-6, headroom * 1.15))
        gain[over] = compressed / np.maximum(env[over], 1e-6)
    limited = np.clip(arr * gain, -ceiling * 0.998, ceiling * 0.998)
    pcm = np.clip(np.round(limited * 32767.0), -32767, 32767).astype(np.int16)
    return AudioSegment(pcm.tobytes(), frame_rate=SR, sample_width=2, channels=1)
