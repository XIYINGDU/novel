#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Synthesize Scene 1-2 English Moscow crisis phone call via OpenBMB/VoxCPM2 on Colab GPU."""

import os
import subprocess
import sys
import tarfile

os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

try:
    import voxcpm  # noqa: F401
except ImportError:
    print("[setup] Installing OpenBMB voxcpm & audio dependencies...", flush=True)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "voxcpm"])
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-q",
            "einops",
            "addict",
            "inflect",
            "argbind",
            "simplejson",
            "sortedcontainers",
            "soundfile",
            "librosa",
            "safetensors",
            "huggingface_hub[hf_transfer]",
            "torchcodec",
        ]
    )

import soundfile as sf
import torch
from voxcpm import VoxCPM

OUT_DIR = "/tmp/voxcpm2_v03_en"
os.makedirs(OUT_DIR, exist_ok=True)

if "model" not in globals() or model is None:
    print("[load] Loading openbmb/VoxCPM2 on CUDA...", flush=True)
    model = VoxCPM.from_pretrained(
        "openbmb/VoxCPM2",
        load_denoiser=False,
        optimize=False,
        device="cuda",
    )
sr = model.tts_model.sample_rate
print(f"[ready] VoxCPM2 sample_rate={sr}", flush=True)

# Keep exact same Luo Jiaming vocal identity (seed=1991) + design authentic Russian-accented English partner Kuglev
ACTORS = {
    "luo": (
        "四十二岁中国北方中年男性，电影实力派男演员生活化原声，嗓音低沉醇厚略带熬夜烟嗓沙哑，呼吸真实自然，克制内敛，绝不播音腔",
        "莫斯科的夜太冷了，这间办公室里的台灯已经亮了一整宿。",
        1991,
    ),
    "kug_en": (
        "Forty-eight-year-old rough Russian male oil executive in Moscow speaking English with a thick authentic Russian accent, deep gravelly voice, tense heavy breathing, realistic natural speech",
        "Mister Luo, all the ministry approvals and oil well contracts are collapsing tonight in Moscow.",
        1995,
    ),
}

ref_paths = {}
for key, (ctrl, sample_txt, seed) in ACTORS.items():
    p = os.path.join(OUT_DIR, f"actor_{key}.wav")
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    wav = model.generate(
        text=f"({ctrl}){sample_txt}",
        cfg_value=2.0,
        inference_timesteps=18,
        normalize=False,
        denoise=False,
    )
    sf.write(p, wav, sr)
    ref_paths[key] = p
    print(f"[actor] {key} -> {len(wav)/sr:.2f}s", flush=True)

LINES = [
    (
        "line_05a_en.wav",
        "luo",
        "Exhausted 42-year-old Chinese man answering a midnight phone call in English, low hoarse quiet voice, calm and brief",
        "This is Luo.",
        3001,
    ),
    (
        "line_05b1_en.wav",
        "kug_en",
        "Terrified Russian man shouting urgently in Russian-accented English over the phone, breathless fast pace, sheer panic",
        "Luo! Three of the five senior officials in our secret shareholder deal have already been arrested! The other two ministers' sons fled to Switzerland this evening!",
        3002,
    ),
    (
        "line_05b2_en.wav",
        "kug_en",
        "Desperate panicked Russian man pleading rapidly in Russian-accented English on the verge of breakdown, breathless urgency",
        "The American oil company just pulled out of buying those hundred and fifty wells, and the prosecutor's office is coming to seal the doors tomorrow morning! Luo, what about my sixty thousand dollars in secret shares?!",
        3003,
    ),
    (
        "line_05c_en.wav",
        "luo",
        "Deadly calm exhausted man speaking quiet hoarse English, hollow numb tone without emotion, unhurried pace",
        "Got it, Kuglev. Let's talk tomorrow.",
        3004,
    ),
]

for fname, actor_key, ctrl, txt, seed in LINES:
    out_wav = os.path.join(OUT_DIR, fname)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    wav = model.generate(
        text=f"({ctrl}){txt}",
        reference_wav_path=ref_paths[actor_key],
        cfg_value=2.0,
        inference_timesteps=20,
        normalize=False,
        denoise=False,
    )
    sf.write(out_wav, wav, sr)
    mp3_name = fname.replace(".wav", ".mp3")
    subprocess.check_call(
        [
            "ffmpeg", "-y", "-v", "error", "-i", out_wav,
            "-ar", "48000", "-ac", "1", "-b:a", "256k",
            os.path.join(OUT_DIR, mp3_name),
        ]
    )
    print(f"[synth] {mp3_name} ({len(wav)/sr:.2f}s)", flush=True)

# Clean up VRAM immediately so ComfyUI / Qwen-Image-2.1 has full 96GB!
del model
torch.cuda.empty_cache()

tar_path = "/tmp/voxcpm2_v03_en.tar.gz"
with tarfile.open(tar_path, "w:gz") as tf:
    for fn in sorted(os.listdir(OUT_DIR)):
        if fn.endswith(".mp3"):
            tf.add(os.path.join(OUT_DIR, fn), arcname=fn)

print(f"VOXCPM2_V03_DONE {tar_path} ({os.path.getsize(tar_path) // 1024} KB)", flush=True)
