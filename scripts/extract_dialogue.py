#!/usr/bin/env python3
"""Forward-only dialogue extract: NAME + verb + quote.

Never bind a quote to the *next* speaker (that was the 芮小丹/肖亚文 bug).
Names must be from a known list, longest first.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path


def compile_name_re(names: list[str]) -> re.Pattern[str]:
    uniq = sorted(set(names), key=len, reverse=True)
    return re.compile("|".join(re.escape(n) for n in uniq))


def parse_hui(text: str) -> int:
    m = re.search(r"第([一二三四五六七八九十百零〇○两\d]+)回", text)
    if not m:
        return 0
    t = m.group(1)
    if t.isdigit():
        return int(t)
    cn = {
        "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
        "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
    }
    # 第一一三回 / 第一二○回（校注本文件名，不用「百」）
    if t.startswith("一") and "十" not in t and "百" not in t and len(t) >= 3:
        rest = t[1:].replace("○", "零").replace("〇", "零")
        tens = cn.get(rest[0], 0)
        ones = cn.get(rest[1], 0) if len(rest) > 1 else 0
        return 100 + tens * 10 + ones
    if t.startswith("一百"):
        rest = t[2:]
        if not rest:
            return 100
        if rest.startswith("十"):
            return 110 + (cn.get(rest[1], 0) if len(rest) > 1 else 0)
        if "十" in rest:
            a, b = rest.split("十", 1)
            return 100 + cn.get(a, 0) * 10 + cn.get(b, 0)
        return 100 + cn.get(rest, 0)
    if t.startswith("十"):
        return 10 + (cn.get(t[1], 0) if len(t) > 1 else 0)
    if "十" in t:
        a, b = t.split("十", 1)
        return cn.get(a, 1) * 10 + cn.get(b, 0)
    return cn.get(t, 0)


def extract(
    raw: str,
    name_re: re.Pattern[str],
    alias: dict[str, str],
    verb: str,
) -> list[tuple[str, str]]:
    # optional adverb between name and verb, but not another name
    pat = re.compile(
        rf"(?<![\u4e00-\u9fff])({name_re.pattern})"
        rf"(?:对(?:{name_re.pattern}))?"
        rf"(?:[的地得])?"
        rf"(?:笑着|苦着脸|平静地|淡淡地|认真地|随口|忽然|立刻|细细|忙|因|便|又|也|却){{0,2}}"
        rf"(?:{verb})"
        rf"[道着了过得]?"
        rf"[：:，,]?\s*[“「\"]([^”」\"]{{2,500}})[”」\"]"
    )
    out: list[tuple[str, str]] = []
    for m in pat.finditer(raw):
        name = alias.get(m.group(1), m.group(1))
        quote = m.group(2).strip()
        if len(quote) < 2:
            continue
        out.append((name, quote))
    return out


def pick(items: list[dict], n: int) -> list[dict]:
    scored = []
    for it in items:
        length = len(it["text"])
        scored.append((min(length, 80) + (10 if 8 <= length <= 160 else 0), it))
    scored.sort(key=lambda x: -x[0])
    picked: list[dict] = []
    chs: collections.Counter[int] = collections.Counter()
    seen: set[tuple[int, str]] = set()
    for _, it in scored:
        key = (it["ch"], it["text"])
        if key in seen:
            continue
        if chs[it["ch"]] >= 4:
            continue
        seen.add(key)
        picked.append(it)
        chs[it["ch"]] += 1
        if len(picked) >= n:
            break
    picked.sort(key=lambda x: x["ch"])
    return picked


def run_book(
    files: list[Path],
    chapter_fn,
    names: list[str],
    alias: dict[str, str],
    verb: str,
    out_dir: Path,
    unit: str,
    full_n: set[str],
) -> list[dict]:
    name_re = compile_name_re(list(names) + list(alias.keys()))
    by: dict[str, list[dict]] = collections.defaultdict(list)
    for path in files:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        ch = chapter_fn(path, raw)
        for name, quote in extract(raw, name_re, alias, verb):
            by[name].append({"ch": ch, "text": quote})

    for name, lst in list(by.items()):
        seen: set[tuple[int, str]] = set()
        uniq = []
        for it in lst:
            key = (it["ch"], it["text"])
            if key in seen:
                continue
            seen.add(key)
            uniq.append(it)
        by[name] = uniq

    quotes_dir = out_dir / "quotes"
    quotes_dir.mkdir(parents=True, exist_ok=True)
    # drop stale files
    for old in quotes_dir.glob("*.md"):
        old.unlink()

    index = []
    for name, lst in sorted(by.items(), key=lambda x: -len(x[1])):
        nmax = 80 if name in full_n else 40
        chosen = pick(lst, nmax)
        lines = [
            f"# {name} · 原文台词\n",
            f"> 正向抽取（人名+动词+引号）{len(lst)} 条，精选 {len(chosen)} 条。不作反向粘贴。\n",
        ]
        for it in chosen:
            lines.append(f"- **第{it['ch']}{unit}** 「{it['text']}」")
        (quotes_dir / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        index.append({"name": name, "total": len(lst), "picked": len(chosen)})

    (out_dir / "_extract.json").write_text(
        json.dumps({"index": index, "rule": "forward-only NAME+verb+quote"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return index


def main() -> None:
    root = Path("/Users/duxiying/Documents/novel")

    # --- 救世主 ---
    alias_yy = {
        "小丹": "芮小丹", "芮警官": "芮小丹",
        "元英": "丁元英", "丁总": "丁元英", "丁先生": "丁元英", "丁哥": "丁元英",
        "亚文": "肖亚文", "欧阳": "欧阳雪",
        "韩总": "韩楚风", "韩大哥": "韩楚风",
        "晓明": "叶晓明", "世杰": "冯世杰",
        "林董": "林雨峰", "芮导": "芮伟峰",
        "张姨": "张慧敏", "芮母": "张慧敏",
        "建时": "郑建时", "雷队": "雷剑峰",
        "胖子": "赵国强", "福田": "王福田",
        "智玄大师": "智玄", "阎所长": "阎希成",
        "秋红": "丁秋红", "蒋律师": "蒋汉臣",
    }
    names_yy = [
        "丁元英", "芮小丹", "欧阳雪", "肖亚文", "韩楚风", "叶晓明", "冯世杰", "刘冰",
        "林雨峰", "智玄", "芮伟峰", "张慧敏", "詹妮", "郑建时", "王明阳", "赵青",
        "雷剑峰", "蒋汉臣", "周剑华", "阎希成", "苏逸文", "曾华", "王福田", "赵国强",
        "赵忠涛", "于志伟", "格贝森", "辛格", "格尔斯曼", "库兹曼", "恩格",
        "李志江", "丁秋红", "谢辉", "陈茹", "韦天逸", "杜小辉", "冯母", "刘大爷",
        "周国正", "吴志明", "李铁军", "刘牧师", "赵丽静", "赵云哲", "马经理",
        "戚伯", "楚婕", "沈楠", "黄福海", "吴建军", "刘东昌", "徐处长", "王队长",
        "黄文贤", "审判长", "张静", "小赵", "小杨",
    ]
    verb_modern = r"说|道|问|答|喊|骂|吼|冷笑|苦笑|解释|回答|插言|插话|吩咐|嘱咐|声明|宣布|强调|反问|质问|感叹|嘀咕|自语|喃喃"
    files_yy = sorted((root / "遥远的救世主").glob("[0-9]*_第*章.md"))

    def ch_yy(path: Path, raw: str) -> int:
        return int(path.name[:3]) - 2

    idx = run_book(
        files_yy, ch_yy, names_yy, alias_yy, verb_modern,
        root / "遥远的救世主" / "subagents", "章",
        {"丁元英", "芮小丹"},
    )
    print("救世主", len(idx), "people", sum(x["total"] for x in idx), "quotes")

    # --- 天幕 ---
    alias_tm = {
        "子农": "叶子农", "叶先生": "叶子农", "叶总": "叶子农",
        "梦岩": "戴梦岩", "梦姐": "戴梦岩", "戴小姐": "戴梦岩",
        "方总": "方迪", "方姐": "方迪",
        "九哥": "老九", "慕容久": "老九",
        "梁哥": "梁士乔", "梁先生": "梁士乔",
        "雪红": "林雪红", "林总": "林雪红", "林姐": "林雪红",
        "张主任": "张志诚", "彪哥": "沈彪",
        "许主席": "许亚夫", "许兄": "许亚夫",
        "钱主席": "钱静辉", "黄主任": "黄书宁", "雷师傅": "雷卫东",
        "石经理": "石天佑",
    }
    names_tm = [
        "叶子农", "戴梦岩", "方迪", "老九", "奥布莱恩", "罗家明", "林雪红",
        "布兰迪", "梁士乔", "张志诚", "沈彪", "沃尔斯", "乔治", "许亚夫",
        "钱静辉", "库格列夫", "黄书宁", "凯勒", "戴维", "沈处长", "方父",
        "赵军", "周富均", "石天佑", "雷卫东", "张娟", "耿大爷", "孙瑶",
        "董丽", "普林斯", "秦处长", "张立波",
    ]
    files_tm = sorted((root / "天幕红尘").glob("[0-9]*_第*.md"))

    def ch_tm(path: Path, raw: str) -> int:
        return int(path.name[:3])

    idx = run_book(
        files_tm, ch_tm, names_tm, alias_tm, verb_modern,
        root / "天幕红尘" / "subagents", "章",
        {"叶子农", "戴梦岩", "方迪"},
    )
    print("天幕", len(idx), "people", sum(x["total"] for x in idx), "quotes")

    # --- 红楼 ---
    alias_hlm = {
        "宝玉": "贾宝玉", "宝二爷": "贾宝玉",
        "黛玉": "林黛玉", "颦儿": "林黛玉", "林姑娘": "林黛玉", "林妹妹": "林黛玉",
        "宝钗": "薛宝钗", "宝姑娘": "薛宝钗", "宝丫头": "薛宝钗",
        "凤姐": "王熙凤", "凤姐儿": "王熙凤", "熙凤": "王熙凤",
        "老祖宗": "贾母", "史太君": "贾母",
        "探春": "贾探春", "三姑娘": "贾探春",
        "迎春": "贾迎春", "惜春": "贾惜春",
        "湘云": "史湘云", "袭人": "花袭人",
        "雨村": "贾雨村", "士隐": "甄士隐",
        "可卿": "秦可卿", "秦氏": "秦可卿",
        "英莲": "香菱", "秋菱": "香菱",
        "元春": "贾元春", "姥姥": "刘姥姥",
        "警幻": "警幻仙姑",
    }
    names_hlm = [
        "贾宝玉", "林黛玉", "薛宝钗", "王熙凤", "贾母", "王夫人", "贾政",
        "贾探春", "贾迎春", "贾惜春", "史湘云", "花袭人", "晴雯", "鸳鸯",
        "平儿", "紫鹃", "刘姥姥", "贾雨村", "甄士隐", "秦可卿", "香菱",
        "妙玉", "薛蟠", "贾琏", "贾珍", "尤氏", "邢夫人", "薛姨妈", "李纨",
        "贾元春", "赵姨娘", "贾环", "麝月", "秋纹", "司棋", "芳官",
        "警幻仙姑", "周瑞家的", "焦大",
    ]
    verb_hlm = r"冷笑道|忙笑道|笑问道|笑道|哭道|骂道|问道|答道|回道|说道|因道|便道|又道|道"
    files_hlm = sorted(
        p for p in (root / "红楼梦").iterdir()
        if "回" in p.name and p.suffix == ".md"
    )

    def ch_hlm(path: Path, raw: str) -> int:
        return parse_hui(path.name) or parse_hui(raw[:120])

    idx = run_book(
        files_hlm, ch_hlm, names_hlm, alias_hlm, verb_hlm,
        root / "红楼梦" / "subagents", "回",
        {"贾宝玉", "林黛玉", "王熙凤", "薛宝钗"},
    )
    print("红楼", len(idx), "people", sum(x["total"] for x in idx), "quotes")


if __name__ == "__main__":
    main()
