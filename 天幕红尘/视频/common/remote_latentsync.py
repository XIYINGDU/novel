#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""云端通用 LatentSync-1.6（512x512 V2V 口型）worker。从 ep01_p2/remote_latentsync_p2.py 通用化。
读 /content/lipsync_job.json：
  {"in": "/content/lipsync_in.tar.gz", "out": "/content/lipsync_out.tar.gz",
   "roi": {sid: "left_0.56" | "right_0.46"},       # 只在画面左/右某比例内找脸（双人镜）
   "guidance": {sid: 1.75}, "default_g": 1.55,     # A-LIPSYNC-GUIDANCE-TIER
   "steps": 20}
输入包内是 vid_<sid>.mp4（25fps）+ stem_<sid>.wav（只含画内开口者，A-LIPSYNC-CLEAN-STEM）。
检不到脸的镜头回退为原片（日志 [lipsync fallback]）。
"""

import json
import os
import zlib
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

JOB = json.load(open("/content/lipsync_job.json"))
WORK = Path("/tmp/lipsync_work")
IN_DIR = WORK / "in"
OUT_DIR = WORK / "out"
REPO_DIR = Path("/content/LatentSync")

for d in (IN_DIR, OUT_DIR):  # 同一台机器连跑多个分片：先清掉上一片的输入输出
    shutil.rmtree(d, ignore_errors=True)
for d in (WORK, IN_DIR, OUT_DIR):
    d.mkdir(parents=True, exist_ok=True)

print("[1/5] Installing lightweight LatentSync dependencies (preserving system torch)...", flush=True)
subprocess.check_call(
    [
        sys.executable, "-m", "pip", "install", "-q",
        "diffusers", "transformers", "accelerate", "einops", "omegaconf",
        "opencv-python-headless", "librosa", "soundfile", "imageio", "imageio-ffmpeg",
        "kornia", "insightface", "onnxruntime", "ffmpeg-python", "more-itertools",
        "regex", "matplotlib", "huggingface_hub",
    ]
)

if not (REPO_DIR / "scripts" / "inference.py").exists():
    print("[2/5] Cloning bytedance/LatentSync...", flush=True)
    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    env_git = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1")
    subprocess.check_call(
        ["git", "clone", "--depth", "1", "https://github.com/bytedance/LatentSync.git", str(REPO_DIR)],
        env=env_git,
    )

for rel_p in ("latentsync/models/attention.py", "latentsync/models/motion_module.py", "latentsync/models/stable_syncnet.py"):
    py_f = REPO_DIR / rel_p
    if py_f.exists():
        txt = py_f.read_text(encoding="utf-8")
        if "from diffusers.models.attention import FeedForward, AdaLayerNorm" in txt:
            txt = txt.replace(
                "from diffusers.models.attention import FeedForward, AdaLayerNorm",
                "try:\n    from diffusers.models.attention import FeedForward\nexcept ImportError:\n    from diffusers.models.attention_processor import FeedForward\ntry:\n    from diffusers.models.attention import AdaLayerNorm\nexcept ImportError:\n    from diffusers.models.normalization import AdaLayerNorm",
            )
            py_f.write_text(txt, encoding="utf-8")

util_py = REPO_DIR / "latentsync" / "utils" / "util.py"
util_txt = util_py.read_text(encoding="utf-8")
if "from decord import AudioReader, VideoReader" in util_txt:
    util_txt = util_txt.replace("from decord import AudioReader, VideoReader", "import librosa")
    util_txt = util_txt.replace(
        "def read_video(video_path: str, change_fps=True, use_decord=True):",
        "def read_video(video_path: str, change_fps=False, use_decord=False):",
    )
    old_audio_fn = """def read_audio(audio_path: str, audio_sample_rate: int = 16000):
    if audio_path is None:
        raise ValueError("Audio path is required.")
    ar = AudioReader(audio_path, sample_rate=audio_sample_rate, mono=True)

    # To access the audio samples
    audio_samples = torch.from_numpy(ar[:].asnumpy())
    audio_samples = audio_samples.squeeze(0)

    return audio_samples"""
    new_audio_fn = """def read_audio(audio_path: str, audio_sample_rate: int = 16000):
    if audio_path is None:
        raise ValueError("Audio path is required.")
    wav, _ = librosa.load(audio_path, sr=audio_sample_rate, mono=True)
    return torch.from_numpy(wav.astype(np.float32))"""
    util_txt = util_txt.replace(old_audio_fn, new_audio_fn)
    util_py.write_text(util_txt, encoding="utf-8")

fd_py = REPO_DIR / "latentsync" / "utils" / "face_detector.py"
fd_txt = fd_py.read_text(encoding="utf-8")
if "_CACHED_FACE_APP" not in fd_txt:
    fd_txt = fd_txt.replace(
        "INSIGHTFACE_DETECT_SIZE = 512",
        "INSIGHTFACE_DETECT_SIZE = 512\n_CACHED_FACE_APP = None",
    )
    old_init = """    def __init__(self, device="cuda"):
        self.app = FaceAnalysis(
            allowed_modules=["detection", "landmark_2d_106"],
            root="checkpoints/auxiliary",
            providers=["CUDAExecutionProvider"],
        )
        self.app.prepare(ctx_id=cuda_to_int(device), det_size=(INSIGHTFACE_DETECT_SIZE, INSIGHTFACE_DETECT_SIZE))"""
    new_init = """    def __init__(self, device="cuda"):
        global _CACHED_FACE_APP
        if _CACHED_FACE_APP is None:
            _CACHED_FACE_APP = FaceAnalysis(
                allowed_modules=["detection", "landmark_2d_106"],
                root="checkpoints/auxiliary",
                providers=["CPUExecutionProvider"],
            )
            _CACHED_FACE_APP.prepare(ctx_id=0, det_size=(INSIGHTFACE_DETECT_SIZE, INSIGHTFACE_DETECT_SIZE))
        self.app = _CACHED_FACE_APP"""
    fd_txt = fd_txt.replace(old_init, new_init)
    fd_txt = fd_txt.replace("def __call__(self, frame, threshold=0.5):", "def __call__(self, frame, threshold=0.25):")
    fd_txt = fd_txt.replace(
        "        faces = self.app.get(frame)",
        (
            "        import os as _os\n"
            "        _roi = _os.environ.get('LS_ROI_MODE', '')\n"
            "        if _roi:\n"
            "            frame = frame.copy()\n"
            "            _w = frame.shape[1]\n"
            "            _side, _frac = _roi.split('_')\n"
            "            _frac = float(_frac)\n"
            "            if _side == 'left':\n"
            "                frame[:, int(_w * _frac):] = 0\n"
            "            else:\n"
            "                frame[:, :int(_w * _frac)] = 0\n"
            "        faces = self.app.get(frame)\n"
            "        if len(faces) == 0:\n"
            "            bright = np.clip(frame.astype(np.float32) * 2.1 + 20.0, 0, 255).astype(np.uint8)\n"
            "            faces = self.app.get(bright)"
        ),
    )
    fd_txt = fd_txt.replace("if w < 50 or h < 80:", "if w < 28 or h < 40:")
    fd_py.write_text(fd_txt, encoding="utf-8")

ip_py = REPO_DIR / "latentsync" / "utils" / "image_processor.py"
ip_txt = ip_py.read_text(encoding="utf-8")
if "_last_det" not in ip_txt:
    ip_txt = ip_txt.replace(
        '        bbox, landmark_2d_106 = self.face_detector(image)\n        if bbox is None:\n            raise RuntimeError("Face not detected")',
        "        bbox, landmark_2d_106 = self.face_detector(image)\n        if bbox is None and getattr(self, '_last_det', None) is not None:\n            bbox, landmark_2d_106 = self._last_det\n        if bbox is None:\n            raise RuntimeError('Face not detected')\n        self._last_det = (bbox, landmark_2d_106)",
    )
    ip_py.write_text(ip_txt, encoding="utf-8")

lp_py = REPO_DIR / "latentsync" / "pipelines" / "lipsync_pipeline.py"
lp_txt = lp_py.read_text(encoding="utf-8")
if "_preseed_det" not in lp_txt:
    lp_txt = lp_txt.replace(
        "        for frame in tqdm.tqdm(video_frames):",
        "        # _preseed_det: ensure _last_det is populated per clip without leaking across clips\n        self.image_processor._last_det = None\n        for _pf in video_frames[::4]:\n            _pb, _pl = self.image_processor.face_detector(_pf)\n            if _pb is not None:\n                self.image_processor._last_det = (_pb, _pl)\n                break\n        for frame in tqdm.tqdm(video_frames):",
    )
    lp_py.write_text(lp_txt, encoding="utf-8")

from huggingface_hub import hf_hub_download

ckpt_dir = REPO_DIR / "checkpoints"
ckpt_dir.mkdir(parents=True, exist_ok=True)
print("[3/5] Downloading ByteDance/LatentSync-1.6 checkpoints...", flush=True)
for fn in ("whisper/tiny.pt", "latentsync_unet.pt"):
    target = ckpt_dir / fn
    if not target.exists():
        hf_hub_download(repo_id="ByteDance/LatentSync-1.6", filename=fn, local_dir=str(ckpt_dir))
        print(f"  downloaded {fn}", flush=True)

tar_in = Path(JOB.get("in", "/content/lipsync_in.tar.gz"))
if not tar_in.exists():
    raise FileNotFoundError(f"Missing {tar_in}")
with tarfile.open(tar_in, "r:gz") as tf:
    tf.extractall(IN_DIR)

os.chdir(REPO_DIR)
sys.path.insert(0, str(REPO_DIR))

import torch
from accelerate.utils import set_seed
from diffusers import AutoencoderKL, DDIMScheduler
from omegaconf import OmegaConf

from latentsync.models.unet import UNet3DConditionModel
from latentsync.pipelines.lipsync_pipeline import LipsyncPipeline
from latentsync.whisper.audio2feature import Audio2Feature

print(f"[4/5] Loading LatentSync-1.6 (512x512) pipeline on {torch.cuda.get_device_name(0)}...", flush=True)
config = OmegaConf.load(str(REPO_DIR / "configs" / "unet" / "stage2_512.yaml"))
dtype = torch.float16
scheduler = DDIMScheduler.from_pretrained(str(REPO_DIR / "configs"))
audio_encoder = Audio2Feature(
    model_path=str(ckpt_dir / "whisper" / "tiny.pt"),
    device="cuda",
    num_frames=config.data.num_frames,
    audio_feat_length=config.data.audio_feat_length,
)
vae = AutoencoderKL.from_pretrained("stabilityai/sd-vae-ft-mse", torch_dtype=dtype)
vae.config.scaling_factor = 0.18215
vae.config.shift_factor = 0

unet, _ = UNet3DConditionModel.from_pretrained(
    OmegaConf.to_container(config.model),
    str(ckpt_dir / "latentsync_unet.pt"),
    device="cpu",
)
unet = unet.to(dtype=dtype)

pipeline = LipsyncPipeline(
    vae=vae,
    audio_encoder=audio_encoder,
    unet=unet,
    scheduler=scheduler,
).to("cuda")

ROI_BY_SHOT = JOB.get("roi", {})
G_BY_SHOT = JOB.get("guidance", {})
DEFAULT_G = float(JOB.get("default_g", 1.55))
STEPS = int(JOB.get("steps", 20))

shot_ids = sorted(p.stem.removeprefix("vid_") for p in IN_DIR.glob("vid_*.mp4"))
print(f"[lipsync slate] {shot_ids}", flush=True)
for sid in shot_ids:
    vid_p = IN_DIR / f"vid_{sid}.mp4"
    wav_p = IN_DIR / f"stem_{sid}.wav"
    out_p = OUT_DIR / f"sync_{sid}.mp4"
    if not vid_p.exists() or not wav_p.exists():
        print(f"[skip missing] {sid}", flush=True)
        continue
    t0 = time.time()
    set_seed(1991 + zlib.crc32(sid.encode()) % 100)  # 稳定种子（hash() 每进程随机）
    roi_mode = ROI_BY_SHOT.get(sid, "")
    if roi_mode:
        os.environ["LS_ROI_MODE"] = roi_mode
    else:
        os.environ.pop("LS_ROI_MODE", None)
    g_scale = float(G_BY_SHOT.get(sid, DEFAULT_G))
    print(f"[lipsync run] {sid} (g={g_scale}, roi={roi_mode or 'full'})", flush=True)
    try:
        pipeline(
            video_path=str(vid_p),
            audio_path=str(wav_p),
            video_out_path=str(out_p),
            num_frames=config.data.num_frames,
            num_inference_steps=STEPS,
            guidance_scale=g_scale,
            weight_dtype=dtype,
            width=config.data.resolution,
            height=config.data.resolution,
            mask_image_path=str(REPO_DIR / config.data.mask_image_path),
            temp_dir=str(WORK / f"tmp_{sid}"),
        )
        print(f"[lipsync ok] sync_{sid}.mp4 ({out_p.stat().st_size // 1024} KB, {time.time() - t0:.1f}s)", flush=True)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[lipsync fallback] {sid} raised {e}; copying clean RIFE base clip", flush=True)
        shutil.copyfile(vid_p, out_p)
    finally:
        os.environ.pop("LS_ROI_MODE", None)

del pipeline, unet, vae, audio_encoder
torch.cuda.empty_cache()

tar_out = Path(JOB.get("out", "/content/lipsync_out.tar.gz"))
with tarfile.open(tar_out, "w:gz") as tf:
    for p in sorted(OUT_DIR.glob("sync_*.mp4")):
        tf.add(p, arcname=p.name)

print(f"[5/5] LATENTSYNC_DONE {tar_out} ({tar_out.stat().st_size // 1024} KB)", flush=True)
