#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage A remote worker: Synthesize Ep01 Part 2 (1-5 & 1-6) film dialogue on G4 GPU using OpenBMB/VoxCPM2.
Locks Kuglev (English panic) and Su Yuping to their exact v0.3 voice identities via reference WAVs,
and casts Lin Xuehong (lin, seed=1997) + Luo Huijuan (hui, seed=1996) with naturalistic 1991 cinema acting.
"""

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
            sys.executable, "-m", "pip", "install", "-q",
            "einops", "addict", "inflect", "argbind", "simplejson", "sortedcontainers",
            "soundfile", "librosa", "safetensors", "huggingface_hub[hf_transfer]", "torchcodec",
        ]
    )

import soundfile as sf
import torch
from voxcpm import VoxCPM

WORK = "/tmp/voxcpm2_p2"
REF_DIR = os.path.join(WORK, "refs")
OUT_DIR = os.path.join(WORK, "out")
os.makedirs(REF_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

tar_refs = "/content/voice_refs_p2.tar.gz"
if os.path.exists(tar_refs):
    with tarfile.open(tar_refs, "r:gz") as tf:
        tf.extractall(REF_DIR)
    print(f"[refs] Extracted {sorted(os.listdir(REF_DIR))}", flush=True)

if "model" not in globals() or model is None:
    print("[load] Loading openbmb/VoxCPM2 on CUDA...", flush=True)
    model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False, optimize=False, device="cuda")

sr = model.tts_model.sample_rate
print(f"[ready] VoxCPM2 sample_rate={sr}", flush=True)

ACTORS = {
    "lin": (
        "三十八岁中国女性，电影实力派女演员生活化原声，中低音沉稳干练，咬字清晰克制、很有主心骨，真实日常说话气息，绝不播音腔不舞台腔",
        "纽约这边的账本我昨晚全都理过了，明天饭店照常开门营业。",
        1997,
    ),
    "hui": (
        "三十五岁中国女性，普通家庭主妇生活化原声，嗓音温和自然略带口语随和感，情绪真实外露，绝不播音腔",
        "嫂子，早上这会儿菜都切好了，等会儿妈醒了就能吃早饭。",
        1996,
    ),
}

ref_paths = {
    "kug_en": os.path.join(REF_DIR, "ref_kug_en.wav"),
    "su": os.path.join(REF_DIR, "ref_su.wav"),
}

for key, (ctrl, txt, seed) in ACTORS.items():
    p = os.path.join(OUT_DIR, f"actor_{key}.wav")
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    wav = model.generate(
        text=f"({ctrl}){txt}",
        cfg_value=2.0,
        inference_timesteps=20,
        normalize=False,
        denoise=False,
    )
    sf.write(p, wav, sr)
    ref_paths[key] = p
    subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-i", p, "-ar", "48000", "-ac", "1", "-b:a", "256k", os.path.join(OUT_DIR, f"actor_{key}.mp3")])
    print(f"[actor] {key} -> {len(wav)/sr:.2f}s", flush=True)

# Scene 1-5 & 1-6 takes (multi-take on short/emotional bursts for strict selection)
LINES = [
    (
        "kug_15_panic_en_t1", "kug_en",
        "Hysterical terrified Russian man shouting into telephone in heavy Russian-accented English, crying panic, fast urgent panting",
        "Luo is ruined! Bankrupt! He shot himself last night in his Moscow office!",
        5101,
    ),
    (
        "kug_15_panic_en_t2", "kug_en",
        "Frantic desperate Russian man on phone in Russian-accented English, trembling terrified sobs, high urgency",
        "Luo is ruined! Bankrupt! He shot himself last night in his Moscow office!",
        5102,
    ),
    (
        "kug_15_leak_en", "kug_en",
        "Panicked Russian man shouting loud and fast on phone in Russian-accented English, desperate shrill urgency",
        "He shot himself last night! He's gone—dead in Moscow!",
        5103,
    ),
    (
        "hui_15_scream_t1", "hui",
        "三十五岁中国女人刚听见亲哥哥自杀噩耗，脸色惨白失声惊叫，嗓音发抖破音",
        "哥——！",
        5201,
    ),
    (
        "hui_15_scream_t2", "hui",
        "女人骤然惊骇尖叫喊出声，呼吸抽紧带着哭腔颤抖",
        "哥——！",
        5202,
    ),
    (
        "hui_15_scream_t3", "hui",
        "极度震惊惶恐之下突然尖叫，短促刺耳撕裂感",
        "哥——！",
        5203,
    ),
    (
        "lin_16_ask_t1", "lin",
        "三十八岁女人冲出厨房抢过电话急声追问，语速急促紧绷压低质问",
        "喂？！到底怎么回事？！",
        5301,
    ),
    (
        "lin_16_ask_t2", "lin",
        "女人声音发紧，呼吸微喘着抢接电话急问，生活化真实焦急",
        "喂？怎么回事？！你慢点说！",
        5302,
    ),
    (
        "su_17_gasp_t1", "su",
        "七十岁老母亲听见儿子开枪自杀的瞬间如遭雷击，呼吸骤停抽噎倒气，微弱绝望吐出两个字",
        "家明……",
        5401,
    ),
    (
        "su_17_gasp_t2", "su",
        "七十岁老人突发心脏病剧痛，气息窒息哽咽，极短促惊喘一句",
        "不……家明……",
        5402,
    ),
    (
        "lin_18b_cry_t1", "lin",
        "女人扑跪在地板上抱住晕倒的婆婆撕心裂肺哭喊，声音嘶哑颤抖万分焦急",
        "妈——！慧娟！拿急救药！快叫救护车！！",
        5501,
    ),
    (
        "lin_18b_cry_t2", "lin",
        "女人极度慌张急切、带着哭腔喊出声，呼吸沉重仓促，真实救命呼喊",
        "妈——！慧娟！拿急救药！快叫救护车！！",
        5502,
    ),
    (
        "hui_21a_weep_t1", "hui",
        "女人瘫坐在医院走廊墙根崩溃痛哭，抽泣断续，绝望崩溃喊出声",
        "一天工夫，哥没了，妈也没了！",
        5601,
    ),
    (
        "hui_21a_weep_t2", "hui",
        "小姑子边哭边捶打膝盖抽噎着哭诉，声音嘶哑无助，真实崩溃大哭",
        "一天工夫，哥没了，妈也没了！",
        5602,
    ),
    (
        "hui_21b_weep_t1", "hui",
        "女人哭得上气不接下气，绝望无助地哭喊追问，嗓音哭哑",
        "还欠着一百多万美金的债，咱们孤儿寡母怎么活啊？！",
        5611,
    ),
    (
        "hui_21b_weep_t2", "hui",
        "三十五岁女人崩溃大哭着哀叹绝望，带着鼻音与哭泣抽噎",
        "还欠着一百多万美金的债，咱们孤儿寡母怎么活啊？！",
        5612,
    ),
    (
        "lin_23_iron_t1", "lin",
        "刚经历巨变与哭喊后的女人嗓音沙哑低沉，硬生生逼回眼泪，一字一顿斩钉截铁，冷冽而有力量",
        "别哭了！哭保不住曼哈顿的裕香阁饭店，更还不清债！",
        5701,
    ),
    (
        "lin_23_iron_t2", "lin",
        "三十八岁女人压着浑身颤抖与喉头嘶哑，声音低冷硬朗如铁，厉声止住小姑子",
        "别哭了！哭保不住曼哈顿的裕香阁饭店，更还不清债！",
        5702,
    ),
    (
        "lin_24a_plan_t1", "lin",
        "女人目光坚定，嗓音沙哑却冷静到极点，语速紧凑干脆地下达命令",
        "听着，从现在起对外一律封锁死讯，妈的葬礼定在二十八号！",
        5801,
    ),
    (
        "lin_24a_plan_t2", "lin",
        "沉着刚硬的女性沙哑嗓音，不容置疑的决断口吻，清晰果断",
        "听着，从现在起对外一律封锁死讯，妈的葬礼定在二十八号！",
        5802,
    ),
    (
        "lin_24b_plan_t1", "lin",
        "女人抓紧对方肩膀压低声音急切交代关键细节，嗓音沙哑，条理极其清晰",
        "你马上给莫斯科的库格列夫回电话，求他务必在那边办完火化，二十七号把你哥的骨灰、遗书，",
        5811,
    ),
    (
        "lin_24b_plan_t2", "lin",
        "极度克制镇定、微哑有力的中年女声，急而不乱地交代安排",
        "你马上给莫斯科的库格列夫回电话，求他务必在那边办完火化，二十七号把你哥的骨灰、遗书，",
        5812,
    ),
    (
        "lin_24c_plan_t1", "lin",
        "女人一字一句咬紧重音、带着孤注一掷的狠劲儿和担当，末尾句沉稳落定",
        "还有墙上挂着的那幅见路不走横幅一块儿带回纽约！剩下的事交给我！",
        5821,
    ),
    (
        "lin_24c_plan_t2", "lin",
        "嗓音微哑、目光死盯着对方交代完最后一件信物，末句「剩下的事交给我！」铿锵坚定",
        "还有墙上挂着的那幅见路不走横幅一块儿带回纽约！剩下的事交给我！",
        5822,
    ),
]

for fname, actor_key, ctrl, txt, seed in LINES:
    out_wav = os.path.join(OUT_DIR, f"{fname}.wav")
    out_mp3 = os.path.join(OUT_DIR, f"{fname}.mp3")
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    wav = model.generate(
        text=f"({ctrl}){txt}",
        reference_wav_path=ref_paths[actor_key],
        cfg_value=2.05,
        inference_timesteps=22,
        normalize=False,
        denoise=False,
    )
    sf.write(out_wav, wav, sr)
    subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-i", out_wav, "-ar", "48000", "-ac", "1", "-b:a", "256k", out_mp3])
    print(f"[synth] {fname}.mp3 ({len(wav)/sr:.2f}s)", flush=True)

tar_out = "/content/vox_ep01_p2_out.tar.gz"
with tarfile.open(tar_out, "w:gz") as tf:
    for fn in sorted(os.listdir(OUT_DIR)):
        if fn.endswith(".mp3"):
            tf.add(os.path.join(OUT_DIR, fn), arcname=fn)

print(f"VOX_P2_DONE {tar_out} ({os.path.getsize(tar_out) // 1024} KB)", flush=True)
