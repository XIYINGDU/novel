#!/usr/bin/env python3
"""ep01 p3 关键帧（1-7 机场电话亭 / 1-8 摄影棚）。镜头见 分镜表.md；设定依据原著第二章。
同机位的台词镜共用一张关键帧（正反打连贯，V-CONTINUITY-ADJACENT）。
负向词只在这里有效（V-WAN-CFG1-NO-NEG）。传真「见路不走」单独出源图（V-PROP-PIXEL-LOCK）。
用法：uv run -q --with pillow python stageB2_keyframes_p3.py [--n 2] [--only id1,id2]
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VID = HERE.parent
sys.path.insert(0, str(VID / "common"))
import qwen  # noqa: E402
from colab_pool import ColabPool  # noqa: E402

REF = VID / "ref"
STILLS = HERE / "stills"
S = qwen.STYLE
NEG = qwen.NEG_PORTRAIT + (", modern airport, glass curtain wall, floor-to-ceiling windows, high ceiling, skylight, blue signage, "
                           "backpack, rolling suitcase, sportswear, LED screen, digital display, smartphone, laptop, 2020s fashion, "
                           "readable signage, garbled chinese characters, broad smile, grin, laughing")
LIANG = ("Keep the EXACT same Hong Kong Chinese man in his early forties (same face, neatly combed short dark hair, thin gold-rimmed "
         "eyeglasses, tailored charcoal double-breasted suit, white shirt, muted silk tie). ")
DAI = ("Keep the EXACT same 28-year-old Hong Kong Chinese film star (same face, long flowing black hair, heavy glamorous film makeup, "
       "long white late-autumn trench coat costume). ")
HAN = "Keep the EXACT same young Beijing man (same face, short haircut, short-sleeved pale blue cotton shirt, black pager on his belt). "
AYING = "Keep the EXACT same 27-year-old Chinese assistant (same face, hair tied back, light-grey blouse, slightly red nose from a cold). "
T1 = ("inside the dated 1991 Beijing Capital Airport departure hall built in 1980: LOW concrete ceiling with rows of plain "
       "fluorescent tube fixtures, square concrete pillars clad in beige tile, worn beige terrazzo floor, heavy brown varnished wooden "
       "check-in counters with old CAAC scales, small high windows only, slightly dim yellowish light, sparse travellers in early-1990s "
       "Chinese clothing (white short-sleeved shirts, grey jackets, cloth bags, old leather suitcases), no readable signs")  # v2：v1 太现代
BOOTH = ("inside a small 1991 Chinese public telephone booth of dark varnished wood with a half-glass folding door and a grey metal "
         "payphone on the wall, dim dated airport hall with low fluorescent ceiling blurred behind")
CORRIDOR = ("in a dim 1991 Beijing film studio backstage corridor with peeling pale-green painted walls, cables on the floor, a beige "
            "wall-mounted extension telephone, hot hazy summer light from a doorway")
STUDIO = ("inside a huge hot 1991 Beijing film soundstage: big industrial blower fans, blinding tungsten lights on stands, a camera "
          "crane, crew in sweaty T-shirts, dusty air")
CORNER = "in a far dim corner of the hot 1991 Beijing film soundstage, old wooden crates and coiled cables, bright set lights glaring far behind"

KEYFRAMES = [
    # 定妆补齐：戴梦岩中性版（同脸）
    {"id": "ref_dai_neutral", "ref": REF / "戴梦岩_戏服.png", "seed": 7310,
     "prompt": "Keep the EXACT same woman's face and long black hair, but now off duty: light natural makeup, simple cream silk blouse, "
               "plain softly blurred interior, calm neutral expression, mouth closed. Medium close-up portrait. " + S},
    # ---- 1-7 ----
    {"id": "k7a", "ref": REF / "梁士乔.png", "seed": 7721,
     "prompt": LIANG + "Wide shot " + T1 + ". He stands at a check-in counter handing over a passport and ticket, black leather business "
               "shoulder bag on his shoulder; a young man in a short-sleeved pale blue shirt holding a document folder waits a step behind him. " + S},
    {"id": "k7b", "ref": REF / "韩平.png", "seed": 7712,  # v2：v1 画成带键盘的计算器
     "neg": NEG + ", keypad, number buttons, calculator, mobile phone, cellphone",
     "prompt": HAN + "Extreme close-up of his waist: his hand lifts a tiny black 1991 numeric pager (matchbox-sized plastic beeper with a "
               "belt clip, a single narrow one-line green LCD strip and only two small buttons on top, NO keypad) off his leather belt, "
               "the LCD glowing with no readable text, pale blue shirt, airport terrazzo blurred behind. " + S},
    {"id": "k7c", "ref": REF / "韩平.png", "seed": 7723,
     "prompt": HAN + "Medium close-up " + T1.replace("inside ", "in ") + ". He looks up from the pager with sudden urgency, brows tense, "
               "lips parted about to speak, document folder under his arm. " + S},
    {"id": "k7d_s", "ref": REF / "梁士乔.png", "seed": 7724,
     "prompt": LIANG + "Medium shot " + T1.replace("inside ", "at a brown wooden check-in counter ") + ". Brows knitted, he reaches to "
               "pull his passport and ticket back off the counter, black business bag on shoulder. " + S},
    {"id": "k7d_e", "ref_still_id": "k7d_s", "seed": 7725,
     "prompt": "STRICTLY KEEP the exact same man, suit, glasses, bag and the same 1991 airport hall. Now he has turned away from the "
               "counter, passport and ticket in hand, striding briskly toward screen left, serious face. Same lighting. " + S},
    {"id": "k7e_s", "ref": REF / "梁士乔.png", "seed": 7736,
     "prompt": LIANG + "Medium shot " + T1.replace("inside ", "in ") + ", beside a row of small dark-wood public telephone booths with half-glass "
               "folding doors; he pulls a booth door open with one hand, passport in the other, hurried. " + S},
    {"id": "k7e_e", "ref_still_id": "k7e_s", "seed": 7737,
     "prompt": "STRICTLY KEEP the exact same man, suit and glasses, same booth row and camera. Now he stands inside the booth, grey payphone "
               "receiver held to his ear, other hand on the dial, glancing at his wristwatch, glass door half open. " + S},
    {"id": "k_liang_booth", "ref": REF / "梁士乔.png", "seed": 7728,
     "prompt": LIANG + "Close-up " + BOOTH + ". He holds the grey payphone receiver to his ear, listening, composed but alert, mouth closed. " + S},
    {"id": "k7f", "ref": REF / "戴梦岩_戏服.png", "seed": 7709,
     "prompt": DAI + "Medium shot " + CORRIDOR + ". She lifts the beige wall telephone receiver to her ear, cool and grave. " + S},
    {"id": "k_dai_corridor", "ref": REF / "戴梦岩_戏服.png", "seed": 7710,
     "prompt": DAI + "Close-up " + CORRIDOR + ". She holds the beige receiver to her ear, calm, grave, steady eyes, mouth closed. " + S},
    # ---- 1-8 ----
    {"id": "k8a", "ref": REF / "梁士乔.png", "seed": 7801,
     "prompt": LIANG + "Wide shot outside a 1991 Beijing film studio gate in scorching August sun: two uniformed security guards at the "
               "gate, a few entertainment reporters with film cameras crowd him; he smiles politely and cups his fist in greeting while "
               "brushing past. Heat haze. " + S},
    {"id": "k8b", "ref": VID / "ep01_p3" / "ref_tmp" / "comp_aying_liang.png", "seed": 7822,  # v2：v1 门匾乱码
     "neg": NEG + ", signboard, plaque, chinese characters, calligraphy, any text",
     "prompt": "Use the two people from the reference image (keep both faces and clothes exactly): two-shot beside a plain grey brick "
               "wall and an unmarked iron gate with NO signboard or plaque, hot summer daylight outside a 1991 Beijing film studio; the young assistant woman (left in reference) hands a sealed brown kraft paper envelope "
               "to the man in the charcoal suit and gold-rimmed glasses, speaking quietly; he takes it, nodding. " + S},
    {"id": "k8c", "ref": REF / "戴梦岩_戏服.png", "seed": 7803,
     "prompt": DAI + "Wide shot " + STUDIO + ". She hangs mid-air on thin steel wires from a harness under her white trench coat, long hair "
               "streaming in the blower wind, a black military pistol in each hand. " + S},
    {"id": "k8d_s", "ref": REF / "戴梦岩_戏服.png", "seed": 7804,
     "prompt": DAI + "Medium shot " + STUDIO + ". Suspended mid-air on steel wires, she swings forward, coat flaring, two black military "
               "pistols held low at her sides. " + S},
    {"id": "k8d_e", "ref_still_id": "k8d_s", "seed": 7805,
     "prompt": "STRICTLY KEEP the exact same woman, white trench coat, wires, studio and camera. Now she freezes in a cold stylish aerial "
               "pose, both arms extended, aiming the two pistols straight past camera, icy stare, hair blown back. No muzzle flash. " + S},
    {"id": "k8e", "ref": REF / "梁士乔.png", "seed": 7806,
     "prompt": LIANG + "Medium shot " + CORNER + ". He sits on an old wooden crate, the opened kraft envelope beside him, pulling out three "
               "thin sheets of curling thermal fax paper densely covered in illegible handwriting. " + S},
    {"id": "k8f", "seed": 7807, "mode": "t2i",
     "neg": qwen.NEG_PORTRAIT + ", printed font, typed text, extra characters, english",
     "prompt": "Extreme close-up of the bottom of a curling 1991 thermal fax page with faint grey Chinese handwriting lines too small to read; "
               "at the bottom, four large handwritten Chinese characters in blue ballpoint pen, clear and correct: 「见路不走」. "
               "A man's fingers hold the page edge. Warm dim light. " + S},
    {"id": "k8g_s", "ref": REF / "戴梦岩_戏服.png", "seed": 7818,  # v2：v1 风衣敞开露腿
     "neg": NEG + ", bare legs, thighs, shorts, skirt, open coat",
     "prompt": DAI + "Full shot " + STUDIO + ". Her long white trench coat is fully buttoned and belted, closed down to her shins. "
               "She has just landed from the wires, knees buckling, exhausted and drenched in sweat, two crew "
               "members in T-shirts grabbing her arms to hold her up, harness still on. " + S},
    {"id": "k8g_e", "ref_still_id": "k8g_s", "seed": 7809,
     "prompt": "STRICTLY KEEP the exact same woman, buttoned long white trench coat, two crew members and studio. Now the three walk closer toward camera, she is "
               "half carried, panting, head lowered, one hand lifting to point toward the far corner. " + S},
    {"id": "k8h_s", "ref": REF / "戴梦岩_戏服.png", "seed": 7820,  # v2：v1 已坐下
     "neg": NEG + ", sitting, seated, sitting on chair",
     "prompt": DAI + "Medium full shot " + CORNER + ". She is STANDING upright on her feet next to an EMPTY folding canvas chair (not "
               "seated yet), one hand resting on the chair's backrest, exhausted and sweaty, panting. " + S},
    {"id": "k8h_e", "ref_still_id": "k8h_s", "seed": 7811,
     "prompt": "STRICTLY KEEP the exact same woman, costume, chair and corner. Now she is seated in the folding chair, slumped back, "
               "holding a white tissue near her sweaty forehead. " + S},
    {"id": "k8i", "ref": VID / "ep01_p3" / "ref_tmp" / "comp_liang_dai.png", "seed": 7812,
     "prompt": "Use the two people from the reference image (keep both faces and clothes exactly): medium two-shot " + CORNER + ". The "
               "woman in the white trench coat sits sweaty in a folding chair; the man in the charcoal suit and gold-rimmed glasses stands "
               "beside her handing her three sheets of thermal fax paper, serious. " + S},
    {"id": "k_liang_studio", "ref": REF / "梁士乔.png", "seed": 7813,
     "prompt": LIANG + "Close-up " + CORNER + ". Seated on a wooden crate, faint sweat at his temple in the heat, thoughtful shrewd eyes, "
               "mouth closed. " + S},
    {"id": "k_dai_studio", "ref": REF / "戴梦岩_戏服.png", "seed": 7814,
     "prompt": DAI + "Close-up " + CORNER + ". Seated, sweat-damp hair at her temples, she reads three sheets of thermal fax paper held in "
               "both hands, brows slightly drawn, mouth closed. " + S},
    {"id": "k8l_e", "ref_still_id": "k_dai_studio", "seed": 7815,
     "prompt": "STRICTLY KEEP the exact same woman, costume, sweat and corner, same framing. Now she has snapped the fax pages shut against "
               "her lap with one hand, chin lifted, a cold disdainful look. " + S},
    {"id": "k8p", "ref": REF / "戴梦岩_戏服.png", "seed": 7816,
     "prompt": DAI + "Low-angle close-up in the hot 1991 film soundstage: seated, sweaty, she tilts her head back gazing up at the "
               "blinding tungsten spotlights in the rig above, eyes suddenly lost and uncertain. " + S},
]
for k in KEYFRAMES:
    k.setdefault("neg", NEG)


def main():
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 1
    kfs = KEYFRAMES
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
        kfs = [k for k in KEYFRAMES if k["id"] in only]
    qwen.composite([REF / "阿英.png", REF / "梁士乔.png"], HERE / "ref_tmp" / "comp_aying_liang.png")
    qwen.composite([REF / "梁士乔.png", REF / "戴梦岩_戏服.png"], HERE / "ref_tmp" / "comp_liang_dai.png")
    todo = [k for k in kfs if not (STILLS / f"{k['id']}.png").exists()]
    if not todo:
        print("[skip] 关键帧都已存在")
        return
    with ColabPool(n=n, setup=qwen.setup, seg="p3", stage="keyframes") as pool:
        r = qwen.run_keyframes(pool, todo, STILLS)
    print(f"[keyframes] 完成 {len(r['done'])}，失败 {r['failed'] or '无'}")


if __name__ == "__main__":
    main()
