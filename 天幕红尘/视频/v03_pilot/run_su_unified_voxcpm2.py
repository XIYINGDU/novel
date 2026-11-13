#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Synthesize Su Yuping's two lines in ONE continuous VoxCPM2 pass so vocal timbre is 100% identical."""

import os
import subprocess
import sys

os.environ["HF_XET_HIGH_PERFORMANCE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

try:
    import voxcpm  # noqa: F401
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "voxcpm"])
    subprocess.check_call(
        [
            sys.executable, "-m", "pip", "install", "-q",
            "einops", "addict", "inflect", "argbind", "simplejson",
            "sortedcontainers", "soundfile", "librosa", "safetensors",
            "huggingface_hub", "torchcodec",
        ]
    )

import soundfile as sf
import torch
from voxcpm import VoxCPM

OUT_DIR = "/tmp/su_unified"
os.makedirs(OUT_DIR, exist_ok=True)

model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False, optimize=False, device="cuda")
sr = model.tts_model.sample_rate

# Create 70yo gentle mother reference
torch.manual_seed(1994)
torch.cuda.manual_seed_all(1994)
ref_wav = model.generate(
    text="(七十岁中国慈祥老母亲，退休大学女教授，声音温和苍老、亲切自然，生活化慢语速，绝不朗诵腔)家明啊，在外头忙归忙，一定得按时吃饭，照顾好自己。",
    cfg_value=2.0,
    inference_timesteps=18,
    normalize=False,
    denoise=False,
)
ref_path = os.path.join(OUT_DIR, "ref_su.wav")
sf.write(ref_path, ref_wav, sr)

# Generate ONE continuous take containing BOTH lines separated by a natural pause!
PROMPT_CTRL = "七十岁中国慈祥老母亲接起电话，声音温和苍老亲切自然，语速舒缓，先温和接听再关切轻问，绝不播音腔"
FULL_TEXT = "喂？是家明吗？……家明？是你吗？怎么不说话呀？"

for idx, seed in enumerate((2026, 2028), 1):
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    wav = model.generate(
        text=f"({PROMPT_CTRL}){FULL_TEXT}",
        reference_wav_path=ref_path,
        cfg_value=2.0,
        inference_timesteps=20,
        normalize=False,
        denoise=False,
    )
    wpath = os.path.join(OUT_DIR, f"su_continuous_{idx}.wav")
    mpath = os.path.join(OUT_DIR, f"su_continuous_{idx}.mp3")
    sf.write(wpath, wav, sr)
    subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-i", wpath, "-ar", "48000", "-ac", "1", "-b:a", "256k", mpath])
    print(f"[done] su_continuous_{idx}.mp3 ({len(wav)/sr:.2f}s)", flush=True)
