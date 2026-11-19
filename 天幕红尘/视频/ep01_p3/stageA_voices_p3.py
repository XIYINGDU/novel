#!/Users/duxiying/.local/share/uv/tools/google-colab-cli/bin/python
"""ep01 p3 配音（VoxCPM2）。台词来自 剧本/第01集.md 1-7、1-8；长段按镜头拆句（画内开口者才进 LatentSync）。
关键句（keyline）两条候选人耳选（A-KEYLINE-MULTI-CANDIDATE）。数字一律写汉字，防 TTS 读错。
音色 seed：梁士乔 1998 / 戴梦岩 1999 / 韩平 2000 / 阿英 2001（A-ACTOR-BASE-VOICE）；导演（画外一声「咔」）2002。
用法：本文件用 google-colab-cli 的 python 直接运行。
"""
import json
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
from colab_pool import ColabPool  # noqa: E402
from remote_job import run_remote  # noqa: E402

AUD = HERE / "audio"
JOB = HERE / "vox_job_p3.json"

ACTORS = {
    "liang": ["四十多岁香港男人，演艺经纪公司总经理，带一点港式口音的普通话，嗓音温润儒雅，语速快而有分寸，精明务实，生活化真实说话，绝不播音腔",
              "这次的行程我都排好了，你们照着走就行。", 1998],
    "dai": ["二十八岁香港当红女影星，带轻微港式口音的普通话，中音清冷有质感，语气平静笃定、自带气场，生活化，绝不播音腔、绝不娇嗲",
            "今天的戏拍完我再回酒店，有事打片场电话找我。", 1999],
    "han": ["二十多岁北京小伙子，剧组司机，地道北京口音，嗓音年轻清亮，说话利落，生活化", "车就停在外头，您出来我就开过来。", 2000],
    "aying": ["二十七岁香港女助理，带港式口音的普通话，正患感冒、鼻音很重，声音轻而稳当，生活化", "东西我都收好了，您放心。", 2001],
    "director": ["四十多岁北方男人，片场导演，嗓门洪亮干脆", "好，各部门准备。", 2002],
}

# [文件名, 角色, 情绪/语气描述, 台词, seed]
LINES = [
    ["han_7c", "han", "看了传呼机脸色一变，急声上前汇报，压着嗓子又急", "梁哥，梦姐刚呼您——说情况有变，取消去巴黎，让您速回片场！", 7301],
    ["liang_7g", "liang", "在电话亭里看着表压低声音，有点不耐烦", "什么事？我马上登机了。还有什么事能比圣西蒙电影节颁奖典礼更重要？", 7302],
    ["dai_7h", "dai", "接电话，语调平缓而严峻，不容商量", "你今天不能去巴黎了，得先飞一趟纽约，再从纽约转去巴黎，顺道回家看看。阿英刚查过，晚上十一点那班还有票。", 7303],
    ["dai_7i_t1", "dai", "压着情绪，低沉严峻地说出噩耗，一字一顿", "梁哥，出事了——罗家明二十四号在莫斯科破产自杀了，苏老师受不住打击，二十五号在纽约心脏病猝死。", 7311],
    ["dai_7i_t2", "dai", "声音克制发紧，平静里透着沉重，停顿处有呼吸", "梁哥，出事了——罗家明二十四号在莫斯科破产自杀了，苏老师受不住打击，二十五号在纽约心脏病猝死。", 7312],
    ["dai_7k_a", "dai", "冷静有条理地交代细节，语速平稳", "阿英二十分钟前在酒店商务中心亲自接了林雪红的保密传真，我刚打去纽约核实过，葬礼就在明天二十八号。", 7321],
    ["dai_7k_b", "dai", "冷静有条理地继续交代，末句干脆", "传真里没提葬礼，主要说借给苏老师那笔连本带利三十六万美金的债，让我们巴黎颁奖礼结束后去柏林开债权人会议。我还没看到传真原件，你退了票直接来片场。", 7322],
    ["liang_7l_a", "liang", "推推眼镜，职业本能上来，语速加快据理力争", "这次最佳女主角提名你是最被看好的，每个细节都关系你的最新身价！人都没了，罗家明如果有办法愿意死吗？", 7331],
    ["liang_7l_b", "liang", "急切地摆道理，有点激动", "他不知道他母亲的心脏承受不了这种打击吗？况且今晚十一点的飞机到纽约是明天下午两点，根本赶不上上午的葬礼！", 7332],
    ["dai_7m_a", "dai", "寸步不让，平静但强硬", "我接到消息第一时间做出反应了，这是最重要的。三十六万美金能不能还也要弄个明白，如果是走过场我就没必要再去柏林。", 7341],
    ["dai_7m_b", "dai", "语气放缓一点，但不容拒绝", "我办美国签证来不及，你替我走一趟吧。", 7342],
    ["liang_7n", "liang", "无奈地叹口气妥协", "你想怎样就怎样吧，我退票去。", 7351],
    ["aying_8b", "aying", "带着感冒鼻音低声交代，稳当", "梁哥，传真我在商务中心亲手收的，晚上十一点的票锁好了。", 7401],
    ["director_8g", "director", "隔着很远大声喊停", "咔！", 7402],
    ["liang_8i", "liang", "把传真递过去，语气平淡里带着判断", "你自己看吧。林雪红连半句让你去葬礼的暗示都没有，她没这个心思了，她关心的是债。", 7411],
    ["liang_8j_a", "liang", "冷静地摆事实，像在报账", "罗家明跟两个苏联高官公子搞权力经济买油井批文，政变洗牌全砸手里了，个人赔光二百四十万，北京房产早卖了。", 7412],
    ["liang_8j_b", "liang", "条理清楚地一笔一笔数债，语速平稳", "现在总债一百零五万美金，全是十一月十号到期——曼哈顿裕香阁饭店抵押贷了四十五万，剩下六十万私人债：你三十六万是大头，纽约老九，十二万；美国电视台一个叫布兰迪的六万，莫斯科库格列夫六万。", 7413],
    ["dai_8l_a_t1", "dai", "啪地合上传真，满脸不屑，冷笑着挖苦", "见路不走？送罗家明这四个字的叶子农，脑子不正常吧！初中文凭，自己还蜷在柏林四十平米的破屋里靠租间小铺子混饭吃，", 7421],
    ["dai_8l_a_t2", "dai", "语带讥讽，轻蔑地一句句数落", "见路不走？送罗家明这四个字的叶子农，脑子不正常吧！初中文凭，自己还蜷在柏林四十平米的破屋里靠租间小铺子混饭吃，", 7422],
    ["dai_8l_b", "dai", "不屑地下结论，末句冷淡干脆", "他要有本事早发财了，罗家明死前还不知道找他求条生路？还轮得着林雪红约九月五号去柏林开会？这钱，没指望了。", 7423],
    ["liang_8m", "liang", "点着烟，慢悠悠地，目光深邃", "林雪红写了这么多，条理这么清楚，半点没乱方寸，也许就是要让你自己得出这个结论。", 7431],
    ["dai_8n", "dai", "沉吟片刻，疑惑地问", "苏老师也是有知名度的人，三天了怎么一点风声都没漏？", 7441],
    ["liang_8n", "liang", "淡淡地，有点世故的感慨", "贫居闹市无人问嘛，封锁消息大家都避免尴尬。", 7442],
    ["dai_8o", "dai", "干脆地交代，有分寸", "你带上点钱去纽约，人到了，礼就到了。一万美金吧——太少了像讨债的，还不如不去。", 7451],
    ["dai_8p_t1", "dai", "仰头望着灯，忽然有些茫然，声音轻下来", "梁哥，要在两个月里凭空生出这么大一笔钱，你觉得有可能吗？", 7461],
    ["dai_8p_t2", "dai", "低声自问似的，带一点疲惫和不确定", "梁哥，要在两个月里凭空生出这么大一笔钱，你觉得有可能吗？", 7462],
    ["liang_8q_t1", "liang", "斩钉截铁，干脆利落", "就是组织抢银行都来不及了。", 7471],
    ["liang_8q_t2", "liang", "苦笑一声，断然地", "就是组织抢银行都来不及了。", 7472],
]


