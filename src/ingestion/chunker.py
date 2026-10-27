"""按页切块：一个 chunk 只属于一页，切点落在句子边界，重叠按句子计。

三条硬约束（测试里逐条断言，改代码时别破坏）：

1. 一个 chunk 只属于一页 —— `text` 一定是该页清洗后文本的子串。
   旧实现用 `prev_suffix + curr_text` 跨页拼接，导致 55% 的 chunk 页码标错，
   这是"可追溯"的致命伤，所以这里彻底不做跨页拼接。
2. 切点落在句子边界 —— 判据是"以 。！？；结尾的 chunk 占比"，目标 >= 90%。
   旧实现按字符硬切，只有 3% 的 chunk 以句末标点结尾。
3. 内容无损 —— 每页所有非空白字符都被某个 chunk 的 [char_start, char_end) 覆盖。

坐标约定：`char_start` / `char_end` 是**相对于清洗后该页文本**的字符下标，
且恒有 `text == page_text[char_start:char_end]`。
"""

from __future__ import annotations

import re

# 中文句末标点：见到就断句
_CN_END = "。！？；"
# 半角句末标点：只有后面是空白/换行/结尾时才断句（"3.5" 里的点不算）
_EN_END = "!?;"
# 句末标点后面常跟的收尾符号，跟着一起收进本句
_CLOSERS = "）】」』”’"

# 短于这个长度的行不可能是正文折行，按块边界处理（标题 / 标签 / 表格单元格）。
# 这份说明书正文行约 18～20 字，表格单元格 2～6 字。阈值扫描结果：
#   6  → 句子平均 23.7 字，59% 以句末标点结尾（但会把 "1600km" 这类格子并进下一行）
#   8  → 句子平均 21.9 字，54%
#   12 → 句子平均 20.3 字，51%
# 取 8：表格单元格仍然断开，正文折行基本都能接上。
SHORT_LINE = 8

# 条目 / 列表 / 编号开头：出现在行首说明是新条目，必须断开
_ITEM_START = re.compile(
    r"(?:[●※·•◆◇○■□▲△▪◦]|\d{1,2}[.、)）]|[一二三四五六七八九十]{1,3}[、.])"
)

# 短于这个长度的片段视为标签（危险 / 警告 / ● / 一挡），不该成为块尾
_LABEL_MAX = 6


def split_sentences(text: str) -> list[tuple[int, int]]:
    """把一页文本切成句子，返回 [(start, end), ...] 字符区间。

    返回区间而不是字符串，是为了让调用方能算出 char_start/char_end，
    也才能做"覆盖无遗漏"的测试。区间两端已去掉空白。

    断句规则（每条都对应这份说明书里的真实情况）：

    | 触发            | 条件                                        |
    |-----------------|---------------------------------------------|
    | 。！？；        | 直接断（全角）                              |
    | ! ? ;           | 后面是空白/换行/结尾时才断（半角）          |
    | .               | 后面是空白/换行/结尾，且**前一个字符不是数字** |
    | ……              | 两个省略号之后断，单个 … 不断（语气延续）   |
    | \\n             | **仅在"硬换行"处断**，见下                  |

    换行为什么不一律断：这份说明书正文是硬折行排版的（平均每行 11 字），
    「该项是否适 / 用于您购买的车型」只是一个折行。一律断行会把每个折行当句子，
    切块照样切在半句上——实测 chunk 以句末标点结尾的比例只有 50%，和按字符硬切
    没区别。所以只在"这一行不是正文折行"时断：

    * 上一行短（< SHORT_LINE 字）——标题、标签、表格单元格；
    * 上一行以 ：/ : 结尾——标签引出内容；
    * 空行——段落边界；
    * 下一行以 ●※ 或「1.」「一、」开头——新条目。

    其余换行当空格，句子跨行继续。

    为什么句点要"前一个字符不是数字"：`3.5`、`见第 3.2 节`、`1. 通过…` 里的点
    前面都是数字，这样一条规则同时挡住了小数点和编号，不用再单独列编号规则。
    代价是 `Mr. Smith` 这类缩写会被切开——这份语料里没有，暂时不管。
    """
    spans: list[tuple[int, int]] = []
    n = len(text)
    i = 0
    start = 0
    line_start = 0  # 当前行的起始下标，用来判断"这一行是不是折行"

    while i < n:
        ch = text[i]
        cut_at = -1   # 本句的结束下标（不含）
        next_i = -1   # 下一句从哪继续扫

        if ch == "\n":
            if _is_hard_break(text, i, line_start):
                cut_at = i          # 换行本身不属于任何一句
                next_i = i + 1
            else:
                line_start = i + 1  # 软换行：当空格，句子继续
                i += 1
                continue
            line_start = i + 1
        elif ch in _CN_END:
            cut_at = i + 1
            while cut_at < n and text[cut_at] in _CLOSERS:
                cut_at += 1
            next_i = cut_at
        elif ch == "…" and i + 1 < n and text[i + 1] == "…":
            cut_at = next_i = i + 2
        elif ch in _EN_END:
            if i + 1 >= n or text[i + 1].isspace():
                cut_at = next_i = i + 1
        elif ch == ".":
            after = text[i + 1] if i + 1 < n else ""
            prev = text[i - 1] if i > 0 else ""
            if (after == "" or after.isspace()) and not prev.isdigit():
                cut_at = next_i = i + 1

        if cut_at < 0:
            i += 1
            continue

        _append_span(spans, text, start, cut_at)
        start = i = next_i

    _append_span(spans, text, start, n)
    return spans


