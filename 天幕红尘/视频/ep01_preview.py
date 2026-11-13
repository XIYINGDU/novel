# -*- coding: utf-8 -*-
"""《天幕红尘》第01集 试片（1-1 至 1-10）—— 在 Colab GPU 上运行。

用法（在 Colab VM 上）：
    python ep01_preview.py all        # 依次跑 tts → video → assemble
    python ep01_preview.py tts|video|assemble

依据：天幕红尘/剧本/第01集.md 场 1-1 至 1-10（已审定稿）。
产物：/content/ep1/out/第01集_试片.mp4
"""
import os, sys, json, time, math, random, subprocess, asyncio, urllib.request
from pathlib import Path

ROOT = Path("/content/ep1")
CLIP, AUD, STILL, SHOT, OUT, FONT = [ROOT / d for d in ("clips", "audio", "stills", "shots", "out", "fonts")]
for d in (CLIP, AUD, STILL, SHOT, OUT, FONT):
    d.mkdir(parents=True, exist_ok=True)
LOG = ROOT / "progress.log"
W, H, FPS = 1280, 720, 24

def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")

# ----------------------------------------------------------------------------
# 人物与风格
# ----------------------------------------------------------------------------
STYLE = (", 1991, cinematic 35mm film still, realistic, natural skin texture, shallow depth of field, "
         "film grain, moody low-key lighting, muted colors")
LUO = "a 42-year-old Chinese businessman with short black hair, loosened tie, sweat-stained white dress shirt"
SU = "a 70-year-old Chinese grandmother with grey hair in a bun, reading glasses, beige cardigan"
LIN = "a 38-year-old Chinese woman with shoulder-length black hair, plain dark blouse"
HUI = "a 35-year-old Chinese woman with a ponytail, light sweater"
KUG = "a chubby 40-year-old Russian man with brown hair in a wrinkled brown suit"
MOSCOW = "dim 1991 Moscow office at midnight, single warm desk lamp, cold blue light from window"
NY = "bright 1991 New York apartment, afternoon sunlight through windows"
NEG = ("色调艳丽，过曝，静态，细节模糊不清，字幕，文字，字母，水印，风格，作品，画作，画面，静止，整体发灰，"
       "最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，"
       "毁容的，形态畸形的肢体，手指融合，杂乱的背景，三条腿，背景人很多，倒着走，cartoon, anime, smartphone, modern")

# ----------------------------------------------------------------------------
# 声音：edge-tts 角色表（voice, rate, pitch）
# ----------------------------------------------------------------------------
VOICES = {
    "叶子农": ("zh-CN-YunjianNeural", "-18%", "-12Hz"),
    "罗家明": ("zh-CN-YunyangNeural", "-8%", "-6Hz"),
    "库格列夫": ("zh-CN-YunjianNeural", "+12%", "+4Hz"),
    "库格列夫RU": ("ru-RU-DmitryNeural", "+0%", "+0Hz"),
    "苏玉平": ("zh-TW-HsiaoChenNeural", "-18%", "-18Hz"),
    "林雪红": ("zh-CN-XiaoxiaoNeural", "-4%", "-6Hz"),
    "罗慧娟": ("zh-CN-XiaoyiNeural", "+6%", "+0Hz"),
    "医生": ("en-US-GuyNeural", "-6%", "-4Hz"),
    "电视": ("ru-RU-DmitryNeural", "-6%", "-8Hz"),
}
TV_TEXT = ("Я прекращаю свою деятельность на посту Президента СССР. "
           "Центральный комитет КПСС принял решение о самороспуске. "
           "Мы живём в новом мире.")

