#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run OpenBMB/VoxCPM2 on Colab GPU to synthesize lifelike 48kHz film dialogue & inner monologue."""

import os
import subprocess
import sys
import tarfile

os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Install voxcpm cleanly without clobbering Colab's CUDA PyTorch
try:
    import voxcpm  # noqa: F401
except ImportError:
    print("[setup] Installing OpenBMB voxcpm & audio dependencies...", flush=True)
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-q",
            "--no-deps",
            "voxcpm",
        ]
    )
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

OUT_DIR = "/tmp/voxcpm2_pilot_audio"
os.makedirs(OUT_DIR, exist_ok=True)

if "model" not in globals() or model is None:
    print("[load] Downloading & loading openbmb/VoxCPM2 on CUDA...", flush=True)
    model = VoxCPM.from_pretrained(
        "openbmb/VoxCPM2",
        load_denoiser=False,
        optimize=False,
        device="cuda",
    )
sr = model.tts_model.sample_rate
print(f"[ready] VoxCPM2 ready! sample_rate={sr}", flush=True)

# Step 1: Voice Design — cast 4 lifelike film actors (zero broadcast/robotic cadence)
ACTORS = {
    "luo": (
        "四十二岁中国北方中年男性，电影实力派男演员生活化原声，嗓音低沉醇厚略带熬夜烟嗓沙哑，呼吸真实自然，克制内敛，绝不播音腔",
        "莫斯科的夜太冷了，这间办公室里的台灯已经亮了一整宿。",
        1991,
    ),
    "ye": (
        "四十多岁北京中年男人，嗓音低沉磁性、松弛通透，真实生活口语质感，从容淡定，绝不播音腔",
        "这世上的事儿，本来就没有什么现成的路可走。",
        1992,
    ),
    "kug": (
        "四十多岁粗犷中年男人，嗓音浑厚粗粝，气息偏重，情绪紧绷真实，生活化口语",
        "罗先生，公司的账目和油井批文现在全都压在上面了。",
        1993,
    ),
    "su": (
        "七十岁中国慈祥老母亲，退休大学女教授，声音温和苍老、亲切自然，生活化慢语速，绝不朗诵腔",
        "家明啊，在外头忙归忙，一定得按时吃饭，照顾好自己。",
        1994,
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

# Step 2: Controllable Voice Cloning — lock actor timbre + scene-specific film acting!
TV_TEXT_RU = (
    "Я слагаю с себя полномочия Генерального секретаря Центрального Комитета КПСС. "
    "Центральный Комитет КПСС должен принять трудное, но честное решение о самороспуске. "
    "Судьбу республиканских компартий и местных партийных организаций определят они сами."
)

LINES = [
    (
        "tv_gorbachev_19910824.wav",
        None,
        "Sixty-year-old Russian male statesman speaking on 1991 television broadcast, solemn grave authoritative tone, measured pace",
        TV_TEXT_RU,
        2001,
    ),
    (
        "line_02_3.wav",
        "ye",
        "身受重伤胸口中弹，呼吸沉重喘息，带着一丝苦涩荒诞的自嘲轻笑，低声虚弱口语",
        "呵……还真他妈抬举我。",
        2002,
    ),
    (
        "line_05a_1.wav",
        "luo",
        "深夜接起电话，极度疲惫沙哑，低沉简短平静的生活口语",
        "我是罗。",
        2003,
    ),
    (
        "line_05a_2.wav",
        "kug",
        "惊恐万分，呼吸急促，语速飞快焦急喊话，情绪失控",
        "罗！秘密股东协议里的五个高官已经抓了三个！另外两个高官公子傍晚跑去瑞士了！",
        2004,
    ),
    (
        "line_05b_0.wav",
        "kug",
        "绝望恐慌，语速极快，焦急逼问近乎崩溃",
        "美国石油公司刚撤回了那一百五十口油井的收购意向，明天一早检察院就来贴封条！罗，我那六万美金口头暗股怎么办？！",
        2005,
    ),
    (
        "line_05b_2.wav",
        "luo",
        "心如死灰，平静得可怕，声音低沉沙哑，语速平缓克制毫无波澜",
        "知道了，库格列夫。明天再说吧。",
        2006,
    ),
    (
        "line_06_1.wav",
        "luo",
        "冷冷低语，带着一丝轻蔑与彻底的厌倦，声音低沉简短自然",
        "这个笨蛋。",
        2007,
    ),
    (
        "line_08_3.wav",
        "su",
        "慈祥温和的老母亲接起电话，带着温暖笑意与关切，自然亲切口语",
        "喂？是家明吗？",
        2008,
    ),
    (
        "line_09_1.wav",
        "su",
        "温和关切的老母亲对着电话轻声询问，略带一丝疑惑与担心，语速舒缓自然",
        "家明？是你吗？怎么不说话呀？",
        2009,
    ),
    (
        "line_10_4.wav",
        "luo",
        "深夜死寂中写遗书时的内心独白，声音极轻近乎耳语，带着真实的疲惫呼吸感，语速缓慢悲凉克制，像真人低声叹息绝不朗诵腔",
        "我撑不住了……我不能请求原谅，这不是可以原谅的事。",
        2010,
    ),
    (
        "line_11_1.wav",
        "luo",
        "深夜空旷房间里近乎气声耳语的喃喃自语，嗓音沙哑空洞微弱，语速极慢，字句间有真实的停顿与苦涩绝望，绝不播音腔",
        "见路不走……可我现在能见到的，只有一条死路……不走，也得走了……",
        2011,
    ),
]

for fname, actor_key, ctrl, txt, seed in LINES:
    out_wav = os.path.join(OUT_DIR, fname)
    ref_wav = ref_paths[actor_key] if actor_key else None
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    wav = model.generate(
        text=f"({ctrl}){txt}",
        reference_wav_path=ref_wav,
        cfg_value=2.0,
        inference_timesteps=20,
        normalize=False,
        denoise=False,
    )
    sf.write(out_wav, wav, sr)
    # Convert to high-bitrate 320kbps 48kHz MP3 too so bundle size is tiny (~1.5MB) and crisp
    mp3_name = fname.replace(".wav", ".mp3")
    subprocess.check_call(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            out_wav,
            "-ar",
            "48000",
            "-ac",
            "1",
            "-b:a",
            "256k",
            os.path.join(OUT_DIR, mp3_name),
        ]
    )
    print(f"[synth] {mp3_name} ({len(wav)/sr:.2f}s)", flush=True)

tar_path = "/tmp/voxcpm2_audio.tar.gz"
with tarfile.open(tar_path, "w:gz") as tf:
    for fn in sorted(os.listdir(OUT_DIR)):
        if fn.endswith(".mp3"):
            tf.add(os.path.join(OUT_DIR, fn), arcname=fn)

print(f"VOXCPM2_ALL_DONE {tar_path} ({os.path.getsize(tar_path) // 1024} KB)", flush=True)
