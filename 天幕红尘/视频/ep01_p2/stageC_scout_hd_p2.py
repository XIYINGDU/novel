#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage C (ep01_p2): Fast 480p Scout -> Selective 720p HD Wan2.2 LightX2V Pipeline on EasyColab G4.
Reuses v09/v10 ComfyUI bridge & warm-session architecture so Wan2.2 14B (~35.4GB) stays hot between 480p scout and 720p HD!

Usage:
  stageC_scout_hd_p2.py --scout          # render 480p scout candidates & contact sheets, then stop_all
  stageC_scout_hd_p2.py --hd             # render 720p HD from hd_plan.json, then stop_all
  stageC_scout_hd_p2.py --warm-pipeline  # --scout -> wait for hd_plan.json -> --hd -> stop_all
  追加 --n 2 / --n 3：多台 G4 并行（common/colab_pool.py，规则 P-COLAB-DUAL-G4）；默认 --n 1 = 原单机行为
"""

import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

VID_ROOT = Path("/Users/duxiying/Documents/novel/天幕红尘/视频")
V09_DIR = VID_ROOT / "v09_fixes"
V10_DIR = VID_ROOT / "v10_fixes"
sys.path.insert(0, str(V09_DIR))
sys.path.insert(0, str(V10_DIR))

sys.path.insert(0, str(VID_ROOT / "common"))

import stage2_clips_v09 as s2v9
import stage2_scout_hd_v10 as s2v10
from colab_pool import ColabPool, Worker, hooks

P2 = VID_ROOT / "ep01_p2"
STILL_DIR = P2 / "stills"
SCOUT_DIR = P2 / "scout_clips"
CLIP_DIR = P2 / "clips"
SCRATCH_DIR = Path("/Users/duxiying/.gemini/antigravity-cli/brain/a18da7f8-846f-4989-874d-c081bff5e532/scratch")
for d in (SCOUT_DIR, CLIP_DIR, SCRATCH_DIR):
    d.mkdir(parents=True, exist_ok=True)

NEG_BASE = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，文字水印，整体发灰，最差质量，低质量，JPEG压缩残留，"
    "extra fingers, six fingers, fused fingers, deformed hands, missing fingers, extra limbs, third hand, "
    "modern smartphone, iPhone, wireless phone, rubbery face, morphing face, smiling, laughing, cheerful grin"
)


def make_default_scout_jobs() -> list[tuple]:
    """2 focused seeds per shot (30 fast 480p clips)."""
    defs = [
        # 14: Hui listening -> pale terrified realization (49f = 3.0s)
        (
            "14", "flf2v", STILL_DIR / "still_14_start.png", STILL_DIR / "still_14_end.png", 49, 8140,
            NEG_BASE + ", dropping phone, hospital",
            "Photorealistic 1991 35mm cinema still-to-motion transition in warm sunlit Manhattan living room. Holding beige corded phone firmly to ear, the 35-year-old Chinese woman hears shattering tragedy — eyes widen rapidly in horror, chest catches a sharp terrified breath, color drains tense and pale across her quivering face while curtains shimmer softly.",
            "Natural 1991 film realism in sunny Manhattan apartment beside sheer curtains and glass of water. Keeping beige telephone pressed to her ear, her puzzled frown freezes and snaps into wide-eyed pale terror and trembling disbelief.",
        ),
        # 15: Hui screams '哥!' -> limp shock, handset slips dangling by cord (41f = 2.5s)
        (
            "15", "flf2v", STILL_DIR / "still_15_start.png", STILL_DIR / "still_15_end.png", 41, 8150,
            NEG_BASE + ", hand touching shoulder, third hand on sweater, camera whip pan",
            "Tight emotional 1991 35mm MCU in sunny apartment. First moment she gasps and bursts out crying in terror gripping the beige handset; abruptly her trembling hand opens limp and drops below bottom frame leaving shoulders completely bare, as the beige phone handset falls swinging down across her chest suspended on its coiled cord.",
            "Intimate 35mm film close-up of heartbroken horrified woman. Her lips cry out one choked shout into the receiver, then shock paralyzes her: her fingers let go cleanly and drop out of frame while the beige handset tumbles dangling on its cord below her chin, staring pale ahead.",
        ),
        # 16: Lin rushes out from kitchen & snatches dangling handset to ear (41f = 2.5s)
        (
            "16", "flf2v", STILL_DIR / "still_16_start.png", STILL_DIR / "still_16_end.png", 41, 8160,
            NEG_BASE + ", slow motion, floating, smile",
            "Urgent realistic 1991 cinema medium shot in sunlit Manhattan apartment hallway beside wooden coffee table with water glass. The unsmiling aproned woman lunges swiftly forward, snatches the beige corded handset off the table edge in one decisive grab and slams it upright to her ear, leaning sharply forward demanding urgently.",
            "Dynamic brisk 1991 dramatic motion: frightened unsmiling Chinese woman in apron lunges from doorway, grabs the beige handset quickly, pulls it tight against her ear on its stretching coiled cord, breathing hard shouting sharply into the phone.",
        ),
        # 17: Su hears phone leak -> clutches center sweater chest in sudden heart trauma (49f = 3.0s)
        (
            "17", "flf2v", STILL_DIR / "still_17_start.png", STILL_DIR / "still_17_end.png", 49, 8170,
            NEG_BASE + ", sitting down, falling to floor yet, extra fingers",
            "Grounded 1991 35mm medium shot in sunny Manhattan living room with sheer curtains and glass of water on coffee table. Frozen beside the table listening to devastating leaked words, a sudden piercing pain strikes the 70-year-old grandmother's heart — face knots in silent pale agony, both trembling five-fingered hands rise swiftly clutching tight onto her beige cardigan right over center chest.",
            "Natural realistic 1991 film drama: silver-haired grandmother standing stiffly beside wooden table trembles from abrupt fatal chest pain, breathing arrested, squeezing eyes tight as both five-fingered hands clamp onto the wool knit over her sternum.",
        ),
        # 18a: Start IS 17_end -> rapid natural gravity collapse backward + glass tumbler falls & shatters spilling water! (41f = 2.5s)
        (
            "18a", "flf2v", STILL_DIR / "still_17_end.png", STILL_DIR / "still_18a_end_a.png", 41, 8180,
            NEG_BASE + ", slow floating sink, push-up hold, standing upright at end, upright glass remaining on table",
            "Static camera 1991 35mm realism starting locked on grandmother clutching her chest. Hold stunned rigid for 0.3 seconds, then both knees snap completely loose under true gravity and her body crashes briskly backward down onto the rug beside the sofa as her trailing arm clips the table edge — knocking the single clear water glass swiftly off the coffee table to shatter and splash water onto the wooden floor below.",
            "Locked-off dramatic 1991 film fall: sudden genuine gravitational collapse. After a split-second spasm holding her beige cardigan, the elderly grandmother topples swiftly backward stiffly onto the carpet behind the table; the single water glass sweeps off the corner and smashes spilling cold water across the foreground wood.",
        ),
        # 18b: Lin drops on knees cradling unconscious Su screaming for ambulance/pills (57f = 3.5s)
        (
            "18b", "i2v", STILL_DIR / "still_18b_start.png", None, 57, 8185,
            NEG_BASE + ", smiling, standing up, calm, hospital",
            "Emotional low-angle 1991 35mm MCU on sunlit floor beside spilled glass and water puddle. Holding the limp unconscious grandmother tightly against her shoulder, the aproned woman whips her tear-streaked terrified eyes urgently left and front, weeping and screaming frantically for heart medicine and an ambulance while rocking slightly with desperation.",
            "Intense desperate 1991 acting close-up: aproned Chinese woman cradles unconscious grandmother tightly on wood floor, chests heaving frantically as she looks up calling desperately off-screen for medicine and ambulance in panic.",
        ),
        # 19: Night Hospital ER doors — red IN SURGERY sign lamp snaps OFF! (33f = 2.0s)
        (
            "19", "flf2v", STILL_DIR / "still_19_start.png", STILL_DIR / "still_19_end.png", 33, 8190,
            NEG_BASE + ", people walking in corridor, camera panning away, red glow at end",
            "Static locked-off cold 1991 night hospital ER corridor shot facing frosted metal double doors. After holding tense quiet for half a second under fluorescent hum, the glowing red lightbox sign above the doors clicks abruptly dead dark OFF, leaving cool sterile greenish-white shadows across the empty corridor.",
            "Clean architectural 1991 cinema transition: empty cold New York ER hallway holds silent for a beat under dim fluorescent flicker, then the illuminated red rectangular sign over the frosted doors switches cleanly off to black.",
        ),
        # 20: American doctor exits wearing surgical mask -> pulls mask down -> heavy silent head shake (49f = 3.0s)
        (
            "20", "flf2v", STILL_DIR / "still_20_start.png", STILL_DIR / "still_20_end.png", 49, 8200,
            NEG_BASE + ", talking loudly, smiling, mask flying away, extra fingers",
            "Grave realistic 1991 35mm medium close-up under sterile pale hospital fluorescent light. With heavy sorrow in his tired eyes, the American surgeon uses his clean right hand to smoothly pull the blue surgical mask completely down off his nose and mouth to hang under his chin, drops his hand out of frame, then gives one slow grave solemn shake of his head looking sorrowfully ahead.",
            "Subtle heartbreaking 1991 medical drama close-up: American ER doctor pulls his blue surgical mask gently down below his chin and lowers his hand, pauses half a beat, and slowly solemnly shakes his head side to side in silent defeat.",
        ),
        # 21a: Hui buckles & slides down cold hospital corridor wall weeping (49f = 3.0s)
        (
            "21a", "flf2v", STILL_DIR / "still_21a_start.png", STILL_DIR / "still_21a_end.png", 49, 8210,
            NEG_BASE + ", camera zooming, teleporting clothes, apartment",
            "Static camera 1991 cold sterile hospital corridor medium-wide shot. Legs completely failing beneath sudden grief, the soft-grey sweatered woman drags her back straight down along the cold painted wall collapsing heavily into a slumped crying heap on the linoleum tiles, head dropping toward her knees weeping violently.",
            "Raw heartbroken 1991 acting: overwhelmed by grief, the Chinese woman's knees buckle swiftly and she slides limply down the cold hospital wall onto the tiled floor, trembling shoulders heaving as she bursts into helpless sobs.",
        ),
        # 21b: Tight low MCU Hui slumped against baseboard beating floor weakly & weeping (65f = 4.0s)
        (
            "21b", "i2v", STILL_DIR / "still_21b_start.png", None, 65, 8215,
            NEG_BASE + ", standing up, calm expression, cheerful, brown bag",
            "Raw devastating 1991 35mm low-angle close-up on cold hospital linoleum floor under harsh cool light. Slumped crying brokenly with tears streaming down pale cheeks, her trembling clenched fist beats twice weakly and helplessly against the cold floor tiles as shoulders heave sobbing bitterly.",
            "Visceral sorrowful 1991 hospital corridor close-up: weeping woman slumped tightly against white wall strikes her small clenched fist softly against the cold floor in sheer helplessness, sobbing brokenly through tears.",
        ),
        # 22: Lin leans against cold wall biting lower lip -> forces tears back into iron calm (49f = 3.0s)
        (
            "22", "flf2v", STILL_DIR / "still_22_start.png", STILL_DIR / "still_22_end.png", 49, 8220,
            NEG_BASE + ", mouth speaking words, laughing, warm living room, apron",
            "Tight dramatic silent 1991 35mm close-up leaning against white hospital wall under sterile night light. Her teeth bite down trembling lower lip while chest heaves through three controlled painful suppressed breaths holding unshed tears at bay; slowly she releases her bitten lip, swallows hard, and locks her jaw cold and steely dry-eyed.",
            "Powerful wordless 1991 psychological transformation close-up: red-rimmed eyes glistening with restrained tears while biting her lower lip hard, shoulders take two tense restrained breaths, then every tear vanishes as her face sets into iron unyielding resolve.",
        ),
        # 23: Lin bends & yanks sobbing Hui forcefully upright against cold white hospital wall (57f = 3.5s)
        (
            "23", "flf2v", STILL_DIR / "still_23_start.png", STILL_DIR / "still_23_end.png", 57, 8230,
            NEG_BASE + ", warm wood room, smiling, apron, three arms",
            "Static medium shot in sterile cold white-green 1991 hospital corridor under cool light. Unsmiling with fierce urgent resolve, the older dark-haired woman in dark grey-taupe top grips the younger grey-sweatered woman firmly by both shoulders and yanks her swiftly upright off the floor pinning her close at eye level against the white wall commanding fiercely.",
            "Intense physical confrontation in cold hospital hallway: stern cold-eyed woman bends down, hauls the weeping grey-sweatered woman briskly back onto her feet gripping both shoulders tightly against the white wall, staring fiercely at close range speaking harshly.",
        ),
        # 24a: Steely tight MCU Lin issuing lock-news & funeral command (73f = 4.5s)
        (
            "24a", "i2v", STILL_DIR / "still_24_lin_mcu.png", None, 73, 8240,
            NEG_BASE + ", smiling, nodding warmly, soft lighting",
            "Piercing static-frame 1991 35mm tight close-up in cold sterile hospital corridor light (listener shoulder blurred softly foreground left). Dry-eyed with cold steely authority, she speaks swiftly and decisively with slight crisp chin emphasis, never blinking, holding unshakable iron control.",
            "Sharp focused 1991 cinema close-up under fluorescent hospital hallway light: pale stern Chinese woman with cold razor-sharp eyes delivers brisk decisive orders at close range with controlled intense jaw movement and minimal subtle head tension.",
        ),
        # 24b: Reverse OTS onto tear-rimmed stunned Hui listening & obeying silently (81f = 5.0s)
        (
            "24b", "i2v", STILL_DIR / "still_24b_hui_ots.png", None, 81, 8245,
            NEG_BASE + ", talking loudly, smiling, listener turning face to camera",
            "Static reverse over-shoulder 1991 hospital corridor MCU onto tear-rimmed pale younger woman (dark blurred shoulder foreground right holds still). She listens frozen in stunned grief under cool fluorescent tubes, blinks moist dark eyes, catches a fragile breath and swallows timidly with one tiny helpless nod of silent obedience.",
            "Quiet tense reverse close-up in 1991 hospital night hallway: tear-rimmed sister stands pinned against cold wall listening stunned to fierce unseen commands, eyes trembling slightly with tiny swallow and faint obedient tremor.",
        ),
        # 24c: Final steely closer MCU Lin '剩下的事交给我！' cold dignity hold (81f = 5.0s)
        (
            "24c", "i2v", STILL_DIR / "still_24_lin_mcu.png", None, 81, 8250,
            NEG_BASE + ", smiling, laughing, relaxing",
            "Slow agonizingly steady push-in 1991 35mm close-up in cold hospital hallway light (listener head shadow left). She finishes delivering final solemn command with steel-hard composure, then holds dead still for final beats — chin steady, cold eyes burning with quiet unbroken defiance before night fades.",
            "Controlled heavy dramatic 1991 close-up subtly creeping a fraction closer: pale dry-eyed woman utters final decisive promise with quiet iron dignity, then locks gaze unflinching and silent through the final lingering second.",
        ),
    ]

    jobs = []
    for cid, mode, s_p, e_p, nf, base_seed, neg, p1, p2 in defs:
        jobs.append((f"{cid}_s1", mode, s_p, e_p, nf, base_seed + 1, neg, p1))
        jobs.append((f"{cid}_s2", mode, s_p, e_p, nf, base_seed + 2, neg, p2))
    return jobs


def make_p2_sheet(mp4_path: Path, step: int = 1) -> Path:
    """Create dense step=1 frame inspection sheet in SCRATCH_DIR."""
    out_png = SCRATCH_DIR / f"p2_{mp4_path.stem}.png"
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(mp4_path)],
        capture_output=True, text=True, check=True,
    )
    nf = max(1, int(res.stdout.strip() or "49"))
    # At ~1fps/every 2-3f or dense 6xN tile for step=1 on <=81f! For 81f step=2 gives 41f (7x6), step=1 on <=49f gives 7x7!
    use_step = 1 if nf <= 50 else 2
    cols = 7
    rows = (nf // use_step + cols - 1) // cols
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", str(mp4_path),
            "-vf", f"select='not(mod(n,{use_step}))',scale=280:-1,tile={cols}x{rows}",
            "-frames:v", "1", str(out_png),
        ],
        check=True,
    )
    return out_png


def resolve_jobs(json_path: Path, default_jobs: list[tuple]) -> list[tuple]:
    items = json.loads(json_path.read_text(encoding="utf-8"))
    by_id = {j[0]: j for j in default_jobs}
    out = []
    for item in items:
        if isinstance(item, str):
            out.append(by_id[item])
        else:
            base = list(by_id[item["base_id"]]) if item.get("base_id") in by_id else None
            if base is None:
                out.append((
                    item["id"], item["mode"], Path(item["start"]), Path(item["end"]) if item.get("end") else None,
                    int(item["frames"]), int(item["seed"]), item["neg"], item["prompt"],
                ))
            else:
                if "id" in item:
                    base[0] = item["id"]
                if "start" in item:
                    base[2] = Path(item["start"])
                if "end" in item:
                    base[3] = Path(item["end"]) if item["end"] else None
                if "frames" in item:
                    base[4] = int(item["frames"])
                if "seed" in item:
                    base[5] = int(item["seed"])
                if "neg" in item:
                    base[6] = item["neg"]
                if "prompt" in item:
                    base[7] = item["prompt"]
                out.append(tuple(base))
    return out


def setup_wan(w: Worker):
    """每台机器：拉起 ComfyUI + Wan2.2 权重；上传缓存按机器分开。"""
    w.log("启动 ComfyUI / Wan2.2 ...")
    cf_url = s2v9.ensure_wan22_and_comfyui(w.base_gradio)
    w.ctx.update(cf_url=cf_url, use_vhs=s2v9.has_vhs_node(cf_url), client_id=uuid.uuid4().hex, uploaded={})
    w.log(f"ComfyUI ready: {cf_url} (use_vhs={w.ctx['use_vhs']})")


def render(w: Worker, job, width: int, height: int, out_dir: Path, tag: str) -> Path:
    c = w.ctx
    mp4_p = s2v10.submit_and_download(c["cf_url"], w.base_gradio, c["client_id"], c["use_vhs"], c["uploaded"],
                                      job, width, height, out_dir, tag)
    w.log(f"done {mp4_p.name}")
    return mp4_p


def main():
    args = sys.argv[1:]
    n = 1
    if "--n" in args:
        k = args.index("--n")
        n = int(args[k + 1])
        del args[k:k + 2]
    mode_arg = args[0] if args else "--scout"
    scout_plan_path = P2 / "scout_plan.json"
    hd_plan_path = P2 / "hd_plan.json"
    scout_ready_flag = P2 / "scout_ready.json"
    default_jobs = make_default_scout_jobs()

    stage = "scout" if mode_arg == "--scout" else ("hd" if mode_arg == "--hd" else "scout+hd")
    with ColabPool(n=n, setup=setup_wan, seg="p2", stage=stage) as pool:
        if mode_arg in ("--scout", "--warm-pipeline"):
            if hd_plan_path.exists():
                hd_plan_path.unlink()
            if scout_ready_flag.exists():
                scout_ready_flag.unlink()
            scout_jobs = resolve_jobs(scout_plan_path, default_jobs) if scout_plan_path.exists() else default_jobs
            print(f"[SCOUT] {len(scout_jobs)} 个 832x480 镜头，{len(pool.workers)} 台并行...", flush=True)
            res, failed = pool.run(scout_jobs, lambda w, j: make_p2_sheet(render(w, j, 832, 480, SCOUT_DIR, "p2s")))
            sheets = [str(res[j[0]]) for j in scout_jobs if j[0] in res]  # 按原任务顺序
            scout_ready_flag.write_text(json.dumps({"sheets": sheets, "failed": failed, "ready_at": time.time()},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[SCOUT DONE] {len(sheets)} 张接触表；失败 {list(failed) or '无'}", flush=True)
            hooks.after_render("p2", "01", "scout", [SCOUT_DIR / f"clip_{j[0]}.mp4" for j in scout_jobs if j[0] in res])

        if mode_arg == "--warm-pipeline":
            print("[WAIT-APPROVAL] 机器保温，最多等 600s 的 hd_plan.json...", flush=True)
            deadline = time.time() + 600.0
            while time.time() < deadline:
                if hd_plan_path.exists() and hd_plan_path.stat().st_size > 10:
                    time.sleep(0.5)
                    break
                time.sleep(2.0)
            else:
                print("[TIMEOUT] 600s 内没有 hd_plan.json，关机。", flush=True)
                return

        if mode_arg in ("--hd", "--warm-pipeline"):
            hd_jobs = resolve_jobs(hd_plan_path, default_jobs) if hd_plan_path.exists() else [default_jobs[i] for i in range(0, len(default_jobs), 2)]
            print(f"[HD] {len(hd_jobs)} 个 1280x720 镜头，{len(pool.workers)} 台并行...", flush=True)
            res, failed = pool.run(hd_jobs, lambda w, j: make_p2_sheet(render(w, j, 1280, 720, CLIP_DIR, "p2hd")))
            print(f"[HD DONE] {len(res)} 个完成；失败 {list(failed) or '无'}", flush=True)
            hooks.after_render("p2", "01", "hd", [CLIP_DIR / f"clip_{j[0]}.mp4" for j in hd_jobs if j[0] in res])


if __name__ == "__main__":
    main()
