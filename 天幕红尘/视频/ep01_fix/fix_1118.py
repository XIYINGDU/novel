#!/Users/duxiying/.local/share/uv/tools/google-colab-cli/bin/python
# -*- coding: utf-8 -*-
"""ep01 p2+p3 修复批（2026-11-18，xiying「修吧，再把 p3 也修一下」）。defects 见 loop/ledger/defects.jsonl。

  .../google-colab-cli/bin/python ep01_fix/fix_1118.py stills          # Qwen i2i：21a 首帧去笑、23 首尾帧慧娟改回长发圆领
  .../google-colab-cli/bin/python ep01_fix/fix_1118.py wan [--n 3]     # Wan HD：21a×4 23×3 24a×4（p2）8m×4（p3）；读 picks.json 的 still 选择
  .../google-colab-cli/bin/python ep01_fix/fix_1118.py cont            # 8m 选中种子的续段（末帧 I2V）
规则（loop compile 2026-11-18）：V-GRIEF-AU-PROMPT（AU 描述；有台词不写 lips closed）、V-WAN-CFG1-NO-NEG（Wan 不读负向，
表情镜 ≥4 种子）、P-SHM-NO-MIX（Qwen 与 Wan 分池）、V-HAND-ANATOMY（23 手）、V-CONTINUITY-ADJACENT（续段首帧=末帧）。
override V-SCOUT-THEN-HD：返修镜 HD 直出多种子（首帧/动作已在旧版验证过，只换表情/服装）。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VID = HERE.parent
sys.path.insert(0, str(VID / "common"))
import qwen  # noqa: E402
import wan  # noqa: E402
from colab_pool import ColabPool, hooks  # noqa: E402

P2, P3 = VID / "ep01_p2", VID / "ep01_p3"
P2S, P3S = P2 / "stills", P3 / "stills"
FIX_STILLS = P2S / "fix1118"
PICKS = HERE / "picks.json"  # {"21a_start": "<png>", "23_start": ..., "23_end": ..., "8m": "clip_s8m_s6"}

NEG_NY = ("cartoon, anime, CGI, 3d render, oversaturated, plastic skin, modern smartphone, wireless phone, iPhone, "
          "flatscreen TV, watermark, subtitle, text, extra fingers, deformed hands, fused fingers, six fingers")
NO_SMILE = ", smiling, smile, grin, cheerful, smirk, pleasant expression, teeth showing in a smile, laughing, raised cheeks"
STYLE_Q = qwen.STYLE
STYLE_W = " 1991 35mm film look, natural film grain, realistic, steady camera, subtle natural motion."
GRIEF_AU = "inner eyebrows raised and pinched upward, mouth corners pulled down, chin trembling, wet eyes"
HUI_LOOK = ("long straight black hair falling past her shoulders, soft heather-grey crewneck knit sweater with a round "
            "neck (no collar, no buttons), black trousers")
LIN_LOOK = "shoulder-length black hair, dark grey collared button cardigan"
HANDS = " five-finger bare hands, four fingers + one thumb."
TALK_M = " He speaks naturally, lips moving with the words, small natural head movements and blinks."

# ---------- 阶段 1：Qwen 关键帧（每张 2 种子） ----------
STILLS = []
for k, seed in enumerate((7811, 7812)):
    STILLS += [
        dict(id=f"21a_start_k{k + 1}", ref=P2S / "still_21a_start.png", seed=seed,
             neg=NEG_NY + NO_SMILE,
             prompt=("STRICTLY KEEP THE EXACT SAME static camera framing, cold green-white hospital corridor, lighting, and the "
                     "same 35-year-old Chinese woman leaning back against the wall in the same pose, " + HUI_LOOK + ", flat "
                     "shoes. Change ONLY her face to raw grief: " + GRIEF_AU + ", eyes squeezed half shut, no smile at all, "
                     "cheeks not raised. " + STYLE_Q)),
        dict(id=f"23_start_k{k + 1}", ref=P2S / "still_23_start.png", seed=seed + 10,
             neg=NEG_NY + NO_SMILE + ", short hair, bob haircut, collar on the younger woman, buttons on the younger woman, "
                 "matching outfits, extra arm, three hands",
             prompt=("STRICTLY KEEP THE EXACT SAME camera framing, hospital corridor, lighting, and the older woman on the right "
                     "(" + LIN_LOOK + ") bending forward gripping the younger woman's shoulders with both hands. Change ONLY "
                     "the younger woman crouched against the wall on the left: she has " + HUI_LOOK + "; her head bowed in "
                     "grief." + HANDS + " " + STYLE_Q)),
        dict(id=f"23_end_k{k + 1}", ref=P2S / "still_23_end.png", seed=seed + 20,
             neg=NEG_NY + NO_SMILE + ", short hair, bob haircut, collar on the younger woman, buttons on the younger woman, "
                 "matching outfits, extra arm, three hands",
             prompt=("STRICTLY KEEP THE EXACT SAME camera framing, hospital corridor, lighting, and the older woman on the right "
                     "(" + LIN_LOOK + ") gripping the younger woman's shoulders, staring at her fiercely. Change ONLY the "
                     "younger woman standing against the wall on the left, seen in profile: she has " + HUI_LOOK + "; tear-"
                     "stained face, " + GRIEF_AU + "." + HANDS + " " + STYLE_Q)),
    ]


def run_stills():
    jobs = [{"out": FIX_STILLS / f"{s['id']}.png", "mode": "i2i_edit", "ref": s["ref"], "seed": s["seed"],
             "prompt": s["prompt"], "neg": s["neg"]} for s in STILLS]
    with ColabPool(n=1, setup=qwen.setup, seg="p2", stage="stills_fix") as pool:
        res, failed = pool.run(jobs, qwen.render_job, key=lambda j: j["out"].stem)
    print(f"[stills] {len(res)} 张；失败 {failed or '无'} → {FIX_STILLS}", flush=True)


# ---------- 阶段 2：Wan HD ----------
def wan_jobs(picks: dict) -> list[tuple]:
    j = []
    s21 = Path(picks["21a_start"])
    for k in range(4):
        j.append((f"p2:21a_v3s{k + 1}", "flf2v", s21, P2S / "still_21a_end.png", 49, 8310 + k, "",
                  "Static camera 1991 cold sterile hospital corridor medium-wide shot. Her legs give way beneath her and the "
                  "woman in the soft grey crewneck sweater slides her back straight down along the cold painted wall until she "
                  "sits slumped on the linoleum floor, knees drawn up. Throughout, her face shows grief: " + GRIEF_AU +
                  "; shoulders shaking. She speaks a few broken words." + STYLE_W))
    for k in range(3):
        j.append((f"p2:23_v3s{k + 1}", "flf2v", Path(picks["23_start"]), Path(picks["23_end"]), 57, 8330 + k, "",
                  "Static medium shot in a sterile cold white hospital corridor under cool light. The older woman (" + LIN_LOOK +
                  "), unsmiling with fierce urgent resolve, grips the younger woman (" + HUI_LOOK + ") firmly by both "
                  "shoulders and pulls her up off the floor, pinning her upright against the white wall at eye level, and "
                  "speaks to her harshly at close range." + HANDS + STYLE_W))
    for k in range(4):
        j.append((f"p2:24a_v3s{k + 1}", "i2v", P2S / "still_24_lin_mcu.png", None, 73, 8340 + k, "",
                  "Static tight close-up in a cold sterile hospital corridor (listener's dark shoulder blurred in the left "
                  "foreground). Dry-eyed, hoarse and iron-hard, she gives orders: brows drawn down and together, eyes narrowed "
                  "and fixed on the listener, jaw set hard, mouth corners flat, eyebrows never lift, face never softens, "
                  "almost no head movement. She speaks, lips moving with the words." + STYLE_W))
    for k in range(4):
        j.append((f"p3:s8m_s{k + 3}", "i2v", P3S / "k_liang_studio.png", None, 81, 9400 + k, "",
                  "In the first second he puts a cigarette between his lips and lights it with a small lighter, then lowers the "
                  "lighter out of frame and takes the lit cigarette between the index and middle fingers of his right hand, "
                  "keeping that hand raised near his chin with the burning cigarette clearly visible and a thin wisp of smoke "
                  "rising for the whole rest of the shot. Then he speaks slowly with deep eyes." + TALK_M + STYLE_W))
    return j


def out_dir(jid: str) -> tuple[Path, str]:
    seg, name = jid.split(":", 1)
    return (P2 / "clips" if seg == "p2" else P3 / "clips"), name


def render_one(w, job):
    d, name = out_dir(job[0])
    p = wan.render(w, (name,) + tuple(job[1:]), wan.HD, d, "fix")
    want = d / f"clip_{name}.mp4"
    if p != want and p.exists():
        p.rename(want)
    return want


def run_wan(n: int):
    picks = json.loads(PICKS.read_text(encoding="utf-8"))
    jobs = [j for j in wan_jobs(picks) if not (out_dir(j[0])[0] / f"clip_{out_dir(j[0])[1]}.mp4").exists()]
    print(f"[wan] {len(jobs)} 条 HD：{[j[0] for j in jobs]}", flush=True)
    with ColabPool(n=n, setup=wan.setup, seg="fix", stage="hd") as pool:
        res, failed = pool.run(jobs, render_one, key=lambda j: j[0])
    print(f"[wan] 完成 {len(res)}；失败 {failed or '无'}", flush=True)
    hooks.after_render("fix", "01", "hd", [Path(v) for v in res.values()])


def last_frame(mp4: Path, png: Path) -> Path:
    png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.2", "-i", str(mp4), "-update", "1", "-q:v", "1", str(png)],
                   check=True)
    return png


def run_cont():
    picks = json.loads(PICKS.read_text(encoding="utf-8"))
    base = picks["8m"]  # e.g. clip_s8m_s4
    src = P3 / "clips" / f"{base}.mp4"
    png = last_frame(src, P3S / "cont" / f"{base}_last.png")
    job = (f"p3:{base.removeprefix('clip_')}_c1", "i2v", png, None, 81, 9450, "",
           "Continuing the same shot from this exact frame: same framing, same pose and background, no cut. The lit cigarette "
           "stays between the index and middle fingers of his raised right hand near his chin, a thin wisp of smoke rising; "
           "he keeps speaking slowly with deep eyes." + TALK_M + STYLE_W)
    with ColabPool(n=1, setup=wan.setup, seg="fix", stage="cont") as pool:
        res, failed = pool.run([job], render_one, key=lambda j: j[0])
    print(f"[cont] {res} 失败 {failed or '无'}", flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    n = int(a[a.index("--n") + 1]) if "--n" in a else 3
    {"stills": run_stills, "wan": lambda: run_wan(n), "cont": run_cont}[a[0]]()
