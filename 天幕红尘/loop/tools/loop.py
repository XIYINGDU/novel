#!/usr/bin/env python3
"""天幕红尘 闭环工具。运行：
  uv run --with pyyaml python 天幕红尘/loop/tools/loop.py <cmd> ...

  lint                         去伪存真：字段、证据路径、过期平台规则；去粗取精：重复负向词、冗余规则
  compile --kind video --tags back_view,char:叶子农 [--ep 01] [--json]
                               由此及彼：按镜头标签合成 prompt/neg/params/流程清单
  qa --ep 01 --shot 21b --version p2-v0.2 --stage scout --tag wrong_expression \
     --symptom "..." --layer 锚点 [--rule ID] [--fix "..."] [--verdict open|fixed|accepted]
                               记一条判定到 ledger/defects.jsonl
  retro [--since 2026-11-01]   由表及里：按层归因、找治标不治本、找无规则缺陷、找失效/闲置规则
"""
import argparse, datetime as dt, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

LOOP = Path(__file__).resolve().parents[1]
TM = LOOP.parent
RULES = LOOP / "rules"
LEDGER = LOOP / "ledger" / "defects.jsonl"
REQUIRED = ["id", "status", "layer", "symptom", "root_cause", "scope"]
STATUSES = {"active", "candidate", "deprecated"}
KIND_ALL = {"video": "all_video", "audio": "all_audio", "script": "all_script"}
SYMPTOMATIC = re.compile(r"重抽|换种子|堆负向词|^负向词$")
STALE_DAYS = 30


def load_rules():
    out = []
    for f in sorted(RULES.glob("*.yaml")):
        for r in yaml.safe_load(f.read_text()) or []:
            r["_file"] = f.name
            out.append(r)
    return out


def load_defects():
    if not LEDGER.exists():
        return []
    return [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]


def evidence_exists(ev: str) -> bool:
    p = re.split(r"[#（(]", str(ev))[0].strip()
    if not p:
        return False
    return any((base / p).exists() for base in (LOOP, TM))


def cmd_lint(a):
    rules, errs, warns = load_rules(), [], []
    ids = Counter(r.get("id") for r in rules)
    for i, n in ids.items():
        if n > 1:
            errs.append(f"重复 id: {i}")
    neg_owner = defaultdict(list)
    today = dt.date.today()
    for r in rules:
        rid = r.get("id", "?")
        for k in REQUIRED:
            if not r.get(k):
                errs.append(f"{rid}: 缺字段 {k}")
        if r.get("status") not in STATUSES:
            errs.append(f"{rid}: status 非法 {r.get('status')}")
        ev = r.get("evidence") or []
        if r.get("status") == "active" and not ev:
            errs.append(f"{rid}: active 规则没有证据（去伪存真）")
        for e in ev:
            if not evidence_exists(e):
                errs.append(f"{rid}: 证据路径不存在 → {e}")
        if r.get("status") == "candidate" and not r.get("regress") and r["_file"] in ("video.yaml", "audio.yaml"):
            warns.append(f"{rid}: candidate 没写 regress 回归镜头，无法转正")
        lc = r.get("last_checked")
        if r.get("layer") == "平台" and r.get("status") == "active":
            if not lc:
                warns.append(f"{rid}: 平台规则没写 last_checked")
            elif (today - dt.date.fromisoformat(str(lc))).days > STALE_DAYS:
                warns.append(f"{rid}: 平台规则 {lc} 后未重验，可能已失效")
        for t in (r.get("action") or {}).get("neg", []) or []:
            neg_owner[t.lower()].append(rid)
    for t, owners in neg_owner.items():
        if len(owners) > 1:
            warns.append(f"负向词「{t}」在 {owners} 重复（去粗取精：合并或明确主从）")
    for e in errs:
        print("ERROR", e)
    for w in warns:
        print("WARN ", w)
    n = Counter(r.get("status") for r in rules)
    print(f"\n{len(rules)} 条规则：active {n['active']} / candidate {n['candidate']} / deprecated {n['deprecated']}；"
          f"{len(errs)} error，{len(warns)} warn")
    return 1 if errs else 0


def scope_hit(scope, tags, ep):
    """ep:NN 是约束（必须同时满足），其余是标签（命中任一即可）。"""
    eps = [s for s in scope if s.startswith("ep:")]
    rest = [s for s in scope if not s.startswith("ep:")]
    if eps:
        if not ep:
            return False
        ok = False
        for s in eps:
            m = re.fullmatch(r"ep:(\d+)(?:-(\d+))?", s)
            if m and int(m[1]) <= int(ep) <= int(m[2] or m[1]):
                ok = True
        if not ok:
            return False
    return not rest or any(s in tags for s in rest)