# ----------------------------------------------------------------------------
# 镜头表。kind: t2v（文生视频）| still（模型背景帧 + 合成文字道具）| card（黑底字幕卡）
# events: ("line", 角色, 台词, {phone, sub}) | ("sfx", 名称) | ("gap", 秒)
# ----------------------------------------------------------------------------
SHOTS = [
    # 1-1 冷开场：巴黎餐厅台阶，夜
    dict(id="01", scene="1-1", kind="t2v", amb="street", min=4.0,
         prompt="Night in Paris, elegant classical French restaurant entrance with four stone steps, warm door light, "
                "a man in a white crewneck sports hoodie and sneakers walks down the steps, shot from behind at waist "
                "height, face never visible" + STYLE,
         events=[("gap", 1.0), ("sfx", "lighter")]),
    dict(id="02", scene="1-1", kind="t2v", amb="street", min=3.5,
         prompt="Extreme close-up at night, a man's hand pulls a steel flip lighter out of a white hoodie pocket and "
                "flicks the lid open with his thumb, small flame, street lights bokeh" + STYLE,
         events=[("gap", 1.2), ("sfx", "thump"), ("gap", 1.0)]),
    dict(id="03", scene="1-1", kind="t2v", amb="street", min=4.5,
         prompt="Close-up of the chest of a man in a white sports hoodie at night, a red blood stain spreading fast on "
                "the white fabric, his hand pressing the chest, face out of frame" + STYLE,
         events=[("sfx", "thump"), ("gap", 0.8),
                 ("line", "叶子农", "还真他妈抬举我。", {}), ("gap", 0.6), ("sfx", "fall"), ("gap", 1.2)]),
    dict(id="04", scene="1-1", kind="card", text=["一年前", "1991年8月24日　莫斯科"], min=4.0, events=[]),

    # 1-2 莫斯科大街
    dict(id="05", scene="1-2", kind="t2v", amb="night_city", min=4.5,
         prompt="Deserted Moscow boulevard at midnight in August 1991, wet asphalt, closed shops with metal shutters, "
                "an old Soviet police Volga car with flashing blue light speeds past, a dark office tower with one lit "
                "window high up" + STYLE,
         events=[("sfx", "siren"), ("gap", 2.5)]),
    dict(id="06", scene="1-2", kind="t2v", amb="night_city", min=4.0,
         prompt=KUG + " pounding with his fist on a locked glass entrance door of an office building at night, an old "
                "Russian security guard behind the glass shakes his head and pulls down a blind" + STYLE,
         events=[("line", "库格列夫RU", "Пустите меня наверх! На двенадцатом свет горит! Господин Ло ещё там!",
                  {"sub": "让我上去！12楼灯还亮着！罗先生还在上面！"}), ("gap", 0.8)]),

    # 1-3 外间办公区
    dict(id="07", scene="1-3", kind="t2v", amb="room", min=4.5,
         prompt=LUO + " crouching in a dark open-plan office, burning documents in a metal bin, firelight flickering on "
                "his face, papers scattered on the floor, green exit sign glow" + STYLE,
         events=[("gap", 2.0), ("sfx", "phone_ru"), ("gap", 0.5)]),

    # 1-4 库格列夫的电话
    dict(id="08", scene="1-4", kind="t2v", amb="room", tv=True, min=3.5,
         prompt=MOSCOW + ", an old boxy CRT television in the corner showing a grey-haired Soviet politician giving a "
                "speech, a black rotary telephone ringing on a wooden desk, a man's hand picks up the receiver" + STYLE,
         events=[("line", "罗家明", "喂，我是罗。", {}),
                 ("line", "库格列夫", "罗！你为什么锁门？你知不知道今天下午五点，石油部伊万诺夫副部长被逮捕了？！加上前天进去的两个，你们公司秘密股东协议里的五个权力股高官，已经进去了三个！", {"phone": True})]),
    dict(id="09", scene="1-4", kind="t2v", amb="room", tv=True, min=3.5,
         prompt="Close-up of " + LUO + " holding a telephone receiver to his ear, an unlit cigarette between his lips, "
                "lit from below by a desk lamp, sweat on his forehead, " + MOSCOW + STYLE,
         events=[("line", "罗家明", "库格列夫，你冷静点。8·19动荡已经平息了，我们的150口油井是有正式批文的——", {}),
                 ("line", "库格列夫", "什么正式批文！你用超低价拿下那150口油井开采权，靠的全是高官权力背景，连根钻管都没打，就指望转手卖给美国石油公司牟取暴利！现在苏共解散了，经济重新洗牌，检察院的查封令和传票明天一早就贴你门上！美国人两小时前已经正式撤回收购了！", {"phone": True})]),
    dict(id="10", scene="1-4", kind="t2v", amb="room", tv=True, min=3.5,
         prompt="Extreme close-up, a cigarette falls from a man's trembling lips onto a wooden desk next to a black "
                "rotary phone, desk lamp light, " + MOSCOW + STYLE,
         events=[("sfx", "tap"),
                 ("line", "库格列夫", "那两个高官公子傍晚已经跑去瑞士了！500多万美元融资全完了！我那6万美元私人借款原本是口头暗股，11月10号到期，你什么时候还我？！", {"phone": True}),
                 ("line", "罗家明", "6万美元少不了你的。明天上午十点你到公司来，我当面给你开票。", {}),
                 ("sfx", "hook"), ("gap", 0.8)]),

    # 1-5 账册、窗前、「这个笨蛋」
    dict(id="11", scene="1-5", kind="still", amb="room", tv=True, min=7.0, overlay="ledger",
         prompt="Top-down close-up of an open black leather ledger book with blank cream pages on a wooden desk under "
                "a warm desk lamp, a fountain pen beside it, dark office at night" + STYLE,
         events=[("sfx", "clock"), ("gap", 6.0)]),
    dict(id="12", scene="1-5", kind="t2v", amb="night_city", tv=True, min=4.0,
         prompt=LUO + " standing at a 12th-floor office window at night seen from behind, smoking, flicking cigarette "
                "ash out of the window, Moscow street lights far below, cold blue night" + STYLE,
         events=[("gap", 2.0), ("line", "罗家明", "这个笨蛋！", {}), ("gap", 0.6), ("sfx", "tv_off")]),

    # 1-6 同一时刻，纽约
    dict(id="13", scene="1-6", kind="t2v", amb="day_room", min=4.0, caption="同一时刻　纽约",
         prompt=SU + " sitting at a dining table, looking at an elegant gold-embossed invitation card, a pill box and a "
                "glass of water on the table, " + NY + STYLE,
         events=[("gap", 2.5)]),
    dict(id="14", scene="1-6", kind="t2v", amb="day_room", min=3.5,
         prompt=LIN + " and " + HUI + " whispering anxiously by a kitchen doorway, the woman with shoulder-length hair "
                "quickly hides a red bank letter into her handbag, " + NY + STYLE,
         events=[("line", "罗慧娟", "嫂子，莫斯科那边两天打不通哥的电话，银行上午又去裕香阁查账了，万一11月10号前油井的钱回不来，咱在纽约连落脚地儿都没了——", {}),
                 ("line", "林雪红", "小声点！妈的心脏什么样你不知道？北京房子卖了、裕香阁抵押贷款、还有借梦岩那30万本金，半个字都不许漏到妈耳朵里！", {})]),
    dict(id="15", scene="1-6", kind="t2v", amb="day_room", min=3.5,
         prompt=SU + " taking off her reading glasses and smiling warmly, beckoning with her hand, " + LIN +
                " walks over and hands her pills, " + NY + STYLE,
         events=[("line", "苏玉平", "雪红，你们看，梦岩人在北京拍戏，还托人把圣西蒙电影节的请柬寄来给我看。这次她提名最佳女主角，拿奖十拿九稳。", {}),
                 ("line", "林雪红", "妈，您教出来的学生哪有不争气的。先把药吃了。", {}),
                 ("gap", 0.6), ("sfx", "phone_us"), ("gap", 0.4)]),

    # 1-7 诀别电话
    dict(id="16", scene="1-7", kind="t2v", amb="day_room", min=3.0,
         prompt=SU + " picking up a beige telephone receiver in a sunny living room, smiling, " + NY + STYLE,
         events=[("line", "苏玉平", "喂？是家明吗？吃了没有？", {})]),
    dict(id="17", scene="1-7", kind="t2v", amb="room", min=3.5,
         prompt="Close-up of " + LUO + " on the phone in a dark office, eyes turning red, quickly wiping his eyes with "
                "his shirt sleeve, " + MOSCOW + STYLE,
         events=[("gap", 0.5), ("line", "罗家明", "……吃了，妈。我就是……想听听您声音。", {})]),
    dict(id="18", scene="1-7", kind="t2v", amb="day_room", min=3.5,
         prompt="Close-up of " + SU + " talking on a beige telephone happily, sunlight on her face, " + NY + STYLE,
         events=[("line", "苏玉平", "你这孩子，深更半夜还不睡。你那边乱不乱？电视上天天放莫斯科开坦克，可把妈吓坏了——", {"phone_for": "罗家明"})]),
    dict(id="19", scene="1-7", kind="t2v", amb="room", min=3.5,
         prompt="Close-up of " + LUO + " holding a telephone receiver, staring down at an open ledger book on the desk, "
                "his voice trembling, " + MOSCOW + STYLE,
         events=[("line", "罗家明", "不乱，都挺好。油井的合同顺着呢。", {}),
                 ("line", "苏玉平", "那就好！对了，梦岩借给咱周转的那30万美金，等你款子一到，头一桩就得连本带利还人家。妈这辈子教书，最怕欠学生人情。", {"phone": True})]),
    dict(id="20", scene="1-7", kind="t2v", amb="room", min=4.0,
         prompt="Extreme close-up of a man's hand gripping a black telephone receiver, shaking violently, veins on his "
                "forehead, his lips move silently, " + MOSCOW + STYLE,
         events=[("gap", 1.5), ("line", "罗家明", "我记着呢，妈……您心脏不好，往后不管遇到什么事，按时吃药……", {})]),
    dict(id="21", scene="1-7", kind="t2v", amb="day_room", min=3.0,
         prompt=LIN + " quickly takes the telephone receiver from an old woman, worried frown, " + NY + STYLE,
         events=[("line", "林雪红", "家明？你声音怎么不对劲？莫斯科到底怎么样了？银行今天又来催——", {"phone_for": "罗家明"})]),
    dict(id="22", scene="1-7", kind="t2v", amb="room", min=4.0,
         prompt=LUO + " slamming the telephone receiver down hard, then covering his mouth with his whole hand, tears, "
                "standing at the desk, " + MOSCOW + STYLE,
         events=[("line", "罗家明", "雪红，照顾好妈和孩子！", {}), ("sfx", "slam"), ("gap", 2.0)]),
    dict(id="23", scene="1-7", kind="t2v", amb="day_room", min=4.0,
         prompt=LIN + " holding a telephone receiver to her ear, then dialing again on a beige push-button phone, "
                "tense face, " + NY + STYLE,
         events=[("sfx", "busy"), ("sfx", "ringback"),
                 ("line", "苏玉平", "怎么了？", {}), ("gap", 0.4),
                 ("line", "林雪红", "线路不好，断了。", {}), ("gap", 0.8)]),

    # 1-8 遗书、横幅、枪声
    dict(id="24", scene="1-8", kind="t2v", amb="room", min=4.5,
         prompt="Close-up of a man's hands opening a red velvet gift box containing an old WWII revolver and bullets on "
                "a wooden desk, loading one bullet into the cylinder, desk lamp light, " + MOSCOW + STYLE,
         events=[("gap", 1.5), ("sfx", "cylinder"), ("gap", 1.0)]),
    dict(id="25", scene="1-8", kind="still", amb="room", min=6.5, overlay="note",
         prompt="Top-down close-up of a blank sheet of white letter paper on a wooden desk under a warm desk lamp, a "
                "fountain pen beside it, a black rotary telephone at the edge" + STYLE,
         events=[("sfx", "pen"), ("gap", 5.0)]),
    dict(id="26", scene="1-8", kind="still", amb="room", min=9.0, overlay="banner",
         prompt="An empty dark office wall with old wooden paneling, lit by a warm desk lamp from below, deep shadows, "
                "static shot, nothing on the wall" + STYLE,
         events=[("gap", 1.5), ("line", "罗家明", "见路不走……可我现在能见到的只有一条死路，不走也得走了……", {"whisper": True}),
                 ("gap", 1.6), ("sfx", "gunshot"), ("gap", 2.0)]),
    dict(id="27", scene="1-8", kind="t2v", amb="silence", min=4.5,
         prompt="Close-up of dark red blood dripping slowly from the edge of a wooden desk onto the floor, a desk lamp "
                "still on, a white letter paper resting on a black telephone, silent dark office" + STYLE,
         events=[("sfx", "drip"), ("gap", 3.0)]),

    # 1-9 次日，纽约
    dict(id="28", scene="1-9", kind="card", text=["次日", "1991年8月25日　纽约"], min=3.5, events=[]),
    dict(id="29", scene="1-9", kind="t2v", amb="day_room", min=3.5,
         prompt=HUI + " answering a beige telephone in a New York living room in the morning, her face goes pale, she "
                "drops the receiver and collapses onto the floor screaming, " + NY + STYLE,
         events=[("sfx", "phone_us"), ("line", "库格列夫", "罗死了！昨晚在办公室开枪自杀了！", {"phone": True}),
                 ("line", "罗慧娟", "哥——！！", {"shout": True})]),
    dict(id="30", scene="1-9", kind="t2v", amb="day_room", min=3.5,
         prompt=LIN + " rushing out of the kitchen and grabbing a fallen telephone receiver, shouting into it, " + NY + STYLE,
         events=[("line", "林雪红", "库格列夫！你说清楚！家明怎么了？！", {"shout": True}),
                 ("line", "库格列夫", "他破产了！昨晚在12楼办公室开枪自杀了！人已经没了！", {"phone": True})]),
    dict(id="31", scene="1-9", kind="t2v", amb="day_room", min=4.0,
         prompt=SU + " clutching her chest in shock, lips turning purple, falling backwards and knocking over a cup of "
                "hot tea from a coffee table, " + NY + STYLE,
         events=[("sfx", "crash"), ("gap", 0.3),
                 ("line", "林雪红", "妈——！慧娟！快拿硝酸甘油！叫救护车！！", {"shout": True}), ("gap", 0.6)]),

    # 1-10 医院走廊
    dict(id="32", scene="1-10", kind="t2v", amb="hospital", min=4.0,
         prompt="A dim New York hospital corridor at night in 1991, a red emergency room light turns off, an American "
                "doctor in scrubs walks out, takes off his mask and slowly shakes his head at two Chinese women" + STYLE,
         events=[("line", "医生", "I'm sorry. It was a massive myocardial infarction. We did everything we could.",
                  {"sub": "很抱歉。是大面积心肌梗死。我们尽力了。"}), ("gap", 0.5)]),
    dict(id="33", scene="1-10", kind="t2v", amb="hospital", min=3.5,
         prompt=HUI + " sliding down a hospital corridor wall to the floor, holding her head and sobbing, night" + STYLE,
         events=[("line", "罗慧娟", "全没了……一天工夫，哥没了，妈也没了！还欠着一百多万美金的债，咱们往后怎么活啊？！", {})]),
    dict(id="34", scene="1-10", kind="t2v", amb="hospital", min=4.0,
         prompt=LIN + " standing in a hospital corridor at night, closing her eyes, breathing hard, then opening them "
                "with a hard determined look and pulling another woman up from the floor" + STYLE,
         events=[("gap", 1.5),
                 ("line", "林雪红", "别哭了！哭要是能把银行那45万哭没了，我现在陪你哭！听着，妈的葬礼定在28号，从现在起对外一律封锁消息！你今晚就飞莫斯科，跟库格列夫把你哥的后事办了，把墙上那幅字和遗书带回来！纽约这边交给我！", {}),
                 ("gap", 1.5)]),
    dict(id="35", scene="end", kind="card", text=["《天幕红尘》第01集　试片", "1-1 至 1-10"], min=4.0, events=[]),
]

