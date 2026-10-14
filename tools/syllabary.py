#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""洄文 · 音系音节表生成器（单一真相源）

设计事实（全部由本文件派生，其它文件不得另写一份）：
  声基 13 类（含零声基） x 腔 8 类 x 调 3 类 = 312 个合法音节
  调 1 = 平（不标）；调 2 = 升（拉丁式加 ˊ，ASCII 加 2）；调 3 = 降（ˇ / 3）
  零声基在声调 1 拼作 y-（yav / yev / yiv / yov / yöv / yuv / yyv / yyv）
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# ---------------------------------------------------------------- 声基（辅音）
# (键, ASCII 字母, IPA, 汉字名, 别名)
ONSETS = [
    ("zero", "-", "∅", "零", "无起首音"),
    ("p",    "p", "p",   "波", "双唇不送气清塞音"),
    ("b",    "b", "b",   "並", "双唇浊塞音"),
    ("t",    "t", "t",   "端", "齿龈不送气清塞音"),
    ("d",    "d", "d",   "定", "齿龈浊塞音"),
    ("k",    "k", "k",   "见", "软腭不送气清塞音"),
    ("g",    "g", "ɡ",   "群", "软腭浊塞音"),
    ("m",    "m", "m",   "明", "双唇鼻音"),
    ("n",    "n", "n",   "泥", "齿龈鼻音"),
    ("s",    "s", "s",   "心", "清齿龈擦音"),
    ("z",    "z", "z",   "邪", "浊齿龈擦音"),
    ("h",    "h", "x",   "晓", "清软腭擦音"),
    ("l",    "l", "l",   "来", "齿龈边音"),
]

# ---------------------------------------------------------------- 腔（元音）
# (键, 显示名, ASCII 拼法, IPA)
VOWELS = [
    ("a",  "a",  "a",   "a"),
    ("e",  "e",  "e",   "e"),
    ("i",  "i",  "i",   "i"),
    ("o",  "o",  "o",   "o"),
    ("oe", "ö",  "oe",  "ø"),
    ("u",  "u",  "u",   "u"),
    ("y",  "y",  "y",   "y"),
    ("v",  "v",  "v",   "ɨ"),
]
ZERO_ONSET_SPELLING = "y"  # 零声基 + 调1 的拼法（yv = [ɨ]，非 [y]）

# ---------------------------------------------------------------- 调
TONES = [
    (1, "平", "", "", "˥", "高平"),
    (2, "升", "ˊ", "2", "˧˥", "中升"),
    (3, "降", "ˇ", "3", "˥˩", "高降"),
    (4, "促", "ˬ", "4", "˦˨", "短促微降（第一次扩容：第 14–16 场词根）"),
    (5, "低", "ˏ", "5", "˩", "低平（第二次扩容：第 17–20 场词根）"),
    (6, "高", "ˋ", "6", "˥˧", "高微降（第三次扩容：虚词与派生语素）"),
]

DIACRITIC = {
    "a": "aàǎ", "e": "eèě", "i": "iìǐ", "o": "oòǒ",    "u": "uùǔ", "y": "yỳỷ", "v": "vṿv̌",
    "ö": "öȫö̌",
}
# 第 4/5 调（促／低）的优雅式：统一用附加符号，不引入新字母
BREVE = {"a": "ă", "e": "ĕ", "i": "ĭ", "o": "ŏ", "u": "ŭ",
         "y": "y̆", "v": "v̆", "ö": "ö̆"}
MACRON = {"a": "ā", "e": "ē", "i": "ī", "o": "ō", "u": "ū",
          "y": "ȳ", "v": "v̄", "ö": "ȫ"}
GRAVE2 = {"a": "â", "e": "ê", "i": "î", "o": "ô", "u": "û",
          "y": "ŷ", "v": "v̂", "ö": "ö̂"}


def latin(onset: str, vowel: str, tone: int, ascii_only: bool = True) -> str:
    """拼写一个音节。ascii_only=True 时用 oe/数字，否则用 ö/加符。

    规则：零声基一律加 y-（ya ye yi yo yö yu yy yv）；调号用数字后缀。
    """
    o = "y" if onset == "zero" else onset
    v = vowel
    if tone == 1:
        return o + v
    if ascii_only:
        return o + v + str(tone)
    if v == "oe":
        v = "ö"
    if tone == 4:
        return o + BREVE[v]
    if tone == 5:
        return o + MACRON[v]
    if tone == 6:
        return o + GRAVE2[v]
    idx = tone - 1
    return o + DIACRITIC[v][idx]