def cmd_compile(a):
    tags = {t.strip() for t in a.tags.split(",") if t.strip()}
    tags.add(KIND_ALL[a.kind])
    hit = [r for r in load_rules() if r.get("status") != "deprecated" and scope_hit(r.get("scope", []), tags, a.ep)]
    prompt, neg, params, process = [], [], {}, []
    for r in hit:
        act = r.get("action") or {}
        flag = "" if r["status"] == "active" else "［候选］"
        for p in act.get("prompt", []) or []:
            if p not in prompt:
                prompt.append(p)
        for n in act.get("neg", []) or []:
            if n not in neg:
                neg.append(n)
        params.update({f"{r['id']}.{k}": v for k, v in (act.get("params") or {}).items()})
        if act.get("process"):
            process.append(f"{flag}{r['id']}: {act['process']}")
        elif not act:
            process.append(f"{flag}{r['id']}: 红线——{r['symptom']}（{r['root_cause']}）")
    if a.json:
        json.dump({"rules": [r["id"] for r in hit], "prompt": prompt, "neg": neg, "params": params,
                   "process": process}, sys.stdout, ensure_ascii=False, indent=1)
        return 0
    print(f"# 命中 {len(hit)} 条：{', '.join(r['id'] for r in hit)}\n")
    print("## prompt 追加\n" + (", ".join(prompt) or "（无）"))
    print("\n## neg 追加（只对 Qwen i2i 关键帧有效；Wan LightX2V cfg=1 不读 neg，见 V-WAN-CFG1-NO-NEG）\n" + (", ".join(neg) or "（无）"))
    if params:
        print("\n## 参数")
        for k, v in params.items():
            print(f"- {k}: {v}")
    print("\n## 流程/红线清单（逐条打勾）")
    for p in process:
        print(f"- [ ] {p}")
    return 0


def cmd_qa(a):
    row = {"date": dt.date.today().isoformat(), "ep": a.ep, "shot": a.shot, "version": a.version,
           "stage": a.stage, "frames": a.frames, "tag": a.tag, "symptom": a.symptom, "cause_layer": a.layer,
           "rule": a.rule, "fix": a.fix, "verdict": a.verdict, "source": "qa"}
    rid = {r["id"] for r in load_rules()}
    if a.rule and a.rule not in rid:
        print(f"WARN 规则 {a.rule} 不存在——复盘时会当作「无规则缺陷」", file=sys.stderr)
    with LEDGER.open("a") as f:
        f.write(json.dumps({k: v for k, v in row.items() if v is not None}, ensure_ascii=False) + "\n")
    print("记入", LEDGER.relative_to(TM), row["shot"], row["tag"])
    return 0


def cmd_retro(a):
    rules = {r["id"]: r for r in load_rules()}
    ds = [d for d in load_defects() if not a.since or d["date"] == "backfill" or d["date"] >= a.since]
    print(f"# 复盘：{len(ds)} 条判定（since={a.since or '全部'}）\n")

    print("## 由表及里：缺陷按根因层")
    for layer, n in Counter(d.get("cause_layer", "?") for d in ds).most_common():
        print(f"- {layer}: {n}")

    print("\n## 同类症状反复出现（同 tag ≥2 镜）")
    by_tag = defaultdict(list)
    for d in ds:
        by_tag[d["tag"]].append(d)
    for tag, rows in sorted(by_tag.items(), key=lambda x: -len(x[1])):
        shots = sorted({r["shot"] for r in rows})
        if len(shots) >= 2:
            sym = sum(bool(SYMPTOMATIC.search(r.get("fix", ""))) for r in rows)
            mark = f"  ⚠ 其中 {sym} 次是治标（重抽/换种/堆负向词）" if sym else ""
            print(f"- {tag}: {len(shots)} 镜 {shots}{mark}")

    print("\n## 无规则缺陷（规则库的盲区）")
    orphan = [d for d in ds if not d.get("rule") or d["rule"] not in rules]
    for d in orphan:
        print(f"- {d['ep']}/{d['shot']} {d['tag']}: {d['symptom']}")
    if not orphan:
        print("- （无）")

    print("\n## 规则在被引用后仍复发（规则可能无效或没被执行）")
    last_fixed, bad = {}, []
    for d in ds:
        r = d.get("rule")
        if not r:
            continue
        if d["verdict"] == "open" and r in last_fixed:
            bad.append(f"- {r}: {last_fixed[r]} 后仍在 {d['shot']} 复发")
        if d["verdict"] == "fixed":
            last_fixed[r] = d["shot"]
    print("\n".join(bad) or "- （无）")

    print("\n## 候选规则（等回归转正）")
    for r in rules.values():
        if r["status"] == "candidate":
            print(f"- {r['id']} → regress {r.get('regress', '（未写）')}")

    cited = {d.get("rule") for d in ds}
    idle = [i for i, r in rules.items() if r["status"] == "active" and i not in cited and r["_file"] in ("video.yaml", "audio.yaml")]
    print("\n## 闲置规则（从未被缺陷引用；不必删，但下次复盘看是否冗余）")
    print("- " + ", ".join(idle) if idle else "- （无）")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("lint")
    c = sp.add_parser("compile")
    c.add_argument("--kind", choices=list(KIND_ALL), default="video")
    c.add_argument("--tags", default="")
    c.add_argument("--ep")
    c.add_argument("--json", action="store_true")
    q = sp.add_parser("qa")
    for k in ("ep", "shot", "version", "stage", "tag", "symptom", "layer"):
        q.add_argument(f"--{k}", required=True)
    q.add_argument("--frames")
    q.add_argument("--rule")
    q.add_argument("--fix", default="")
    q.add_argument("--verdict", choices=["open", "fixed", "accepted"], default="open")
    r = sp.add_parser("retro")
    r.add_argument("--since")
    a = ap.parse_args()
    sys.exit({"lint": cmd_lint, "compile": cmd_compile, "qa": cmd_qa, "retro": cmd_retro}[a.cmd](a))


if __name__ == "__main__":
    main()
