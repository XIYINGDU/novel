#!/usr/bin/env python3
"""ep01 p3 Scout（832×480）→ 选种 → HD。镜头见 分镜表.md，关键帧见 stills/。
- 台词镜 Scout 只出首段（≤81 帧≈5 s）；超长台词在 HD 阶段从选中镜末帧续接（V-CONTINUITY-ADJACENT）
- 种子：默认 2；细微表情镜 4（V-WAN-CFG1-NO-NEG）
- 两人同框不对口型：8n 拆成两个单人镜（LatentSync 会挑错脸）
用法：
  python3 stageC_scout_p3.py --scout [--n 3]            # 出 Scout + 接触表 + 自动量尺
  python3 stageC_scout_p3.py --hd [--n 2]               # 按 hd_plan.json 出 HD（[{"id": "s7c_s2"}, ...]）
  python3 stageC_scout_p3.py --redo --cont [--n 3]      # 重出 REDO 镜（HD 直出多种子）+ 续段（读 cont_plan.json）
续段：上一条 HD 的末帧作首帧 I2V、81 帧、HD 直出 1 种子（首帧本身是 HD，Scout 不可比，override V-SCOUT-THEN-HD）；
c2 依赖 c1 末帧，按轮次在同一个池里跑完。缺上游（如 7j 还没选种）的自动跳过。
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
import wan  # noqa: E402
from colab_pool import ColabPool, hooks  # noqa: E402

K = HERE / "stills"
SCOUT_DIR, HD_DIR, SHEETS = HERE / "scout", HERE / "clips", HERE / "sheets"
STYLE = " 1991 35mm film look, natural film grain, realistic, steady camera, subtle natural motion."
TALK = " She speaks naturally in a calm low voice, lips moving with the words, small natural head movements and blinks."
TALK_M = " He speaks naturally, lips moving with the words, small natural head movements and blinks."

# (镜, 模式, 首帧, 尾帧, 帧数, 种子数, 提示词, 标签)
SHOTS = [
    # ---- 1-7 ----
    ("s7a", "i2v", "k7a", None, 49, 2, "The man in the charcoal suit slides his passport and ticket onto the wooden counter; the young man in the "
     "blue shirt waits behind him; a few travellers walk slowly past. Static wide shot.", []),
    ("s7b", "i2v", "k7b", None, 41, 2, "His fingers unclip the small black pager from the belt and tilt it up toward his eyes; the green screen "
     "glows. Slight handheld drift.", ["hands"]),
    ("s7c", "i2v", "k7c", None, 81, 2, "The young man steps forward and speaks urgently to someone just off-screen left, holding the pager, brows "
     "tense." + TALK_M, ["dialogue"]),
    ("s7d", "flf2v", "k7d_s", "k7d_e", 49, 2, "Frowning, the man pulls his passport and ticket back from the counter, turns and strides off briskly.", []),
    ("s7e", "flf2v", "k7e_s", "k7e_e", 49, 2, "He pulls the booth door open, steps in, lifts the payphone receiver to his ear and glances at his watch.", []),
    ("s7f", "i2v", "k7f", None, 49, 2, "In the dim corridor she lifts the beige wall phone receiver to her ear and listens, cool and grave.", []),
    ("s7g", "i2v", "k_liang_booth", None, 81, 2, "Holding the receiver, he glances at his wristwatch and speaks in a low impatient voice." + TALK_M, ["dialogue"]),
    ("s7h", "i2v", "k_dai_corridor", None, 81, 2, "Holding the receiver to her ear, grave and steady." + TALK, ["dialogue"]),
    ("s7i", "i2v", "k_dai_corridor", None, 81, 2, "Holding the receiver, her eyes lower for a moment, then she delivers grave news, voice controlled." + TALK,
     ["dialogue", "emotion_negative"]),
    ("s7j", "i2v", "k_liang_booth", None, 41, 4, "He freezes, stunned, receiver at his ear; his eyes slowly widen, he stops breathing for a beat. Mouth closed.",
     ["emotion_negative"]),
    ("s7k", "i2v", "k_dai_corridor", None, 81, 2, "Holding the receiver, calm and methodical, explaining details." + TALK, ["dialogue"]),
    ("s7l", "i2v", "k_liang_booth", None, 81, 2, "He pushes his gold-rimmed glasses up with one finger, then argues quickly and firmly into the receiver."
     + TALK_M, ["dialogue"]),
    ("s7m", "i2v", "k_dai_corridor", None, 81, 2, "Unyielding, she answers firmly, chin slightly raised." + TALK, ["dialogue"]),
    ("s7n", "i2v", "k7e_e", None, 49, 2, "He sighs, says a short resigned sentence, then hangs the receiver back on the payphone.", ["dialogue"]),
    # ---- 1-8 ----
    ("s8a", "i2v", "k8a", None, 57, 2, "Reporters press in with cameras; he smiles politely, cups his fist in greeting and walks on past the "
     "guards toward the gate. Heat haze.", []),
    ("s8b", "i2v", "k8b", None, 81, 2, "The young woman hands him the sealed kraft envelope and speaks quietly with a stuffy nose; he takes it "
     "and nods." + TALK, ["dialogue"]),
    ("s8c", "i2v", "k8c", None, 57, 2, "Suspended on steel wires she swings slowly through the air, white coat and long hair streaming in the "
     "blower wind; lights glare. Slow camera pan.", []),
    ("s8d", "flf2v", "k8d_s", "k8d_e", 49, 2, "Swinging forward on the wires she raises both pistols and freezes into a cold aerial shooting pose. "
     "No muzzle flash.", []),
    ("s8e", "i2v", "k8e", None, 49, 2, "Sitting on the crate, he unfolds the curling fax sheets and begins to read, adjusting his glasses.", ["hands"]),
    ("s8f", "i2v", "k8f", None, 41, 2, "Very slow push-in on the fax page; the paper trembles slightly in his fingers. The four large handwritten "
     "characters stay sharp and unchanged.", ["text_sign"]),
    ("s8g", "flf2v", "k8g_s", "k8g_e", 57, 2, "She lands from the wires, knees buckling; two crew members catch her arms and half carry her toward "
     "camera; she lifts a hand to point at the far corner.", []),
    ("s8h1", "flf2v", "k8h_s", "k8h_e", 41, 2, "Exhausted, she lowers herself down into the folding chair and slumps back.", []),
    ("s8h2", "i2v", "k8h_e", None, 49, 2, "Slumped in the chair she wipes the sweat off her forehead with the tissue, panting.", ["hands"]),
    ("s8i", "i2v", "k8i", None, 81, 2, "He hands her the fax sheets and speaks flatly; she takes them without looking up." + TALK_M, ["dialogue"]),
    ("s8j", "i2v", "k_liang_studio", None, 81, 2, "Seated on the crate, he lays out the facts calmly, like reading accounts." + TALK_M, ["dialogue"]),
    ("s8k", "i2v", "k_dai_studio", None, 49, 4, "She turns to the last fax page and reads; her brows knit tighter and tighter. Mouth closed.",
     ["emotion_negative"]),
    ("s8l1", "flf2v", "k_dai_studio", "k8l_e", 33, 2, "She snaps the fax pages shut onto her lap with one hand and lifts her chin, disdainful.", []),
    ("s8l2", "i2v", "k8l_e", None, 81, 2, "With cold contempt she mocks, a faint scornful curl of the lip." + TALK, ["dialogue"]),
    ("s8m", "i2v", "k_liang_studio", None, 81, 2, "He lights a cigarette, exhales a thin stream of smoke, then speaks slowly with deep eyes." + TALK_M,
     ["dialogue"]),
    ("s8n_dai", "i2v", "k_dai_studio", None, 81, 2, "She lowers the fax, thinks for a moment, then asks a quiet question." + TALK, ["dialogue"]),
    ("s8n_liang", "i2v", "k_liang_studio", None, 81, 2, "He answers lightly with a worldly shrug." + TALK_M, ["dialogue"]),
    ("s8o", "i2v", "k_dai_studio", None, 81, 2, "Decisive, she gives a brief instruction." + TALK, ["dialogue"]),
    ("s8p", "i2v", "k8p", None, 81, 4, "Gazing up at the blinding spotlights, her eyes turn lost and uncertain; she asks softly." + TALK,
     ["dialogue", "emotion_negative"]),
    ("s8q", "i2v", "k_liang_studio", None, 41, 2, "He answers flatly and firmly, a short dry sentence." + TALK_M, ["dialogue"]),
]
SEED0 = 9000

# ---- 重出（2026-11-18，/tm-shot 编译过）：HD 直出多种子，xiying/vm 看接触表选
REDO = [
    # s7c：Scout s1 / HD s2 都把传呼机举到耳边当电话（defects #44 #47）→ 写死传呼机留在腰带上、手不过胸
    ("s7c", [2, 3], "i2v", "k7c", 81, "The young man steps forward and speaks urgently to someone just off-screen left. The small black "
     "pager stays clipped on his belt at the waist the whole time; his free hand stays low near his hip and never rises above his "
     "chest." + TALK_M),
    # s7j：HD 同种子张大 O 嘴（defects #48）；改 81 帧（时间线要它扛 1.2s 停顿 + 戴梦岩画外交代）
    ("s7j", [4, 5, 6, 7], "i2v", "k_liang_booth", 81, "He freezes, stunned, receiver at his ear; his eyes widen slightly and stay "
     "fixed; he holds his breath, then listens in silence. Lips stay softly closed, jaw still the whole time."),
]

# ---- 续段提示词：继承景别/姿态/地标（V-CONTINUITY-ADJACENT）；台词镜照常带 TALK（之后 LatentSync 覆盖嘴部）
_C = "Continuing the same shot from this exact frame: same framing, same pose and background, no cut. "
CONT_PROMPT = {
    "s7h": _C + "Holding the beige receiver to her ear in the dim corridor, grave and steady." + TALK,
    "s7i": _C + "Holding the receiver, voice controlled, she keeps delivering grave news." + TALK,
    "s7j": _C + "Receiver at his ear inside the booth, he listens in stunned silence, eyes fixed, breathing slowly. Lips stay "
           "softly closed, jaw still.",
    "s7k": _C + "Holding the receiver, calm and methodical, she keeps explaining details." + TALK,
    "s7l": _C + "Receiver at his ear inside the booth, he keeps arguing quickly and firmly." + TALK_M,
    "s7m": _C + "Holding the receiver, unyielding, chin slightly raised, she keeps answering firmly." + TALK,
    "s8j": _C + "Seated on the crate, he keeps laying out the facts calmly, like reading accounts." + TALK_M,
    "s8k": _C + "She keeps reading the last fax page, brows knitted, holding the sheets with five-finger bare hands, four fingers "
           "+ one thumb. Lips closed.",
    "s8l2": _C + "With cold contempt she keeps mocking, a faint scornful curl of the lip." + TALK,
    "s8m": _C + "Cigarette between his fingers, a thin wisp of smoke, he keeps speaking slowly with deep eyes." + TALK_M,
    "s8o": _C + "Decisive, she keeps giving brief instructions." + TALK,
    "s8p": _C + "Still gazing up toward the blinding spotlights, lost and uncertain, she keeps asking softly." + TALK,
}
CONT_DIR = HERE / "stills" / "cont"


def jobs():
    out = []
    for i, (sid, mode, s, e, nf, ns, prompt, _) in enumerate(SHOTS):
        for k in range(ns):
            out.append((f"{sid}_s{k + 1}", mode, K / f"{s}.png", (K / f"{e}.png") if e else None, nf, SEED0 + i * 10 + k,
                        "", prompt + STYLE))
    return out


def tags():
    return {sid: t for sid, *_, t in SHOTS}


def sheet(mp4: Path) -> Path:
    SHEETS.mkdir(exist_ok=True)
    out = SHEETS / f"{mp4.stem}.png"
    nf = int(subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries",
                             "stream=nb_read_packets", "-of", "csv=p=0", str(mp4)], capture_output=True, text=True).stdout or 49)
    step = 1 if nf <= 50 else 2  # V-QA-EVERY-FRAME：≤50 帧逐帧
    rows = (nf // step + 6) // 7
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp4), "-vf",
                    f"select='not(mod(n,{step}))',scale=240:-1,tile=7x{rows}", "-frames:v", "1", str(out)], check=True)
    return out


def redo_jobs():
    idx = {sid: i for i, (sid, *_) in enumerate(SHOTS)}
    return [(f"{sid}_s{k + 1}", mode, K / f"{kf}.png", None, nf, SEED0 + idx[sid] * 10 + k, "", prompt + STYLE)
            for sid, ks, mode, kf, nf, prompt in REDO for k in ks]


def last_frame(mp4: Path, png: Path) -> Path:
    png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.2", "-i", str(mp4), "-update", "1", "-q:v", "1", str(png)], check=True)
    return png


def cont_ready() -> tuple[list, list]:
    """返回 (上游已就绪的续段 job, 还在等上游的名字)。名字形如 clip_s7h_s1_c1。"""
    names = json.loads((HERE / "cont_plan.json").read_text())
    ready, wait = [], []
    for nm in names:
        cid = nm.removeprefix("clip_")
        if (HD_DIR / f"{nm}.mp4").exists():
            continue
        base, k = cid.rsplit("_c", 1)
        src = HD_DIR / (f"clip_{base}.mp4" if k == "1" else f"clip_{base}_c{int(k) - 1}.mp4")
        if not src.exists():
            wait.append(nm)
            continue
        sid = base.split("_s")[0] if not base.startswith("s8n") else base.rsplit("_s", 1)[0]
        png = last_frame(src, CONT_DIR / f"{cid}_first.png")
        seed = 9500 + sum(map(ord, cid)) % 400
        ready.append((cid, "i2v", png, None, 81, seed, "", CONT_PROMPT[sid] + STYLE))
    return ready, wait


def main():
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 2
    if "--scout" in sys.argv:
        todo = [j for j in jobs() if not (SCOUT_DIR / f"clip_{j[0]}.mp4").exists()]
        wait = [j[0] for j in todo if not j[2].exists() or (j[3] and not j[3].exists())]
        todo = [j for j in todo if j[0] not in wait]
        if wait:
            print(f"[scout] 关键帧未就绪，本轮跳过：{wait}")
        print(f"[scout] {len(todo)} 条（共 {len(jobs())}），{n} 台")
        with ColabPool(n=n, setup=wan.setup, seg="p3", stage="scout") as pool:
            res, failed = pool.run(todo, lambda w, j: wan.render(w, j, wan.SCOUT, SCOUT_DIR, "p3s"))
        for p in res.values():
            sheet(p)
        hooks.after_render("p3", "01", "scout", list(res.values()), tags())
        print(f"[scout] 完成 {len(res)}，失败 {failed or '无'}；接触表 → {SHEETS}")
    elif "--hd" in sys.argv:
        plan = json.loads((HERE / "hd_plan.json").read_text())
        by = {j[0]: j for j in jobs()}
        todo = [by[p["id"]] for p in plan if not (HD_DIR / f"clip_{p['id']}.mp4").exists()]
        with ColabPool(n=n, setup=wan.setup, seg="p3", stage="hd") as pool:
            res, failed = pool.run(todo, lambda w, j: wan.render(w, j, wan.HD, HD_DIR, "p3hd"))
        hooks.after_render("p3", "01", "hd", list(res.values()), tags())
        print(f"[hd] 完成 {len(res)}，失败 {failed or '无'}")
    elif "--redo" in sys.argv or "--cont" in sys.argv:
        todo = [j for j in redo_jobs() if not (HD_DIR / f"clip_{j[0]}.mp4").exists()] if "--redo" in sys.argv else []
        do_cont = "--cont" in sys.argv
        first, wait = cont_ready() if do_cont else ([], [])
        print(f"[redo] {[j[0] for j in todo]}\n[cont] 本轮 {[j[0] for j in first]}；等上游 {wait}")
        done, fails = [], {}
        with ColabPool(n=n, setup=wan.setup, seg="p3", stage="hd_cont") as pool:
            batch = todo + first
            while batch:
                res, failed = pool.run(batch, lambda w, j: wan.render(w, j, wan.HD, HD_DIR, "p3hd"))
                done += list(res.values())
                fails.update(failed)
                if not do_cont or not res:
                    break
                batch, wait = cont_ready()
                batch = [j for j in batch if j[0] not in fails]
                if batch:
                    print(f"[cont] 下一轮 {[j[0] for j in batch]}")
        for p in done:
            sheet(p)
        hooks.after_render("p3", "01", "hd", done, tags())
        print(f"[redo/cont] 完成 {len(done)}，失败 {fails or '无'}；仍在等上游 {wait}；接触表 → {SHEETS}")


if __name__ == "__main__":
    main()