def all_syllables():
    """规范顺序：调外循环 → 声基 → 腔。这是整个项目唯一的排序真相源。"""
    out = []
    for tone, tname, _d, _a, _ipa, _desc in TONES:
        for okey, oascii, oipa, ocn, _od in ONSETS:
            for vkey, vdisp, vascii, vipa in VOWELS:
                out.append({
                    "syll": latin(okey, vkey, tone, ascii_only=True),
                    "spell": latin(okey, vkey, tone, ascii_only=False),
                    "tone": tone,
                    "onset": okey,
                    "vowel": vkey,
                    "ipa": (oipa if okey != "zero" else "∅") + vipa + TONES[tone - 1][4],
                })
    return out


# ---------------------------------------------------------------- 语义场
# id, 汉字名, 边界说明（给起草者划定范围，防止跨场重复）
DOMAINS = [
    # —— 第一批（编号 0..383，单音节，调 1–4）——
    ("ont",   "本体", "存在/有无、同一与差异、整体与部分、类与例、状态与变化、真伪、必然与可能、因果、目的、本质与现象"),
    ("qnt",   "数量", "数、计数与序、多寡、全部与部分、程度、比较、度量与单位、增减、比例"),
    ("spac",  "空间", "方位与距离、内外上下前后、形状、边界与开口、路径、容纳、表面、几何关系、空旷与密集"),
    ("time",  "时间", "时点与时段、先后、同时、持续、开始与终结、周期、过去与未来、等待、瞬间与永恒"),
    ("mov",   "运动", "移动、静止、来去、速度、方向改变、传递与转移、抵达与离开、推拉、旋转与振荡、坠落与升起"),
    ("body",  "身体", "身体部位、生理状态、饥渴疲劳、睡眠与清醒、健康与疾病、生死、五感、性别与生育、气息"),
    ("mind",  "心灵", "情绪、欲望、意图与意志、记忆与遗忘、想象、注意、疑惑与确定、痛苦与愉悦、勇气与恐惧"),
    ("soci",  "社会", "亲属与称谓、朋友与陌生人、群体与身份、权力与服从、冲突与合作、礼节、法律与惩罚、婚配、声誉"),
    ("econ",  "经济", "财物、交换、买卖、价与值、劳与酬、借贷、贫富、工具与器物、建造、衣食住、工艺"),
    ("info",  "信息", "语言与言说、问与答、命名、真话与谎、学习与教、知识、推理与论证、记号与文本、传闻与见证"),
    ("aest",  "美感", "美丑、光与色、声与乐、节奏、形与纹、雅与俗、崇高、幽默、艺术创作、静观"),
    ("ethc",  "伦理", "善与恶、应当、责任、正义、宽恕与报复、荣誉与羞耻、自由、牺牲、承诺、规矩"),
    ("affa",  "情感", "爱与恨、亲近与疏远、挂念与思念、嫉妒、温柔、愤怒、羞耻、孤独、安慰、依恋"),
    ("natu",  "自然", "天地、水土、火、气与风、云雨雪、昼夜四季、植物、动物、山川、星辰、材料"),
    ("math",  "数理", "集合与元素、映射与函、序列与级数、方程与解、证明、对称、随机、空间维度、运算、无穷与极限"),
    ("tech",  "技术", "机械、动力、电与磁、信号、计算与算法、程序、网络、材料强度、测量仪器、失效与维修"),
    # —— 第二批（编号 384..479，单音节，调 5）——
    ("come",  "饮食", "食与饮、味与香、烹与煮、餐具、饱与饿、宴与客、食谱、酒与茶、贮食、忌口"),
    ("clth",  "服饰", "衣与裳、冠与履、织物与缝纫、饰物、纹样、裁与量、新旧、身份之服"),
    ("bldg",  "建筑", "屋与室、门与窗、梁与柱、层与阶、城与墙、庭与院、修与拆、居所类型"),
    ("traf",  "交通", "道路与水路、车与舟、行与载、里程、关卡、路标、拥挤与通畅、渡与桥"),
    # —— 第三批（双音节，由派生式与复合派生，不占单音节格）——
    ("medi",  "医药", "病与症、药与剂、诊与治、伤与愈、疫与防、医者、养与损"),
    ("law",   "法政", "律与令、权与责、诉与判、证与据、官与民、国与界、税与役、赦与罚、议与决"),
    ("war",   "军事", "兵与器、攻与守、阵与谋、胜与败、盟与叛、粮与辎、谍与令、血与和"),
    ("agri",  "农事", "耕与种、苗与穗、土与肥、灌与收、仓与囤、农时、牲与畜、荒与丰、果与蔬"),
    ("tool",  "器用", "手工具、容器、绳索与钉、刃与锤、量器、磨与削、修与补、废弃、借还"),
    ("game",  "游艺", "戏与玩、赌与弈、胜负、规则、队与伴、玩具、竞技、观者、兴与倦"),
    ("weat",  "天候", "晴与阴、风与雨、雷与电、霜与雾、寒与暑、报与测、旱与涝、季与节"),
    ("anim",  "禽兽", "走兽、飞禽、水族、虫豸、家畜、野物、巢与穴、驯与野、皮与角、鸣与吼"),
    ("plant", "草木", "树与木、草与苔、花与果、根与茎、叶与皮、林与丛、枯与荣、种与芽"),
    ("phys",  "形质", "轻与重、硬与软、韧与脆、粗与滑、干与湿、透与蔽、熔与凝、弹与塑"),
    ("chem",  "物质", "元素与合、酸与碱、溶与析、燃与熄、锈与蚀、气液固、纯与杂、毒与药"),
    ("astro", "天文", "日与月、星与辰、天球与轨、潮与汐、历与算、观测、远与近、宇宙"),
    ("geo",   "地理", "山与谷、河与湖、海与岸、岛与陆、沙与岩、纬与经、图与向、土与矿"),
    ("music", "乐律", "音与阶、调与律、器与弦、吹与击、曲与谱、和与独、歌与舞、静与响"),
    ("color", "色采", "红与紫、蓝与绿、黄与褐、黑与白、明与暗、染与褪、混与纯、光泽"),
    ("cook",  "烹调", "切与剁、炒与蒸、煮与烤、腌与熏、调味、火候、盛与摆、剩与鲜"),
    ("text",  "纺织", "丝与麻、棉与毛、纺与织、染与印、缝与补、布幅、经纬、旧与新"),
    ("metal", "金工", "冶与铸、锻与焊、刃与磨、钉与铆、锈与镀、矿与渣、器与废"),
    ("med2",  "医理", "经脉与脏腑、气与血、虚与实、补与泻、诊脉、养生、针灸、药性"),
    ("phil",  "思辨", "是与非、名与实、知与行、一与多、动与静、有限与无穷、怀疑、论证"),
    ("ritual","礼俗", "祭与祷、节与庆、婚与丧、拜与揖、供与献、禁忌、乡约、宴礼"),
    ("comm",  "商易", "契约、账目、票据、货币、市价、运输、仓储、合伙、亏盈"),
    ("educ",  "教育", "学与考、师与徒、课与业、读与写、奖与罚、蒙学、讲席、结业"),
    ("art2",  "艺文", "诗与文、画与书、刻与印、章法、体派、评与赏、藏与传"),
]