# ----------------------------------------------------------------------------
# 字体
# ----------------------------------------------------------------------------
FONT_URLS = {
    "brush": "https://raw.githubusercontent.com/google/fonts/main/ofl/mashanzheng/MaShanZheng-Regular.ttf",
    "hand": "https://raw.githubusercontent.com/google/fonts/main/ofl/longcang/LongCang-Regular.ttf",
}
SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"

def font(kind, size):
    from PIL import ImageFont
    if kind in FONT_URLS:
        p = FONT / (kind + ".ttf")
        if not p.exists():
            try:
                urllib.request.urlretrieve(FONT_URLS[kind], p)
            except Exception as e:
                log(f"font {kind} download failed: {e}")
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.truetype(SERIF if kind == "serif" else SANS, size)

# ----------------------------------------------------------------------------
# Stage 1: TTS + 音效 → 每个镜头的音轨与字幕时间
# ----------------------------------------------------------------------------
def synth_sfx(name):
    import numpy as np
    from pydub import AudioSegment
    sr = 44100
    def seg(x):
        x = np.clip(x, -1, 1)
        return AudioSegment((x * 32767).astype(np.int16).tobytes(), frame_rate=sr, sample_width=2, channels=1)
    t = lambda d: np.arange(int(sr * d)) / sr
    rng = np.random.default_rng(7)
    if name == "gunshot":
        tt = t(1.6); x = rng.normal(0, 1, tt.size) * np.exp(-tt * 9) + 0.9 * np.sin(2 * np.pi * 55 * tt) * np.exp(-tt * 5)
        return seg(x * 0.95)
    if name == "thump":   # 远处狙击：闷响
        tt = t(0.7); x = 0.8 * np.sin(2 * np.pi * 60 * tt) * np.exp(-tt * 10) + 0.25 * rng.normal(0, 1, tt.size) * np.exp(-tt * 25)
        return seg(x)
    if name == "fall":
        tt = t(0.6); return seg(0.6 * np.sin(2 * np.pi * 80 * tt) * np.exp(-tt * 12) + 0.2 * rng.normal(0, 1, tt.size) * np.exp(-tt * 18))
    if name == "lighter":
        tt = t(0.25); return seg(0.5 * rng.normal(0, 1, tt.size) * np.exp(-tt * 60))
    if name in ("phone_ru", "phone_us"):
        tt = t(1.2); f = 25 if name == "phone_ru" else 20
        ring = 0.35 * (np.sin(2 * np.pi * 440 * tt) + np.sin(2 * np.pi * 480 * tt)) * (np.sign(np.sin(2 * np.pi * f * tt)) > 0)
        gap = np.zeros(int(sr * 0.6))
        return seg(np.concatenate([ring, gap, ring]))
    if name == "busy":
        tt = t(0.5); b = 0.25 * (np.sin(2 * np.pi * 480 * tt) + np.sin(2 * np.pi * 620 * tt))
        z = np.zeros(int(sr * 0.5)); return seg(np.concatenate([b, z, b, z]))
    if name == "ringback":
        tt = t(1.0); b = 0.2 * (np.sin(2 * np.pi * 440 * tt) + np.sin(2 * np.pi * 480 * tt))
        z = np.zeros(int(sr * 1.5)); return seg(np.concatenate([b, z, b, z]))
    if name == "siren":
        tt = t(3.0); f = 650 + 250 * np.sin(2 * np.pi * 0.8 * tt)
        x = 0.25 * np.sin(2 * np.pi * np.cumsum(f) / sr) * np.minimum(1, tt / 0.8) * np.minimum(1, (3 - tt) / 1.5)
        return seg(x)
    if name in ("hook", "slam", "tap", "tv_off", "cylinder", "crash"):
        d = {"hook": 0.15, "slam": 0.4, "tap": 0.1, "tv_off": 0.3, "cylinder": 0.5, "crash": 0.8}[name]
        tt = t(d); amp = {"slam": 0.9, "crash": 0.8}.get(name, 0.4)
        x = amp * rng.normal(0, 1, tt.size) * np.exp(-tt * (30 if name != "crash" else 8))
        if name == "cylinder":
            for k in range(4):
                i = int(sr * 0.11 * k); x[i:i + 400] += 0.6 * rng.normal(0, 1, 400)
        return seg(x)
    if name == "clock":
        out = np.zeros(int(sr * 6))
        for k in range(6):
            i = int(sr * k); out[i:i + 300] = 0.35 * rng.normal(0, 1, 300)
        return seg(out)
    if name == "pen":
        tt = t(2.5); return seg(0.08 * rng.normal(0, 1, tt.size) * (np.sin(2 * np.pi * 3 * tt) > 0))
    if name == "drip":
        out = np.zeros(int(sr * 3))
        for k in range(3):
            i = int(sr * k); tt = t(0.12); out[i:i + tt.size] = 0.4 * np.sin(2 * np.pi * (900 - 3000 * tt) * tt) * np.exp(-tt * 40)
        return seg(out)
    raise ValueError(name)

