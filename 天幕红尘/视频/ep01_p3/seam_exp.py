#!/usr/bin/env python3
"""在 p3 v2 成片上离线测量续段首帧亮度对齐的效果。"""

import json
import re
import signal
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from time import monotonic


HERE = Path(__file__).resolve().parent
VIDEO = HERE.parent / "第01集_p3_1-7至1-8_v2.mp4"
GROUP_PLAN = HERE / "ls_group/group_plan.json"
METADATA = HERE / "audio_meta_p3_master.json"
MANIFEST = HERE / "concat_p3_master.txt"
FPS = 30
WINDOW = 5
WIDTH, HEIGHT = 1280, 720
# build_v13 将两行字幕的顶线放在 y=590，黑边向上延伸 2px。
CROP_HEIGHT = 584
MAX_SECONDS = 9 * 60


def load_seams():
    specs = json.loads(METADATA.read_text(encoding="utf-8"))
    manifest_rows = MANIFEST.read_text(encoding="utf-8").splitlines()
    manifest_ids = []
    for row in manifest_rows:
        match = re.fullmatch(r"file '.*?/shots/seg_master_(.+)\.mov'", row)
        if match is None:
            raise ValueError(f"无法识别拼接清单条目 {row!r}")
        manifest_ids.append(match[1])
    if manifest_ids != [spec["id"] for spec in specs]:
        raise ValueError("master 拼接清单与元数据的片段顺序不一致")

    groups = json.loads(GROUP_PLAN.read_text(encoding="utf-8"))["groups"]
    grouped_pairs = {
        (left, right): group
        for group, info in groups.items()
        for left, right in zip(info["pieces"], info["pieces"][1:])
    }
    seams = []
    frame = 0
    for i, spec in enumerate(specs):
        right = spec["id"]
        continuation = re.fullmatch(r"(.+)_c([1-9]\d*)", right)
        if continuation is not None:
            base, number = continuation.groups()
            left = base if number == "1" else f"{base}_c{int(number) - 1}"
            if i == 0 or specs[i - 1]["id"] != left:
                raise ValueError(f"拼接清单在 {right} 之前缺少 {left}")
            seams.append((left, right, frame, grouped_pairs.pop((left, right), None)))
        # segbuild 按每片时长分别舍入，累加帧数可避开容器音频时间戳误差。
        frame += max(1, round(spec["dur"] * FPS))
    if len(seams) != 17 or grouped_pairs:
        raise ValueError(f"预期 17 处接缝且覆盖整镜口型分组，实际找到 {len(seams)} 处")
    return seams, frame


def decode_windows(seams, total_frames):
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
         "-of", "json", str(VIDEO)],
        check=True, capture_output=True, text=True,
    )
    stream, = json.loads(probe.stdout)["streams"]
    if (stream["width"], stream["height"], stream["r_frame_rate"],
            int(stream["nb_frames"])) != (WIDTH, HEIGHT, f"{FPS}/1", total_frames):
        raise ValueError("成片画幅、帧率或总帧数与 master 元数据不符")

    starts = [frame - WINDOW for _, _, frame, _ in seams]
    if (starts[0] < 0 or starts[-1] + 2 * WINDOW > total_frames
            or any(b - a < 2 * WINDOW for a, b in zip(starts, starts[1:]))):
        raise ValueError("接缝窗口越界或重叠")
    selection = "+".join(f"between(n,{start},{start + 2 * WINDOW - 1})" for start in starts)
    decoded = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-hwaccel", "none", "-i", str(VIDEO),
         "-map", "0:v:0", "-vf", f"select='{selection}',crop={WIDTH}:{CROP_HEIGHT}:0:0,extractplanes=y",
         "-fps_mode", "passthrough", "-c:v", "rawvideo", "-pix_fmt", "gray", "-f", "rawvideo", "-"],
        check=True, stdout=subprocess.PIPE,
    ).stdout
    frame_size = WIDTH * CROP_HEIGHT
    if len(decoded) != len(seams) * 2 * WINDOW * frame_size:
        raise ValueError("实际解码帧数与接缝窗口不符")
    pixels = memoryview(decoded)
    return [pixels[i:i + frame_size] for i in range(0, len(pixels), frame_size)]


def luma_alignment(frame, target_sum):
    """求平移后限幅至 0–255 的映射，用浮点亮度保持均值精度。"""
    histogram = Counter(frame)

    def shifted_sum(offset):
        return sum(min(255, max(0, value + offset)) * count
                   for value, count in histogram.items())

    # 两个相邻整数偏移之间，限幅后的每个像素仍随偏移线性变化。
    low, high = -255, 255
    while high - low > 1:
        mid = (low + high) // 2
        if shifted_sum(mid) < target_sum:
            low = mid
        else:
            high = mid
    low_sum, high_sum = shifted_sum(low), shifted_sum(high)
    offset = low + (target_sum - low_sum) / (high_sum - low_sum) if high_sum > low_sum else low
    return [min(255, max(0, value + offset)) for value in range(256)], offset


