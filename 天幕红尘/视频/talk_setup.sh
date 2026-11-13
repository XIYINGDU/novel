#!/bin/bash
# Colab 环境搭建 v2：IndexTTS2（py3.11，uv）+ InfiniteTalk（py3.10，torch 2.4.1）
# VM 自带 Python 3.13，两个项目都不兼容，所以各自用 uv 建独立 venv
# 用法：nohup bash /content/talk_setup.sh > /content/setup.log 2>&1 &
set -x
cd /content
export HF_HUB_ENABLE_HF_TRANSFER=1
pip install -q -U uv "huggingface_hub[cli,hf_transfer]" edge-tts
apt-get -qq install -y ffmpeg git-lfs > /dev/null
HF=$(command -v hf)

# ---------- 权重下载（后台并行，先开始） ----------
mkdir -p /content/InfiniteTalk_weights
( $HF download Wan-AI/Wan2.1-I2V-14B-480P --local-dir /content/InfiniteTalk_weights/Wan2.1-I2V-14B-480P && echo "DL_WAN_DONE" ) > /content/dl_wan.log 2>&1 &
( $HF download TencentGameMate/chinese-wav2vec2-base --local-dir /content/InfiniteTalk_weights/chinese-wav2vec2-base && \
  $HF download TencentGameMate/chinese-wav2vec2-base model.safetensors --revision refs/pr/1 --local-dir /content/InfiniteTalk_weights/chinese-wav2vec2-base && \
  $HF download MeiGen-AI/InfiniteTalk --local-dir /content/InfiniteTalk_weights/InfiniteTalk && echo "DL_IT_DONE" ) > /content/dl_it.log 2>&1 &

# ---------- IndexTTS2 ----------
cd /content
[ -d index-tts ] || git clone --depth 1 https://github.com/index-tts/index-tts.git
cd /content/index-tts
GIT_LFS_SKIP_SMUDGE=1 uv sync --python 3.11 || uv venv -p 3.11 .venv
.venv/bin/python -c "import indextts" || uv pip install --python .venv/bin/python -e .
uv pip install --python .venv/bin/python edge-tts
$HF download IndexTeam/IndexTTS-2 --local-dir checkpoints
echo "INDEXTTS_DONE"

# ---------- InfiniteTalk ----------
cd /content
[ -d InfiniteTalk ] || git clone --depth 1 https://github.com/MeiGen-AI/InfiniteTalk.git
cd /content/InfiniteTalk
uv venv -p 3.10 .venv
PY=/content/InfiniteTalk/.venv/bin/python
uv pip install --python $PY torch==2.4.1 torchvision==0.19.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cu121
uv pip install --python $PY xformers==0.0.28 --index-url https://download.pytorch.org/whl/cu121
uv pip install --python $PY "https://github.com/Dao-AILab/flash-attention/releases/download/v2.7.4.post1/flash_attn-2.7.4.post1+cu12torch2.4cxx11abiFALSE-cp310-cp310-linux_x86_64.whl" || echo "FLASH_ATTN_FAILED"
uv pip install --python $PY -r requirements.txt
uv pip install --python $PY misaki[en] ninja psutil packaging wheel librosa
ln -sfn /content/InfiniteTalk_weights weights
$PY -c "import torch, xformers; print('torch', torch.__version__, torch.cuda.is_available())"
$PY -c "import flash_attn; print('flash_attn ok')" || echo "FLASH_ATTN_MISSING"
echo "INFINITETALK_ENV_DONE"

wait
grep -h "DONE" /content/dl_wan.log /content/dl_it.log
echo "ALL_SETUP_DONE"