def _is_hard_break(text: str, i: int, line_start: int) -> bool:
    """位置 i 处的换行，是"块边界"还是"正文折行"？"""
    prev = text[i - 1] if i > 0 else ""

    # 标签行：上一行以 ：结尾，例如「自动挡车辆磨合期注意事项：」
    if prev in "：:":
        return True

    # 短行：标题、标签、表格单元格
    if i - line_start < SHORT_LINE:
        return True

    # 空行：段落边界
    if i + 1 < len(text) and text[i + 1] == "\n":
        return True

    # 下一行以条目符号/编号开头
    j = i + 1
    while j < len(text) and text[j] in " \t\u3000":
        j += 1
    if j < len(text) and _ITEM_START.match(text, j):
        return True

    return False


def _append_span(spans: list[tuple[int, int]], text: str, start: int, end: int) -> None:
    """去掉两端空白后追加区间；空白区间直接丢弃。"""
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    if end > start:
        spans.append((start, end))


def _attach_labels(
    spans: list[tuple[int, int]], text: str, max_len: int = 4
) -> list[tuple[int, int]]:
    """把连续短标签合并成一个片段（「危险」+「警告」→「危险\\n警告」）。

    这份说明书的标签是独立成行的（「…顶起的车辆内。\\n危险\\n警告\\n…」）。
    不合并的话「危险」「警告」会各自成为一个"句子"，切块时随机落在两块中间。
    合并后配合 split_page 的"尾巴回退"，标签会整体移到下一块开头，跟着它
    标注的正文走。
    """
    merged: list[tuple[int, int]] = []
    i = 0
    while i < len(spans):
        start, end = spans[i]
        # 只合并"仍然很短"的标签，避免把整张表格并成一个巨型句
        while (
            end - start <= max_len
            and text[end - 1] not in _CN_END
            and i + 1 < len(spans)
        ):
            end = spans[i + 1][1]
            i += 1
        merged.append((start, end))
        i += 1
    return merged


def _split_long_spans(text: str, spans: list[tuple[int, int]], max_len: int) -> list[tuple[int, int]]:
    """把超长句子按字符硬切成 max_len 一段。

    兜底用：无标点的长表格行、整段没有断句的说明，不切会撑爆 embedding 的
    512 token 上限（中文约 1 字 1 token）。
    """
    out: list[tuple[int, int]] = []
    for start, end in spans:
        while end - start > max_len:
            out.append((start, start + max_len))
            start += max_len
        out.append((start, end))
    return out


