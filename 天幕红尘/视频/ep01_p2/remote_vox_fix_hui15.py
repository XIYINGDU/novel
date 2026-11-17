#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quick targeted VoxCPM2 re-roll ONLY for hui_15_scream ('哥——！') without trailing hyperventilation artifact."""

import os
import subprocess
import sys
import tarfile

try:
    import voxcpm  # noqa: F401
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "voxcpm"])
    subprocess.check_call(
        [
            sys.executable, "-m", "pip", "install", "-q",
            "einops", "addict", "inflect", "argbind", "simplejson", "sortedcontainers",
            "soundfile", "librosa", "safetensors", "huggingface_hub", "torchcodec",
        ]
    )

import soundfile as sf
import torch
from voxcpm import VoxCPM

OUT_DIR = "/tmp/vox_fix_hui15"
os.makedirs(OUT_DIR, exist_ok=True)
REF_DIR = "/tmp/vox_fix_refs"
os.makedirs(REF_DIR, exist_ok=True)
with tarfile.open("/content/hui15_ref.tar.gz", "r:gz") as tf:
    tf.extractall(REF_DIR)

if "model" not in globals() or model is None:
    model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False, optimize=False, device="cuda")
sr = model.tts_model.sample_rate
ref_wav = os.path.join(REF_DIR, "ref_hui.wav")

TAKES = [
    ("hui_15_v2_a", "三十五岁中国女人刚听见亲哥自杀噩耗，脸色惨白失声喊出，短促真实", "哥！怎么可能！", 7101),
    ("hui_15_v2_b", "女人骤然惊吓失声痛呼一声，声音震颤", "哥！", 7102),
    ("hui_15_v2_c", "女人惊骇欲绝喊出一声，短促哑声绝望", "哥！不……", 7103),
    ("hui_15_v2_d", "女人失声惊喊，嗓音颤抖真实", "哥！你说什么？！", 7104),
    ("su_17_v2_a", "七十岁老母亲突然心口剧痛，极微弱抽气低唤一声", "家明……", 7201),
    ("su_17_v2_b", "七十岁老母亲听见噩耗心脏骤停般窒息倒气", "呃……不……", 7202),
]

for fn, ctrl, txt, seed in TAKES:
    wav_p = os.path.join(OUT_DIR, f"{fn}.wav")
    mp3_p = os.path.join(OUT_DIR, f"{fn}.mp3")
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    wav = model.generate(text=f"({ctrl}){txt}", reference_wav_path=ref_wav if fn.startswith("hui") else None, cfg_value=2.0, inference_timesteps=20, normalize=False, denoise=False)
    sf.write(wav_p, wav, sr)
    subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-i", wav_p, "-ar", "48000", "-ac", "1", "-b:a", "256k", mp3_p])
    print(f"[fix] {fn}.mp3 ({len(wav)/sr:.2f}s)", flush=True)

tar_out = "/content/vox_fix_hui15.tar.gz"
with tarfile.open(tar_out, "w:gz") as tf:
    for p in sorted(os.listdir(OUT_DIR)):
        if p.endswith(".mp3"):
            tf.add(os.path.join(OUT_DIR, p), arcname=p)
print("VOX_HUI15_DONE", tar_out, flush=True)