# 场 → 分配的音节块。**按调分组分配**，不按「场数 × 24」硬切：
#   · 第 1–13 场：编号 0..311，调 1–3（与第一版逐字相同，不许动）
#   · 第 14–16 场：编号 312..383，调 4（与第一版逐字相同，不许动）
#   · 编号 384..415：**留空**（调 4 的尾巴）
#   · 第 17–20 场：编号 416..511，调 5
#   · 虚词：编号 520..551，调 6
#   · 派生语素池：编号 552..591，调 6
#   · 其余：备用
SINGLE_SYLLABLE_DOMAINS = 20
SLOTS_PER_DOMAIN = 24             # 每个单音节场的格数
DERIV_PATTERN_SLOTS = 20          # 派生式数量
DERIV_SYLL_PER_PATTERN = 2        # 每式占用的音节数

# 各音调组的起点（由 TONES 长度与 13 声基 × 8 腔 推出）
ONSETS_N = len(ONSETS)
VOWELS_N = len(VOWELS)
PER_TONE = ONSETS_N * VOWELS_N    # 104


def _tone_start(tone: int) -> int:
    return (tone - 1) * PER_TONE


DOMAIN_ORDER = [d[0] for d in DOMAINS]
CORE_DOMAINS = DOMAIN_ORDER[:13]
EXT_DOMAINS = DOMAIN_ORDER[13:]


