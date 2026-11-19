#!/usr/bin/env python3
"""ep01 p3 定妆候选：梁士乔 / 戴梦岩（戏服 + 中性）/ 韩平 / 阿英，每组 3 个种子。
设定依据：原著第二章 + 剧本 1-7/1-8（见 分镜表.md）。产物 → ref_candidates/，xiying 选定后拷到 视频/ref/。
用法：uv run -q --with pillow python stageB1_char_refs_p3.py [--n 1]
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
import qwen  # noqa: E402
from colab_pool import ColabPool  # noqa: E402

OUT = HERE / "ref_candidates"
NEUTRAL = ", calm neutral expression, mouth closed relaxed, looking slightly off camera"
NEG = qwen.NEG_PORTRAIT + ", broad smile, grin, laughing, modern hairstyle, 2020s fashion"

GROUPS = {
    "梁士乔": (7101, "Medium close-up 1991 cinema portrait of a refined, shrewd Hong Kong Chinese talent-agency general manager in his early "
             "forties, neatly combed short dark hair, elegant thin gold-rimmed designer eyeglasses, impeccably tailored charcoal double-breasted "
             "suit, white shirt, muted silk tie, black leather business shoulder bag strap across his shoulder, cultured yet calculating demeanor, "
             "standing in a bright 1991 Beijing airport departure hall softly out of focus behind him" + NEUTRAL + ". "),
    "戴梦岩_戏服": (7201, "Medium close-up 1991 cinema portrait of a strikingly beautiful 28-year-old Hong Kong Chinese film star in costume for a "
                 "wuxia-style urban heroine role: long flowing black hair, heavy glamorous film makeup with cool sharp eyeliner, wearing a long "
                 "white late-autumn trench coat, standing in a hot hazy 1991 Beijing film studio corridor with set lights behind her, cold aloof "
                 "star aura" + NEUTRAL + ". "),
    "戴梦岩_中性": (7301, "Medium close-up 1991 cinema portrait of a strikingly beautiful 28-year-old Hong Kong Chinese film star off duty: long "
                 "straight black hair, light natural makeup, simple cream silk blouse, clean soft daylight, plain softly blurred interior "
                 "background, intelligent, proud, composed" + NEUTRAL + ". "),
    "韩平": (7401, "Medium close-up 1991 cinema portrait of an ordinary young Beijing man in his mid twenties working as a film-crew car driver, "
           "short practical haircut, short-sleeved pale blue cotton shirt, a black plastic pager clipped on his belt, a document folder tucked "
           "under his arm and car keys in his hand, honest quick-witted face, 1991 Beijing airport departure hall softly blurred behind" + NEUTRAL + ". "),
    "阿英": (7501, "Medium close-up 1991 cinema portrait of a capable 27-year-old Hong Kong Chinese personal assistant, shoulder-length hair tied "
           "back, modest light-grey office blouse and slacks, slightly red nose and tired eyes from a summer cold, holding a sealed brown kraft "
           "paper envelope against her chest, outside a 1991 Beijing film studio gate in hot summer daylight" + NEUTRAL + ". "),
}


def jobs():
    out = []
    for name, (seed0, prompt) in GROUPS.items():
        for k in range(3):
            out.append({"out": OUT / f"{name}_s{k + 1}.png", "mode": "t2i", "seed": seed0 + k,
                        "prompt": prompt + qwen.STYLE, "neg": NEG})
    return out


def contact_sheet():
    """每行一组、3 列种子，便于选（PIL；本机 ffmpeg 没有 drawtext）。"""
    from PIL import Image, ImageDraw, ImageFont
    rows = [(lab, [OUT / f"{name}_s{k}.png" for k in (1, 2, 3)]) for name, lab in zip(GROUPS, GROUPS_LABEL)]
    rows = [(lab, ims) for lab, ims in rows if all(p.exists() for p in ims)]
    if not rows:
        return None
    W, H = 640, 360
    sheet = Image.new("RGB", (W * 3, H * len(rows)), "black")
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 26)
    except Exception:
        font = ImageFont.load_default()
    for r, (lab, ims) in enumerate(rows):
        for c, pth in enumerate(ims):
            sheet.paste(Image.open(pth).convert("RGB").resize((W, H)), (c * W, r * H))
            d.rectangle([c * W, r * H, c * W + 300, r * H + 36], fill="black")
            d.text((c * W + 8, r * H + 4), f"{lab} s{c + 1}", fill="yellow", font=font)
    out = OUT / "contact_sheet.png"
    sheet.save(out)
    return out


GROUPS_LABEL = ["LiangShiqiao", "DaiMengyan-costume", "DaiMengyan-neutral", "HanPing", "AYing"]


def main():
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 1
    todo = [j for j in jobs() if not (j["out"].exists() and j["out"].stat().st_size > 20_000)]
    if todo:
        with ColabPool(n=n, setup=qwen.setup, seg="p3", stage="char_refs") as pool:
            _, failed = pool.run(todo, qwen.render_job, key=lambda j: j["out"].name)
            if failed:
                print("[失败]", failed, flush=True)
    else:
        print("[skip] 候选都已存在")
    print("[contact sheet]", contact_sheet())


if __name__ == "__main__":
    main()
