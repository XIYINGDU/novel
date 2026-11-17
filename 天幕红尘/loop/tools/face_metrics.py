#!/usr/bin/env python3
"""表情漂移的自动量尺（/tm-qa 的机器半边）。

逐帧用 MediaPipe FaceLandmarker 的 blendshape 读出：
  smile   = mouthSmileLeft/Right 均值        —— 笑意（悲恸/冷硬镜头应接近 0）
  cheek   = cheekSquint 均值                  —— 颧肌上提，「哭像笑」的关键
  brow_in = browInnerUp                       —— 悲伤眉
  frown   = mouthFrownLeft/Right 均值
  jaw     = jawOpen
多张脸时取面积最大的一张。

用法（在 天幕红尘/ 下）：
  uv run -q --python 3.11 --with mediapipe==0.10.21 --with opencv-python-headless \
      python loop/tools/face_metrics.py <视频或图片> [...] [--step 1] [--json out.json]
"""
import argparse, json, sys
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

MODEL = Path(__file__).resolve().parent / "models" / "face_landmarker.task"
KEYS = {
    "smile": ("mouthSmileLeft", "mouthSmileRight"),
    "cheek": ("cheekSquintLeft", "cheekSquintRight"),
    "brow_in": ("browInnerUp",),
    "frown": ("mouthFrownLeft", "mouthFrownRight"),
    "jaw": ("jawOpen",),
}
SMILE_T = 0.30  # 单帧 smile 超过即记为「笑帧」


def make_detector():
    o = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL)),
        output_face_blendshapes=True,
        num_faces=3,
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
    )
    return mp.tasks.vision.FaceLandmarker.create_from_options(o)


def frame_scores(det, bgr):
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    res = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    if not res.face_blendshapes:
        return None
    areas = []
    for lm in res.face_landmarks:
        xs, ys = [p.x for p in lm], [p.y for p in lm]
        areas.append((max(xs) - min(xs)) * (max(ys) - min(ys)))
    bs = {c.category_name: c.score for c in res.face_blendshapes[int(np.argmax(areas))]}
    return {k: float(np.mean([bs[n] for n in names])) for k, names in KEYS.items()}


def frames(path: Path, step: int):
    if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        img = cv2.imread(str(path))
        if img is not None:
            yield 0, img
        return
    cap = cv2.VideoCapture(str(path))
    i = 0
    while True:
        ok, img = cap.read()
        if not ok:
            break
        if i % step == 0:
            yield i, img
        i += 1
    cap.release()


def analyze(det, path: Path, step: int):
    rows = []
    for i, img in frames(path, step):
        s = frame_scores(det, img)
        if s:
            rows.append({"f": i, **s})
    if not rows:
        return {"file": str(path), "faces": 0}
    a = {k: np.array([r[k] for r in rows]) for k in KEYS}
    return {
        "file": str(path),
        "faces": len(rows),
        "smile_mean": round(float(a["smile"].mean()), 3),
        "smile_p90": round(float(np.percentile(a["smile"], 90)), 3),
        "smile_max": round(float(a["smile"].max()), 3),
        "smile_frames": int((a["smile"] > SMILE_T).sum()),
        # 读成笑：嘴角拉开但内眉没抬（真悲伤是内眉上抬+嘴角下拉）
        "laugh_read": int(((a["smile"] > SMILE_T) & (a["brow_in"] < 0.15)).sum()),
        "cheek_mean": round(float(a["cheek"].mean()), 3),
        "brow_in_mean": round(float(a["brow_in"].mean()), 3),
        "frown_mean": round(float(a["frown"].mean()), 3),
        "jaw_mean": round(float(a["jaw"].mean()), 3),
        "frames": rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--step", type=int, default=1)
    ap.add_argument("--json")
    a = ap.parse_args()
    det = make_detector()
    out = [analyze(det, Path(p), a.step) for p in a.paths]
    print(f"{'file':52} {'n':>3} {'smile_mean':>10} {'p90':>6} {'max':>6} {'笑帧':>4} {'读成笑':>5} {'cheek':>6} {'brow_in':>7} {'frown':>6} {'jaw':>5}")
    for r in out:
        name = Path(r["file"]).name[:52]
        if not r["faces"]:
            print(f"{name:52}   0  （没检到脸）")
            continue
        print(f"{name:52} {r['faces']:>3} {r['smile_mean']:>10} {r['smile_p90']:>6} {r['smile_max']:>6} "
              f"{r['smile_frames']:>4} {r['laugh_read']:>5} {r['cheek_mean']:>6} {r['brow_in_mean']:>7} {r['frown_mean']:>6} {r['jaw_mean']:>5}")
    if a.json:
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
