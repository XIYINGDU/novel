#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run ByteDance LatentSync-1.6 (512x512 high-res V2V lip-sync) on all v0.4 character shots in ONE GPU pass."""

import os
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

WORK = Path("/tmp/v04_lipsync")
IN_DIR = WORK / "in"
OUT_DIR = WORK / "out"
REPO_DIR = Path("/content/LatentSync")

for d in (WORK, IN_DIR, OUT_DIR):
    d.mkdir(parents=True, exist_ok=True)

# 1. Install lightweight Python dependencies WITHOUT touching Colab's prebuilt CUDA/Blackwell torch!
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

# 2. Clone LatentSync source if not present
if not (REPO_DIR / "scripts" / "inference.py").exists():
    print("[2/5] Cloning bytedance/LatentSync...", flush=True)
    if REPO_DIR.exists():
        shutil.rmtree(REPO_DIR)
    env_git = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1")
    subprocess.check_call(
        ["git", "clone", "--depth", "1", "https://github.com/bytedance/LatentSync.git", str(REPO_DIR)],
        env=env_git,
    )

# 3. Apply surgical compatibility & cinema low-key robustness patches
# Patch A: AdaLayerNorm & FeedForward import compatibility across diffusers 0.32..0.36+
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

# Patch B: Remove decord dependency in util.py -> use cv2 & librosa directly, and keep exact 25fps frames!
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

# Patch C: Allow CPU+CUDA fallback in InsightFace, cache FaceAnalysis across shots,
# lower dark-scene threshold to 0.25, and auto-retry gamma-brightened copy on ultra-dark noir frames!
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
        "        faces = self.app.get(frame)\n        if len(faces) == 0:\n            bright = np.clip(frame.astype(np.float32) * 2.1 + 20.0, 0, 255).astype(np.uint8)\n            faces = self.app.get(bright)",
    )
    fd_txt = fd_txt.replace("if w < 50 or h < 80:", "if w < 32 or h < 45:")
    fd_py.write_text(fd_txt, encoding="utf-8")

# Patch D: Pre-seed & temporal carry-over in image_processor.py + lipsync_pipeline.py so dark frames never abort
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
        "        # _preseed_det: ensure _last_det is populated even if frame 0 is ultra-dark\n        for _pf in video_frames[::4]:\n            _pb, _pl = self.image_processor.face_detector(_pf)\n            if _pb is not None:\n                self.image_processor._last_det = (_pb, _pl)\n                break\n        for frame in tqdm.tqdm(video_frames):",
    )
    lp_py.write_text(lp_txt, encoding="utf-8")

# 4. Download ByteDance/LatentSync-1.6 weights into /content/LatentSync/checkpoints
from huggingface_hub import hf_hub_download

ckpt_dir = REPO_DIR / "checkpoints"
ckpt_dir.mkdir(parents=True, exist_ok=True)
print("[3/5] Downloading ByteDance/LatentSync-1.6 checkpoints...", flush=True)
for fn in ("whisper/tiny.pt", "latentsync_unet.pt"):
    target = ckpt_dir / fn
    if not target.exists():
        hf_hub_download(repo_id="ByteDance/LatentSync-1.6", filename=fn, local_dir=str(ckpt_dir))
        print(f"  downloaded {fn}", flush=True)

# Unpack uploaded input clips + stems
tar_in = Path("/content/lipsync_in.tar.gz")
if not tar_in.exists():
    tar_in = Path("/tmp/lipsync_in.tar.gz")
if not tar_in.exists():
    raise FileNotFoundError("Missing /content/lipsync_in.tar.gz")
with tarfile.open(tar_in, "r:gz") as tf:
    tf.extractall(IN_DIR)

# 5. Load LipsyncPipeline ONCE and process all 7 clips at full 20-step DDIM precision!
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

SHOT_IDS = ["05a", "05c", "06a", "08b", "09a", "11a", "11b"]
for sid in SHOT_IDS:
    vid_p = IN_DIR / f"vid_{sid}.mp4"
    wav_p = IN_DIR / f"stem_{sid}.wav"
    out_p = OUT_DIR / f"sync_{sid}.mp4"
    if not vid_p.exists() or not wav_p.exists():
        print(f"[skip missing] {sid}", flush=True)
        continue
    t0 = time.time()
    set_seed(1991)
    # Gentler guidance on silent grief shot 09a and subtle whispers 11a/11b; crisp articulation on 05a/05c/06a/08b
    g_scale = 1.25 if sid in ("09a", "11a", "11b") else 1.5
    try:
        pipeline(
            video_path=str(vid_p),
            audio_path=str(wav_p),
            video_out_path=str(out_p),
            num_frames=config.data.num_frames,
            num_inference_steps=20,
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

del pipeline, unet, vae, audio_encoder
torch.cuda.empty_cache()

tar_out = Path("/content/lipsync_out.tar.gz")
with tarfile.open(tar_out, "w:gz") as tf:
    for p in sorted(OUT_DIR.glob("sync_*.mp4")):
        tf.add(p, arcname=p.name)

print(f"[5/5] LATENTSYNC_V04_DONE {tar_out} ({tar_out.stat().st_size // 1024} KB)", flush=True)