def split_page(
    text: str,
    chunk_size: int = 420,
    overlap_sents: int = 1,
    min_chars: int = 60,
) -> list[dict]:
    """把一页文本切成若干 chunk（不含 page/section，那些在 split_text 里补）。

    做法是"句子级贪心打包"：

    1. 先切句子（split_sentences），再按字符预算 chunk_size 一句一句往里装；
    2. 下一块从上一块末尾回退 overlap_sents 句开始，而不是回退固定字符数；
    3. 页尾残余不足 min_chars 时并入上一块（只在本页内并，绝不跨页），
       整页本来就短就整页一块，绝不丢内容。
    """
    spans = split_sentences(text)
    if not spans:
        return []

    spans = _attach_labels(spans, text)
    spans = _split_long_spans(text, spans, chunk_size)

    chunks: list[dict] = []
    i = 0
    total = len(spans)

    while i < total:
        start = spans[i][0]
        j = i
        # 贪心：从第 i 句开始往后装，直到再加一句就超预算
        while j < total and spans[j][1] - start <= chunk_size:
            j += 1
        if j == i:  # 单句就超预算（_split_long_spans 已处理，这里只是兜底）
            j = i + 1

        # 尾巴回退：别让块以「危险」「警告」这类标签结尾——标签要跟着它标注的
        # 正文走，所以把它挪到下一块的开头。最多回退 2 个片段，防止把表格拆碎。
        back = 0
        while (
            j - 1 > i
            and back < 2
            and spans[j - 1][1] - spans[j - 1][0] <= _LABEL_MAX
            and text[spans[j - 1][1] - 1] not in _CN_END
        ):
            j -= 1
            back += 1

        end = spans[j - 1][1]
        chunks.append({
            "char_start": start,
            "char_end": end,
            "text": text[start:end],
        })

        if j >= total:
            break
        # 按句子回退重叠；至少前进一句，保证循环一定收敛
        i = max(j - overlap_sents, i + 1)

    # 页尾残余并入上一块（同一页内），可能连续并入多次，直到够长
    while len(chunks) > 1 and len(chunks[-1]["text"]) < min_chars:
        tail = chunks.pop()
        prev = chunks[-1]
        prev["char_end"] = tail["char_end"]
        prev["text"] = text[prev["char_start"]:prev["char_end"]]

    return chunks


def split_text(
    page_data,
    chunk_size: int = 420,
    overlap_sents: int = 1,
    min_chars: int = 60,
) -> list[dict]:
    """按页切块，返回带页码与小节的 chunk 列表。

    Args:
        page_data: load_pdf + clean_text 的输出，每项需含 page/text，
                   可选 headings（load_pdf 会提供，用于填 section）。
        chunk_size: 单块字符预算。中文约 1 字 1 token，bge-small 上限 512 token。
                    取 420 是因为页尾短块（<min_chars）会并进上一块，最坏
                    420+60=480 字，再留出 [CLS]/[SEP] 的余量；超过上限会被
                    静默截断，尾部信息直接丢失且不报错。
        overlap_sents: 相邻块重叠几句，0 表示不重叠。
        min_chars: 页尾残余短于这个长度就并入上一块。

    Returns:
        list[dict]: chunk_id / page / text / section / char_start / char_end。
                    page 只属于一页；section 缺失时继承上一页最后一个小节。
    """
    chunks: list[dict] = []
    chunk_id = 0
    section: str | None = None  # 跨页继承：本页没有标题时沿用上一页的小节

    for item in page_data:
        page = item["page"]
        text = item.get("text") or ""
        marks = _heading_marks(text, item.get("headings") or [])

        for piece in split_page(text, chunk_size, overlap_sents, min_chars):
            chunks.append({
                "chunk_id": chunk_id,
                "page": page,
                "text": piece["text"],
                "section": _section_at(marks, piece["char_start"]) or section,
                "char_start": piece["char_start"],
                "char_end": piece["char_end"],
            })
            chunk_id += 1

        if marks:
            section = marks[-1][1]

    return chunks


def _heading_marks(text: str, headings: list[str]) -> list[tuple[int, str]]:
    """把标题定位到清洗后文本里的字符偏移，返回 [(pos, title), ...]。

    loader 拿到的标题来自原始文本，清洗会改空格/修乱码，所以这里按顺序
    find 一次；找不到就退化到"去掉空格再找"，再找不到就放弃这个标题
    （section 会回退成上一页的小节，不会错位）。
    """
    marks: list[tuple[int, str]] = []
    cursor = 0

    for title in headings:
        pos = text.find(title, cursor)
        if pos < 0:
            pos = text.find(re.sub(r"\s+", "", title), cursor)
        if pos < 0:
            continue
        marks.append((pos, title))
        cursor = pos + 1

    return marks


def _section_at(marks: list[tuple[int, str]], char_start: int) -> str | None:
    """取 chunk 起点之前最近的那个标题。"""
    found = None
    for pos, title in marks:
        if pos <= char_start:
            found = title
    return found
