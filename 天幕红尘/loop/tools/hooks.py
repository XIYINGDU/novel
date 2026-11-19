#!/usr/bin/env python3
"""闭环自动触发（自我迭代）：出片脚本 import 它，环就不靠人记得去转。

- record_run()   每次云端运行自动记账（ColabPool 退出时调用）→ ledger/runs.jsonl
- after_render() 出片后自动跑表情量尺，机器旗标写 defects.jsonl（source=machine, verdict=pending）
- after_build()  成片后记时长，自动出分数卡 + 复盘报告 → ledger/retro/<日期>_<段>.md
- budget_check() 自动回归花钱前查额度（loop/budget.yaml）
只依赖标准库；量尺走子进程 uv（mediapipe 环境）。
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

LOOP = Path(__file__).resolve().parents[1]
TM = LOOP.parent
NOVEL = TM.parent
LEDGER = LOOP / "ledger"
RUNS = LEDGER / "runs.jsonl"
DEFECTS = LEDGER / "defects.jsonl"
BUDGET = LOOP / "budget.yaml"
EMOTION_FLAG_TAGS = ("emotion_negative", "crying", "cold")  # 这些镜头 laugh_read 必须为 0（V-QA-FACE-METRIC）


def _now():
    return dt.datetime.now().isoformat(timespec="seconds")


def _append(path: Path, row: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_budget() -> dict:
    d = {"auto_cu_per_run": 2.0, "auto_cu_per_day": 5.0}
    if BUDGET.exists():  # 简单 key: value 解析，免 pyyaml 依赖
        for line in BUDGET.read_text().splitlines():
            line = line.split("#")[0].strip()
            if ":" in line:
                k, v = (x.strip() for x in line.split(":", 1))
                try:
                    d[k] = float(v)
                except ValueError:
                    d[k] = v
    return d


def runs() -> list[dict]:
    return [json.loads(l) for l in RUNS.read_text().splitlines() if l.strip()] if RUNS.exists() else []


def auto_spent_today() -> float:
    today = dt.date.today().isoformat()
    return sum(r.get("cu_est", 0) for r in runs() if r.get("auto") and r.get("ts", "").startswith(today))


def budget_check(est_cu: float) -> tuple[bool, str]:
    """自动（无人批准）花钱前调用。超额返回 False，须问 xiying。"""
    b = load_budget()
    spent = auto_spent_today()
    if est_cu > b["auto_cu_per_run"]:
        return False, f"预估 {est_cu:.2f} CU 超过单次自动额度 {b['auto_cu_per_run']}"
    if spent + est_cu > b["auto_cu_per_day"]:
        return False, f"今日自动已花 {spent:.2f}，再花 {est_cu:.2f} 超过日额度 {b['auto_cu_per_day']}"
    return True, f"额度内（单次 ≤{b['auto_cu_per_run']}，今日已用 {spent:.2f}/{b['auto_cu_per_day']}）"


def record_run(seg: str, stage: str, workers: int, jobs: int, failed: int, wall_s: float,
               machine_h: float, cu_est: float, auto: bool = False, note: str = ""):
    row = {"ts": _now(), "seg": seg, "stage": stage, "workers": workers, "jobs": jobs, "failed": failed,
           "wall_s": round(wall_s), "machine_h": round(machine_h, 3), "cu_est": round(cu_est, 2), "auto": auto}
    if note:
        row["note"] = note
    _append(RUNS, row)
    print(f"[loop] 运行已入账 runs.jsonl：{seg}/{stage} {jobs} 任务 {failed} 失败，墙钟 {wall_s / 60:.1f} 分，约 {cu_est:.2f} CU", flush=True)


def after_render(seg: str, ep: str, stage: str, clips: list[Path], shot_tags: dict[str, list[str]] | None = None):
    """出片后自动量尺。shot_tags: {镜头id: [标签]}，情绪镜头读成笑>0 自动记 machine 旗标。"""
    clips = [Path(c) for c in clips if Path(c).exists()]
    if not clips:
        return []
    out_json = LEDGER / "metrics" / f"{seg}_{stage}_{dt.datetime.now():%Y%m%d_%H%M%S}.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["uv", "run", "-q", "--python", "3.11", "--with", "mediapipe==0.10.21", "--with", "opencv-python-headless",
           "python", str(LOOP / "tools" / "face_metrics.py"), *map(str, clips), "--step", "2", "--json", str(out_json)]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=TM)
    if r.returncode != 0 or not out_json.exists():
        print(f"[loop] 量尺失败（不阻塞出片）：{r.stderr[-300:]}", flush=True)
        return []
    flags = []
    for m in json.loads(out_json.read_text()):
        shot = Path(m["file"]).stem.removeprefix("clip_")
        base = shot.rsplit("_s", 1)[0]
        tags = (shot_tags or {}).get(shot) or (shot_tags or {}).get(base) or []
        if m.get("faces") and m.get("laugh_read", 0) > 0 and any(t in tags for t in EMOTION_FLAG_TAGS):
            row = {"date": dt.date.today().isoformat(), "ep": ep, "shot": shot, "version": seg, "stage": stage,
                   "tag": "laugh_read", "symptom": f"量尺：读成笑 {m['laugh_read']} 帧（smile_max {m['smile_max']}）",
                   "cause_layer": "?", "rule": "V-QA-FACE-METRIC", "fix": "", "verdict": "pending", "source": "machine"}
            _append(DEFECTS, row)
            flags.append(shot)
    print(f"[loop] 量尺 {len(clips)} 条 → {out_json.name}；机器旗标 {flags or '无'}（待人眼复核）", flush=True)
    return flags


def after_build(seg: str, ep: str, final_mp4: Path):
    """成片后：记时长 → 分数卡 → 复盘报告。"""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(final_mp4)],
                       capture_output=True, text=True)
    dur = float(r.stdout.strip() or 0)
    _append(RUNS, {"ts": _now(), "seg": seg, "stage": "build", "final": str(final_mp4.name), "final_s": round(dur, 2)})
    loop_py = [sys.executable if _has_yaml() else "uv", *([] if _has_yaml() else ["run", "-q", "--with", "pyyaml", "python"]),
               str(LOOP / "tools" / "loop.py")]
    sc = subprocess.run([*loop_py, "score", "--seg", seg], capture_output=True, text=True, cwd=NOVEL).stdout
    rt = subprocess.run([*loop_py, "retro", "--since", dt.date.today().isoformat()], capture_output=True, text=True, cwd=NOVEL).stdout
    out = LEDGER / "retro" / f"{dt.date.today().isoformat()}_{seg}_auto.md"
    out.write_text(f"# 自动复盘：{seg}（{final_mp4.name}，{dur:.1f}s）\n\n{sc}\n{rt}\n"
                   "> 机器生成。提案须经 /tm-retro 由 vm 核实、xiying 批准后才改规则。\n")
    print(f"[loop] 成片 {dur:.1f}s 已入账；分数卡与自动复盘 → {out.relative_to(TM)}", flush=True)
    return out


def _has_yaml() -> bool:
    try:
        import yaml  # noqa: F401
        return True
    except ImportError:
        return False
