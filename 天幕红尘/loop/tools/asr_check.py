#!/usr/bin/env python3
"""配音逐字核对（A-ASR-VERIFY，候选）：ASR 转写与台词比对，抓漏字、读错数字、连读歧义。
用法（在 天幕红尘/ 下）：
  HF_HUB_DISABLE_XET=1 uv run -q --with faster-whisper --with "httpx[socks]" --with socksio \
     python loop/tools/asr_check.py <vox_job.json> <音频目录> [--model medium] [--only a,b]
同音字（梁/良、片/骗）是 ASR 自身误差；看的是：数字、专名、整词缺失、连读后意思变了。
"""
import argparse, difflib, json, re
from pathlib import Path
from faster_whisper import WhisperModel

ap = argparse.ArgumentParser()
ap.add_argument("job"); ap.add_argument("audio"); ap.add_argument("--model", default="medium"); ap.add_argument("--only")
a = ap.parse_args()
lines = json.loads(Path(a.job).read_text())["lines"]
only = set(a.only.split(",")) if a.only else None
m = WhisperModel(a.model, device="cpu", compute_type="int8")
norm = lambda s: re.sub(r"[^一-鿿0-9]", "", s)
for f, _, _, txt, _ in lines:
    if only and f not in only:
        continue
    segs, _ = m.transcribe(str(Path(a.audio) / f"{f}.wav"), language="zh", initial_prompt="以下是普通话的句子。", beam_size=5)
    hyp = "".join(s.text for s in segs)
    r = difflib.SequenceMatcher(None, norm(txt), norm(hyp)).ratio()
    print(f"{f:18} {r:.2f} {'⚠ ' if r < 0.85 else ''}{hyp}", flush=True)