def ambience(kind, ms):
    import numpy as np
    from pydub import AudioSegment
    sr = 44100; n = int(sr * ms / 1000)
    rng = np.random.default_rng(hash(kind) % 1000)
    if kind == "silence":
        x = np.zeros(n)
    else:
        lvl = {"street": 0.05, "night_city": 0.04, "room": 0.015, "day_room": 0.02, "hospital": 0.02}.get(kind, 0.02)
        x = np.cumsum(rng.normal(0, 1, n)); x = x - np.convolve(x, np.ones(2000) / 2000, mode="same")
        x = x / (np.abs(x).max() + 1e-9) * lvl
        if kind in ("room", "hospital"):
            tt = np.arange(n) / sr; x += 0.01 * np.sin(2 * np.pi * 50 * tt)
    return AudioSegment((x * 32767).astype(np.int16).tobytes(), frame_rate=sr, sample_width=2, channels=1)

def stage_tts():
    import nest_asyncio, edge_tts
    from pydub import AudioSegment
    nest_asyncio.apply()

    async def say(text, who, path, plain=False):
        v, r, p = VOICES[who]
        if plain: r, p = "+0%", "+0Hz"
        await edge_tts.Communicate(text, v, rate=r, pitch=p).save(str(path))

    tv_path = AUD / "tv_bed.mp3"
    if not tv_path.exists():
        asyncio.get_event_loop().run_until_complete(say(TV_TEXT, "电视", tv_path))
    tv = AudioSegment.from_file(tv_path).high_pass_filter(400).low_pass_filter(3000) - 20

    meta = {}
    for s in SHOTS:
        track = AudioSegment.silent(0, frame_rate=44100)
        subs = []
        for k, ev in enumerate(s["events"]):
            if ev[0] == "gap":
                track += AudioSegment.silent(int(ev[1] * 1000), frame_rate=44100)
            elif ev[0] == "sfx":
                track += synth_sfx(ev[1]).set_frame_rate(44100)
            elif ev[0] == "line":
                _, who, text, opt = ev
                p = AUD / f"{s['id']}_{k}.mp3"
                if not p.exists() or p.stat().st_size < 1000:
                    for attempt in range(5):
                        try:
                            asyncio.get_event_loop().run_until_complete(say(text, who, p, plain=attempt >= 2))
                            if p.stat().st_size > 1000: break
                            raise RuntimeError("empty audio")
                        except Exception as e:
                            p.unlink(missing_ok=True)
                            log(f"tts retry {s['id']}_{k}: {e}"); time.sleep(3)
                a = AudioSegment.from_file(p).set_frame_rate(44100).set_channels(1)
                if opt.get("phone"):
                    a = a.high_pass_filter(350).low_pass_filter(3200) - 3
                if opt.get("whisper"):
                    a = a - 6
                if opt.get("shout"):
                    a = a + 3
                start = len(track)
                track += a + AudioSegment.silent(250, frame_rate=44100)
                subs.append((start / 1000, (start + len(a)) / 1000, opt.get("sub", text)))
        dur = max(s["min"], len(track) / 1000 + 0.3)
        track = track + AudioSegment.silent(int(dur * 1000) - len(track), frame_rate=44100)
        bed = ambience(s.get("amb", "silence"), len(track))
        if s.get("tv"):
            loops = tv * (int(len(track) / max(1, len(tv))) + 1)
            bed = bed.overlay(loops[:len(track)])
        track = bed.overlay(track)
        track.export(AUD / f"shot_{s['id']}.wav", format="wav")
        meta[s["id"]] = {"dur": dur, "subs": subs}
        log(f"tts shot {s['id']} dur={dur:.1f}s lines={len(subs)}")
    (ROOT / "audio_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))

# ----------------------------------------------------------------------------
# Stage 2: 视频生成（Wan2.2-TI2V-5B，失败回退 Wan2.1-T2V-1.3B）
# ----------------------------------------------------------------------------
def stage_video():
    import torch
    from diffusers import WanPipeline, AutoencoderKLWan
    from diffusers.utils import export_to_video
    cands = [("Wan-AI/Wan2.2-TI2V-5B-Diffusers", 704, 1280, 121, 24, 5.0, 40),
             ("Wan-AI/Wan2.1-T2V-1.3B-Diffusers", 480, 832, 81, 16, 5.0, 40)]
    pipe = None
    for mid, h, w, nf, fps, cfg, steps in cands:
        try:
            log(f"loading {mid}")
            vae = AutoencoderKLWan.from_pretrained(mid, subfolder="vae", torch_dtype=torch.float32)
            pipe = WanPipeline.from_pretrained(mid, vae=vae, torch_dtype=torch.bfloat16)
            pipe.enable_model_cpu_offload()
            try: pipe.vae.enable_tiling()
            except Exception: pass
            break
        except Exception as e:
            log(f"load failed {mid}: {e}")
    assert pipe is not None, "no video model"
    log(f"model ready: {mid} {w}x{h} frames={nf}")
    todo = [s for s in SHOTS if s["kind"] in ("t2v", "still")]
    for i, s in enumerate(todo):
        p = CLIP / f"clip_{s['id']}.mp4"
        if p.exists():
            continue
        t0 = time.time()
        g = torch.Generator("cuda").manual_seed(1991 + int(s["id"]))
        frames = pipe(prompt=s["prompt"], negative_prompt=NEG, height=h, width=w,
                      num_frames=nf if s["kind"] == "t2v" else 21,
                      guidance_scale=cfg, num_inference_steps=steps, generator=g).frames[0]
        export_to_video(frames, str(p), fps=fps)
        log(f"clip {s['id']} ({i + 1}/{len(todo)}) {time.time() - t0:.0f}s")
    log("video stage done")

# ----------------------------------------------------------------------------
# Stage 3: 合成（道具文字、字幕卡、循环/延时、字幕、混音）
# ----------------------------------------------------------------------------
def read_frames(path):
    import imageio.v3 as iio
    return [f for f in iio.imiter(str(path))]

def fit(img):
    from PIL import Image
    return img.convert("RGB").resize((W, H), Image.LANCZOS)

def overlay_prop(img, kind):
    from PIL import Image, ImageDraw, ImageFilter
    import numpy as np
    img = fit(img).convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    if kind == "banner":
        bw, bh = int(W * .66), int(H * .36); bx, by = (W - bw) // 2, int(H * .16)
        sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(sh).rectangle([bx + 14, by + 18, bx + bw + 14, by + bh + 18], fill=(0, 0, 0, 190))
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(16)))
        d.rectangle([bx, by, bx + bw, by + bh], fill=(52, 30, 18, 255), outline=(96, 62, 36, 255), width=5)
        d.rectangle([bx + 16, by + 16, bx + bw - 16, by + bh - 16], fill=(162, 132, 92, 255))
        px1, py1, px2, py2 = bx + 34, by + 34, bx + bw - 34, by + bh - 34
        d.rectangle([px1, py1, px2, py2], fill=(226, 210, 180, 255))
        f = font("brush", int(bh * .46)); step = (px2 - px1 - int((px2 - px1) * .2)) // 4
        for i, ch in enumerate("见路不走"):
            x = px1 + int((px2 - px1) * .14) + i * step
            d.text((x + 2, py1 + int((py2 - py1) * .16) + 2), ch, font=f, fill=(40, 30, 22, 150))
            d.text((x, py1 + int((py2 - py1) * .16)), ch, font=f, fill=(16, 13, 10, 250))
        # 书法家落款（不写叶子农）：年款 + 名章
        fs = font("brush", int(bh * .075))
        for j, ch in enumerate("戊辰夏日"):
            d.text((px1 + 14, py1 + 14 + j * int(bh * .08)), ch, font=fs, fill=(30, 24, 18, 230))
        ss = int(bh * .11); sx, sy = px1 + 12, py1 + 14 + 4 * int(bh * .08) + 6
        d.rectangle([sx, sy, sx + ss, sy + ss], fill=(170, 34, 26, 235))
        d.text((sx + 4, sy + 2), "之印", font=font("brush", int(ss * .45)), fill=(235, 220, 195, 235))
    elif kind == "note":
        pw, ph = int(W * .5), int(H * .38); px, py = int(W * .25), int(H * .3)
        d.rectangle([px, py, px + pw, py + ph], fill=(236, 226, 204, 236))
        for ly in range(py + 50, py + ph - 20, 44):
            d.line([(px + 26, ly), (px + pw - 26, ly)], fill=(180, 160, 128, 120), width=1)
        f = font("hand", int(ph * .13))
        d.text((px + 40, py + 40), "——我撑不住了。", font=f, fill=(20, 22, 40, 245))
        d.text((px + 40, py + 40 + int(ph * .2)), "我不能请求原谅，", font=f, fill=(20, 22, 40, 245))
        d.text((px + 40, py + 40 + int(ph * .4)), "这不是可以原谅的事。", font=f, fill=(20, 22, 40, 245))
        ov = ov.rotate(2.5, resample=Image.BICUBIC, center=(px + pw // 2, py + ph // 2))
    elif kind == "ledger":
        lines = ["诺尔库克公司个人损失：240万美元", "债务最后期限：1991年11月10日", "总债务：105万美元（私人债务60万）",
                 "1. 裕香阁饭店抵押贷款　本息45万", "2. 戴梦岩　　本息36万", "3. 老九　　　本息12万",
                 "4. 布兰迪　　本息6万", "5. 库格列夫　本息6万"]
        pw, ph = int(W * .56), int(H * .7); px, py = int(W * .22), int(H * .14)
        d.rectangle([px, py, px + pw, py + ph], fill=(232, 222, 198, 230))
        f = font("hand", int(ph * .062))
        for i, l in enumerate(lines):
            d.text((px + 36, py + 30 + i * int(ph * .11)), l, font=f, fill=(24, 28, 60, 240))
        ov = ov.rotate(-2, resample=Image.BICUBIC, center=(px + pw // 2, py + ph // 2))
    img = Image.alpha_composite(img, ov)
    # 台灯暗角
    yy, xx = np.ogrid[:H, :W]
    dist = np.sqrt(((xx - W / 2) / (W * .55)) ** 2 + ((yy - H * .45) / (H * .6)) ** 2)
    a = np.zeros((H, W, 4), np.uint8); a[..., 3] = np.clip((dist - .6) * 220, 0, 190).astype(np.uint8)
    return Image.alpha_composite(img, Image.fromarray(a)).convert("RGB")

def card(lines):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), (0, 0, 0)); d = ImageDraw.Draw(img)
    sizes = [52] + [36] * (len(lines) - 1)
    total = sum(sizes) + 30 * (len(lines) - 1); y = (H - total) // 2
    for l, sz in zip(lines, sizes):
        f = font("serif", sz); w = d.textlength(l, font=f)
        d.text(((W - w) / 2, y), l, font=f, fill=(225, 225, 225)); y += sz + 30
    return img

def stage_assemble():
    from PIL import Image
    import numpy as np
    meta = json.loads((ROOT / "audio_meta.json").read_text())
    seg_files, srt, t_cursor = [], [], 0.0
    for s in SHOTS:
        dur = meta[s["id"]]["dur"]; n = int(round(dur * FPS))
        out = SHOT / f"shot_{s['id']}.mp4"
        cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
               "-i", "-", "-i", str(AUD / f"shot_{s['id']}.wav"), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", "-t", f"{dur:.3f}", str(out)]
        pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        if s["kind"] == "card":
            base = np.array(card(s["text"]))
            for k in range(n):
                fade = min(1, k / (FPS * .6), (n - k) / (FPS * .6))
                pr.stdin.write((base * fade).astype(np.uint8).tobytes())
        elif s["kind"] == "still":
            src = read_frames(CLIP / f"clip_{s['id']}.mp4")
            base = overlay_prop(Image.fromarray(src[len(src) // 2]), s["overlay"])
            for k in range(n):  # 缓推
                z = 1 + .08 * k / n; cw, ch = int(W / z), int(H / z)
                fr = base.crop(((W - cw) // 2, (H - ch) // 2, (W - cw) // 2 + cw, (H - ch) // 2 + ch)).resize((W, H), Image.BICUBIC)
                pr.stdin.write(np.asarray(fr).tobytes())
        else:
            src = [np.asarray(fit(Image.fromarray(f))) for f in read_frames(CLIP / f"clip_{s['id']}.mp4")]
            clip_fps = 24 if len(src) > 100 else 16
            seq = []
            # 原速时长不够就放慢（最多 0.6 倍），仍不够则往返循环
            need = n / FPS; base_len = len(src) / clip_fps
            speed = max(0.6, min(1.0, base_len / need))
            idx = [min(len(src) - 1, int(k * clip_fps * speed / FPS)) for k in range(int(base_len / speed * FPS))]
            pingpong = idx + idx[::-1][1:-1]
            while len(seq) < n:
                seq += pingpong if seq else idx
            for k in range(n):
                fr = src[seq[k]]
                if s.get("caption") and k < FPS * 3:
                    im = Image.fromarray(fr); from PIL import ImageDraw
                    ImageDraw.Draw(im).text((60, H - 110), s["caption"], font=font("serif", 34), fill=(235, 235, 235))
                    fr = np.asarray(im)
                pr.stdin.write(fr.tobytes())
        pr.stdin.close(); pr.wait()
        for a, b, text in meta[s["id"]]["subs"]:
            srt.append((t_cursor + a, t_cursor + b, text))
        seg_files.append(out); t_cursor += dur
        log(f"assembled shot {s['id']} {dur:.1f}s")

    lst = ROOT / "concat.txt"; lst.write_text("".join(f"file '{p}'\n" for p in seg_files))
    raw = OUT / "raw.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(raw)], check=True)

    def ts(x):
        h, r = divmod(x, 3600); m, s_ = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s_):02d},{int((s_ % 1) * 1000):03d}"
    srt_path = OUT / "第01集_试片.srt"
    with open(srt_path, "w") as f:
        for i, (a, b, text) in enumerate(srt, 1):
            # 长句按 22 字折行
            chunks = [text[j:j + 22] for j in range(0, len(text), 22)]
            f.write(f"{i}\n{ts(a)} --> {ts(b)}\n" + "\n".join(chunks) + "\n\n")
    final = OUT / "第01集_试片.mp4"
    style = "FontName=Noto Sans CJK SC,FontSize=18,PrimaryColour=&H00F0F0F0,OutlineColour=&H00000000,BorderStyle=1,Outline=1.4,Shadow=0,MarginV=28"
    vf = (f"subtitles={srt_path}:force_style='{style}',noise=alls=7:allf=t,vignette=PI/5,"
          "eq=contrast=1.04:saturation=0.9")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-vf", vf, "-c:v", "libx264", "-crf", "19",
                    "-preset", "medium", "-c:a", "copy", str(final)], check=True)
    log(f"FINAL {final} {t_cursor:.1f}s")

if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    try:
        if stage in ("tts", "all"): stage_tts()
        if stage in ("video", "all"): stage_video()
        if stage in ("assemble", "all"): stage_assemble()
        log("ALL DONE" if stage == "all" else f"{stage} done")
    except Exception as e:
        import traceback
        log("ERROR " + repr(e)); log(traceback.format_exc()); raise