def blocks():
    """按调分组分配音节。返回 {场/池: [音节记录]} 与完整音节表。"""
    sy = all_syllables()
    out: dict[str, list] = {}

    # 1) 前 13 场：调 1–3 起点连续
    cursor = _tone_start(1)                                   # 0
    for did in DOMAIN_ORDER[:13]:
        out[did] = sy[cursor:cursor + SLOTS_PER_DOMAIN]
        cursor += SLOTS_PER_DOMAIN

    # 2) 第 14–16 场：调 4
    cursor = _tone_start(4)                                   # 312
    for did in DOMAIN_ORDER[13:16]:
        out[did] = sy[cursor:cursor + SLOTS_PER_DOMAIN]
        cursor += SLOTS_PER_DOMAIN

    # 3) 第 17–20 场：调 5
    cursor = _tone_start(5)                                   # 416
    for did in DOMAIN_ORDER[16:20]:
        out[did] = sy[cursor:cursor + SLOTS_PER_DOMAIN]
        cursor += SLOTS_PER_DOMAIN

    # 4) 其余单音节场（若有）与双音节场
    for did in DOMAIN_ORDER[20:]:
        out[did] = []          # 双音节场：词形由派生式合成，不占单音节格

    # 5) 虚词（调 6 前 32）与派生语素池（调 6 接下来的 40）
    g0 = _tone_start(6)
    out["_grammar_pool"] = sy[g0:g0 + 32]
    out["_deriv_pool"] = sy[g0 + 32:g0 + 32 + DERIV_PATTERN_SLOTS * DERIV_SYLL_PER_PATTERN]
    used = g0 + 32 + DERIV_PATTERN_SLOTS * DERIV_SYLL_PER_PATTERN
    out["_reserved_future"] = sy[used:]
    return out, sy


def main():
    blk, sy = blocks()
    single = sum(len(blk[d]) for d in DOMAIN_ORDER)
    print(f"音节总数 {len(sy)}（{len(ONSETS)} 声基 × {len(VOWELS)} 腔 × {len(TONES)} 调）"
          f"｜单音节格 {single}｜虚词池 {len(blk['_grammar_pool'])}"
          f"｜派生池 {len(blk['_deriv_pool'])}｜备用 {len(blk['_reserved_future'])}")
    print(f"语义场 {len(DOMAIN_ORDER)} 个（单音节场 {SINGLE_SYLLABLE_DOMAINS}，"
          f"双音节场 {len(DOMAIN_ORDER) - SINGLE_SYLLABLE_DOMAINS}）")

    # 1) 完整音节表（glyph_index = 音节在表中的序号；字形编号另见 lexicon）
    lines = ["syll\ttone\tonset\tvowel\tspell\tipa\tsyll_index"]
    for i, s in enumerate(sy):
        lines.append(f"{s['syll']}\t{s['tone']}\t{s['onset']}\t{s['vowel']}\t"
                     f"{s['spell']}\t{s['ipa']}\t{i}")
    (HERE / "syllabary.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 2) 分场块表（给起草者的工单）
    meta = {"onsets": ONSETS, "vowels": VOWELS, "tones": TONES,
            "domains": DOMAINS, "order": DOMAIN_ORDER,
            "core_domains": CORE_DOMAINS, "ext_domains": EXT_DOMAINS,
            "single_syllable_domains": SINGLE_SYLLABLE_DOMAINS,
            "per_tone": ONSETS_N * VOWELS_N}
    (HERE / "phonology.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    dom = {d[0]: {"zh": d[1], "scope": d[2], "class_no": k}
           for k, d in enumerate(DOMAINS)}
    for did in DOMAIN_ORDER:
        cells = blk[did]
        idx = [sy.index(c) for c in cells]
        dom[did]["block"] = [c["syll"] for c in cells]
        dom[did]["block_spell"] = [c["spell"] for c in cells]
        dom[did]["block_ipa"] = [c["ipa"] for c in cells]
        dom[did]["syll_index_base"] = idx
    for k, name in (("_grammar_pool", "语法虚词"), ("_deriv_pool", "派生语素"),
                    ("_reserved_future", "未来扩充")):
        dom[k] = {"zh": name, "block": [c["syll"] for c in blk[k]],
                  "block_spell": [c["spell"] for c in blk[k]]}
    (HERE / "domains.json").write_text(
        json.dumps(dom, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3) 人读表
    md = [f"# 洄文音节表（{len(sy)}）", "",
          "| # | 拼式 | 优雅式 | IPA | 调 | 声基 | 腔 |", "|---:|---|---|---|---|---|---|"]
    for i, s in enumerate(sy):
        md.append(f"| {i} | `{s['syll']}` | {s['spell']} | {s['ipa']} | {s['tone']} | {s['onset']} | {s['vowel']} |")
    (HERE / "syllabary.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    for did in DOMAIN_ORDER:
        b = dom[did]["block"]
        if not b:
            continue          # 双音节场不占单音节格
        tag = "核心" if did in CORE_DOMAINS else "扩展"
        print(f"[{tag}] {did:5s} {dom[did]['zh']} 类{dom[did]['class_no']:>2}  "
              f"{b[0]:>5} … {b[-1]:<5} | {' '.join(b[:6])} …")
    print(f"[虚词] 调 6 前 32｜[派生语素] 调 6 接下 40｜[备用] {len(blk['_reserved_future'])}")


if __name__ == "__main__":
    main()