def measure(frames):
    # 用两侧未被调亮影响的 7 个邻帧对作共同分母。
    neighboring = [
        sum(abs(a - b) for a, b in zip(left, right)) / len(left)
        for i, (left, right) in enumerate(zip(frames, frames[1:]))
        if i not in (WINDOW - 1, WINDOW)
    ]
    baseline = median(neighboring)
    if baseline == 0:
        raise ValueError("邻帧差中位数为零，无法归一化")
    last, first, second = frames[WINDOW - 1:WINDOW + 2]
    lookup, offset = luma_alignment(first, sum(last))
    before = sum(abs(a - b) for a, b in zip(last, first)) / len(last)
    after = sum(abs(a - lookup[b]) for a, b in zip(last, first)) / len(last)
    next_before = sum(abs(a - b) for a, b in zip(first, second)) / len(last)
    next_after = sum(abs(lookup[a] - b) for a, b in zip(first, second)) / len(last)
    return before / baseline, after / baseline, next_before / baseline, next_after / baseline, offset


def aggregate(label, rows):
    before = mean(row[0] for row in rows)
    after = mean(row[1] for row in rows)
    reduction = f"{(1 - after / before):.2%}" if before else "未定义（对齐前均值为零）"
    next_before = mean(row[2] for row in rows)
    next_after = mean(row[3] for row in rows)
    return (f"{label}（{len(rows)} 处）  接缝均值 {before:.4f} → {after:.4f}  降幅 {reduction}"
            f"  续段首→次帧均值 {next_before:.4f} → {next_after:.4f}")


def stop_on_timeout(_signum, _frame):
    raise TimeoutError("单次运行达到 9 分钟上限，实验已停止")


def main():
    started = monotonic()
    signal.signal(signal.SIGALRM, stop_on_timeout)
    signal.alarm(MAX_SECONDS)
    job_id = datetime.now(timezone.utc).strftime("seam-exp-%Y%m%dT%H%M%S%fZ")
    try:
        seams, total_frames = load_seams()
        frames = decode_windows(seams, total_frames)
        lines = [
            f"jobId {job_id}",
            f"样本 {VIDEO.name}，{FPS} fps，共 {total_frames} 帧。",
            "接缝来自 concat_p3_master.txt 中主镜到续段及续段之间的拼接，"
            "按 audio_meta_p3_master.json 每片舍入后的帧数定位，并与 ls_group/group_plan.json 交叉核对。",
            "整镜口型分组覆盖 16 处。8k → 8k_c1 两片均未走口型处理，计入 17 处总样本。",
            f"每侧取 {WINDOW} 帧，裁去底部 {HEIGHT - CROP_HEIGHT} 像素的字幕带。"
            "帧差为保留区域的 Y 平面像素平均绝对差。",
            "仅在内存中对续段首帧的 Y 加常量并限幅，使保留区域均值与前片末帧相等。"
            "两个受首帧修改影响的帧对共用其余 7 个邻帧差的中位数作为分母。",
            "",
            "接缝 | 续段首帧序号（从 0 起） | 整镜口型组 | 接缝 前 → 后 | 续段首→次帧 前 → 后 | Y 偏移",
        ]
        rows = []
        grouped_rows = []
        for i, (left, right, frame, group) in enumerate(seams):
            start = i * 2 * WINDOW
            row = measure(frames[start:start + 2 * WINDOW])
            before, after, next_before, next_after, offset = row
            rows.append(row)
            if group is not None:
                grouped_rows.append(row)
            lines.append(f"{left} → {right} | {frame} | {group or '未走口型'} | "
                         f"{before:.4f} → {after:.4f} | {next_before:.4f} → {next_after:.4f} | {offset:+.4f}")
        lines.extend(["", aggregate("全部接缝", rows), aggregate("整镜口型接缝", grouped_rows),
                      f"本地计算耗时 {monotonic() - started:.1f} 秒"])
        summary = "\n".join(lines) + "\n"
        output_dir = HERE / "seam_exp"
        output_dir.mkdir(exist_ok=True)
        output = output_dir / f"summary_{job_id}.txt"
        with output.open("x", encoding="utf-8") as report:
            report.write(summary)
        print(summary, end="")
        print(f"汇总文件 {output}")
    except TimeoutError as exc:
        raise SystemExit(f"{job_id} {exc}") from None
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    main()
