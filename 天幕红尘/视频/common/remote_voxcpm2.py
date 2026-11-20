#!/usr/bin/env python3
"""云端通用 VoxCPM2 配音 worker（A-ACTOR-BASE-VOICE）。读 /content/vox_job.json：
{"actors": {key: [音色描述, 定妆句, seed]}, "refs": {key: "/content/xxx.wav"}, "lines": [[文件名, actor, 情绪描述, 台词, seed], ...],
 "out": "/content/vox_out.tar.gz"}
先按固定 seed 铸 actor_<key>.wav（refs 里已有的角色跳过），再以它为参考克隆每句；情绪只用描述控制。
"""
import json
import os
import subprocess
import sys
import tarfile

try:
    import voxcpm  # noqa: F401
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "voxcpm"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "einops", "addict", "inflect", "argbind", "simplejson",
                           "sortedcontainers", "soundfile", "librosa", "safetensors", "huggingface_hub[hf_transfer]", "torchcodec"])
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

import soundfile as sf  # noqa: E402
import torch  # noqa: E402
from voxcpm import VoxCPM  # noqa: E402

job = json.load(open("/content/vox_job.json"))
OUT = "/tmp/vox_out"
os.makedirs(OUT, exist_ok=True)
model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False, optimize=False, device="cuda")
sr = model.tts_model.sample_rate
print(f"[ready] VoxCPM2 sr={sr}", flush=True)


def mp3(wav_path):
    out = wav_path[:-4] + ".mp3"
    subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-i", wav_path, "-ar", "48000", "-ac", "1", "-b:a", "256k", out])
    return out


refs = dict(job.get("refs", {}))
outputs = []
for key, (ctrl, txt, seed) in job["actors"].items():
    if key in refs:
        continue
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    wav = model.generate(text=f"({ctrl}){txt}", cfg_value=2.0, inference_timesteps=20, normalize=False, denoise=False)
    p = os.path.join(OUT, f"actor_{key}.wav")
    sf.write(p, wav, sr)
    outputs.extend((p, mp3(p)))
    refs[key] = p
    print(f"[actor] {key} seed={seed} {len(wav) / sr:.2f}s", flush=True)

for fname, actor, ctrl, txt, seed in job["lines"]:
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    wav = model.generate(text=f"({ctrl}){txt}", reference_wav_path=refs[actor], cfg_value=2.05, inference_timesteps=22,
                         normalize=False, denoise=False)
    p = os.path.join(OUT, f"{fname}.wav")
    sf.write(p, wav, sr)
    outputs.extend((p, mp3(p)))
    print(f"[line] {fname} {len(wav) / sr:.2f}s", flush=True)

with tarfile.open(job["out"], "w:gz") as tf:
    for path in outputs:
        tf.add(path, arcname=os.path.basename(path))  # wav（给 LatentSync）+ mp3（试听）
print("VOX_DONE", flush=True)
