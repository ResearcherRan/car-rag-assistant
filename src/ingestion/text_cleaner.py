"""PDF 提取文本的清洗。

这份说明书实际存在三类问题，分别处理：

1. 字体乱码
   PDF 内嵌的 E-BZ / E-FZ 两个符号字体缺少 ToUnicode 映射，pymupdf 把部分
   标点符号映射成了汉字。例如目录里的「渊3冤」原文是「（3）」。
   下面的映射表每一项都对照渲染出的原图核对过。

2. 页脚
   正文最后一定是「印刷页码 / - / -」三行（192 页如此，其余是前置页和整页图）。
   已核对：印刷页码恒等于 PDF 页码 - 10，见 PAGE_NUMBER_OFFSET。

3. 空白
   旧实现用 re.sub(r"\\s+", "", text) 删掉所有空白，后果是把
   「危险 / 警告」这类标签和正文粘成一句，段落结构也一起丢失。
   现在只做规范化：保留换行，只压缩与排版有关的空格。
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# 1. 字体乱码修复
# ---------------------------------------------------------------------------
# 只收录"在本语料中不会合法出现"的字符，避免误伤正文。
# （「因」是常用字，不能放进来，见 CONTEXT_FIXES）
GLYPH_FIXES = str.maketrans({
    "渊": "（",   # 渊3冤 → （3）
    "冤": "）",
    "尧": "、",   # 开尧闭油箱门 → 开、闭油箱门
    "淫": "※",   # 无钥匙系统淫 → 无钥匙系统※
    "荫": "●",   # 荫松开驻车制动器 → ●松开驻车制动器
    "院": "：",   # 主要具有以下功能院 → …功能：
    "揖": "【",   # 揖A/C 铱 → 【A/C】
    "铱": "】",
    "袁": "，",   # 能转动袁但不能启动 → 能转动，但不能启动
})

# 「因」在正文里大量合法出现（因为 / 因此 / 原因），不能全局替换。
# 只有版权页那一处是 ◎ 的乱码，用上下文精确定位。
CONTEXT_FIXES = [
    (re.compile(r"因(?=重庆长安汽车股份有限公司)"), "◎ "),
]

# ---------------------------------------------------------------------------
# 2. 页脚
# ---------------------------------------------------------------------------
# 匹配结尾的「数字 / - / -」，允许行内空白。
# 用 (?:^|\n) 而不是只写 \n，是为了兼顾第 202 页那种整页是图、
# 正文只有页码的页（文本从页码开头，前面没有换行）。
FOOTER_RE = re.compile(
    r"(?:^|\n)[ \t]*(\d{1,3})[ \t]*\n[ \t]*-[ \t]*\n[ \t]*-?[ \t]*$"
)

# 印刷页码 = PDF 页码 - 10。仅用于测试断言，不参与清洗逻辑。
PAGE_NUMBER_OFFSET = 10

# ---------------------------------------------------------------------------
# 3. 空白与标点规范化
# ---------------------------------------------------------------------------
# 汉字 + 中文标点 + 全角字符
_CJK = r"\u3000-\u303f\u4e00-\u9fff\uff00-\uffef"

_RE_SPACE_AFTER_CJK = re.compile(rf"(?<=[{_CJK}]) +")
_RE_SPACE_BEFORE_CJK = re.compile(rf" +(?=[{_CJK}])")
_RE_MULTI_SPACE = re.compile(r" {2,}")
_RE_MULTI_NEWLINE = re.compile(r"\n{3,}")


def clean_page_text(text: str) -> str:
    """清洗单页文本。幂等：重复调用结果不变。"""
    if not text:
        return ""

    # 统一换行符
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 先去掉尾部空白，保证页脚一定贴在字符串末尾
    text = text.rstrip()

    # 字体乱码
    text = text.translate(GLYPH_FIXES)
    for pattern, repl in CONTEXT_FIXES:
        text = pattern.sub(repl, text)

    # 页脚
    text = FOOTER_RE.sub("", text)

    # 去掉每行行尾空白（PDF 常见的是行尾多余空格）
    text = "\n".join(line.rstrip() for line in text.split("\n"))

    # 制表符和连续空格压成一个空格
    text = text.replace("\t", " ")
    text = _RE_MULTI_SPACE.sub(" ", text)

    # 去掉与汉字相邻的空格：PDF 在中英文字体切换处会插入空格，
    # 例如「逸动DT 系列」「5000 公里」。
    # 纯拉丁文之间的空格要保留（如「In Call」）。
    text = _RE_SPACE_AFTER_CJK.sub("", text)
    text = _RE_SPACE_BEFORE_CJK.sub("", text)

    # 连续空行压成一个空行，保留段落边界
    text = _RE_MULTI_NEWLINE.sub("\n\n", text)

    return text.strip()


def clean_text(page_data):
    """清洗整份文档。

    Args:
        page_data: [{"page": 1, "text": "..."}, ...]（load_pdf 的返回值）

    Returns:
        list[dict]: 结构同入参，text 为清洗后的文本。
                    保持页数和页序不变，空页保留（便于页码对齐）。
                    headings（load_pdf 给的标题）也走一遍同样的清洗——标题里同样
                    有乱码（「铭牌尧车辆识别代号」→「铭牌、车辆识别代号」），
                    不清的话 chunker 在正文里定位不到它，section 就会错位。
                    其余字段原样透传。
    """
    out = []
    for item in page_data:
        cleaned = dict(item, text=clean_page_text(item.get("text") or ""))
        if "headings" in item:
            cleaned["headings"] = [
                h for h in map(clean_page_text, item["headings"]) if h
            ]
        out.append(cleaned)
    return out