# 重配：8j_b 台词去歧义（「纽约老九，十二万」）；导演「咔」多出几条；「见路不走」关键句再加两条候选
RETAKES = [l for l in LINES if l[0] == "liang_8j_b"] + [
    ["director_8g_t2", "director", "片场导演隔着大棚扯着嗓子短促喊停，一个字", "咔！", 7403],
    ["director_8g_t3", "director", "导演对着喇叭大喊一声停", "咔——！", 7404],
    ["dai_8l_a_t3", "dai", "啪地合上传真，冷笑着一字一顿念出这四个字，再轻蔑数落", "见、路、不、走？送罗家明这四个字的叶子农，脑子不正常吧！初中文凭，自己还蜷在柏林四十平米的破屋里靠租间小铺子混饭吃，", 7424],
    ["dai_8l_a_t4", "dai", "不屑地反问，「见路不走」四个字咬字清楚，语带讥讽", "见路不走？送罗家明这四个字的叶子农，脑子不正常吧！初中文凭，自己还蜷在柏林四十平米的破屋里靠租间小铺子混饭吃，", 7425],
]


def main():
    retake = "--retake" in sys.argv
    lines = RETAKES if retake else LINES
    uploads, refs = {}, {}
    if retake:  # 复用已铸好的角色音色，保证同一副嗓子
        for key in {l[1] for l in lines}:
            wav = AUD / f"actor_{key}.wav"
            uploads[wav] = f"/content/actor_{key}.wav"
            refs[key] = f"/content/actor_{key}.wav"
    tag = "vox_p3_retake" if retake else "vox_p3"
    JOB.write_text(json.dumps({"actors": ACTORS, "refs": refs, "lines": lines, "out": f"/content/{tag}_out.tar.gz"},
                              ensure_ascii=False, indent=1))
    uploads[JOB] = "/content/vox_job.json"
    tar_local = HERE / f"{tag}_out.tar.gz"
    with ColabPool(n=1, seg="p3", stage="voices") as pool:
        res, failed = pool.run([0], lambda w, _: run_remote(
            w, HERE.parent / "common" / "remote_voxcpm2.py", uploads,
            f"/content/{tag}_out.tar.gz", tar_local, timeout_s=2400, tag=tag), key=lambda _: "vox")
    if failed:
        raise SystemExit(f"配音失败：{failed}")
    AUD.mkdir(exist_ok=True)
    if retake:
        old = AUD / "liang_8j_b.wav"
        if old.exists():
            (AUD / "_v1").mkdir(exist_ok=True)
            for ext in ("wav", "mp3"):
                (AUD / f"liang_8j_b.{ext}").rename(AUD / "_v1" / f"liang_8j_b.{ext}")
    with tarfile.open(tar_local) as tf:
        tf.extractall(AUD, filter="data")
    print(f"[voices] {len(lines)} 条 → {AUD}")


if __name__ == "__main__":
    main()
