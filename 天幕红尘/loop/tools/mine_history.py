#!/usr/bin/env python3
"""由表及里：从历史版本脚本里挖出「事实上的缺陷记录」。

每当某镜在基础负向词之外又追加了词（NEG_X + ", smiling, ..."），
或出现 reroll/retry/_f1 这类重抽 id，就说明那一镜出过问题。
本脚本把这些追加词按词频和波及镜头统计出来，作为规则候选的证据。

用法: python3 loop/tools/mine_history.py [视频目录] > loop/ledger/mined.json
"""
import json, re, sys
from collections import defaultdict
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "视频")
PY_DELTA = re.compile(r'"id":\s*"([^"]+)"[\s\S]{0,400}?"neg":\s*NEG_[A-Z_]+\s*\+\s*"([^"]+)"')
JSON_NEG = re.compile(r'"id":\s*"([^"]+)"[\s\S]{0,200}?"neg":\s*"([^"]+)"')
BASE = set("色调艳丽 过曝 静态 细节模糊不清 字幕 文字水印 整体发灰 最差质量 低质量 JPEG压缩残留".split())
REROLL = re.compile(r"(reroll|retry|_f\d|_fix)", re.I)

terms = defaultdict(lambda: {"count": 0, "shots": set(), "files": set()})
rerolls = defaultdict(set)

for f in sorted(root.rglob("*")):
    if f.suffix not in (".py", ".json") or "__pycache__" in f.parts or "regress" in f.parts:
        continue
    text = f.read_text(errors="ignore")
    rel = str(f.relative_to(root))
    pat = PY_DELTA if f.suffix == ".py" else JSON_NEG
    for shot, neg in pat.findall(text):
        if REROLL.search(shot) or REROLL.search(f.name):
            rerolls[shot.split("_")[0]].add(rel)
        for t in re.split(r"[,，]", neg):
            t = t.strip().lower()
            if not t or t in BASE:
                continue
            e = terms[t]
            e["count"] += 1
            e["shots"].add(shot.split("_")[0])
            e["files"].add(rel)

out = {
    "terms": sorted(
        ({"term": t, "count": v["count"], "shots": sorted(v["shots"]), "files": sorted(v["files"])}
         for t, v in terms.items()),
        key=lambda x: (-len(x["shots"]), -x["count"]),
    ),
    "rerolled_shots": {k: sorted(v) for k, v in sorted(rerolls.items())},
}
json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
