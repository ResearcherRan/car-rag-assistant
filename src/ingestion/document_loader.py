"""PDF 读取：按页返回正文，并顺带抽出该页的小节标题。

字号是这份说明书的"结构信号"，实测（本仓库 data/raw 下那份 209 页原厂手册）：

    8.9pt  黑体(FZY1JW)  → 正文
    11.8pt 黑体(FZHTK)   → 小节标题（磨合期 / 发动机型号和出厂编号 / 微波窗口…）
    10.4pt ArialMT       → 页脚的 "-"
    7.9pt                → 表格单元格（公里数 / 1600km / 一挡 / 20…）

所以标题不用"猜短行"，直接用字号阈值取。全文 331 行标题候选，分布在 141 页。

注意：这里只取"标题文本 + 出现顺序"，不取字符偏移。因为清洗（去页脚、修乱码、
压空格）会改变文本长度，偏移在 loader 里算了也没用；偏移交给 chunker 在清洗后的
文本上重新定位（见 chunker._heading_marks）。
"""

from __future__ import annotations

import pymupdf

# 超过这个字号的行视为小节标题。正文 8.9pt、表格 7.9pt、页脚 10.4pt 都在下面。
HEADING_MIN_SIZE = 11.0

# 字号同样是 11.8pt，但它们是"调用标签"不是小节：全文出现 125 次
# （危险 47 / 注意 45 / 警告 33）。当成 title 会让 section 变成"注意"，
# 失去意义——它们应该留在正文里，不该占用 section 字段。
CALLOUT_LABELS = frozenset({"危险", "警告", "注意"})


def load_pdf(file_path: str) -> list[dict]:
    """读取 PDF，按页返回文本与标题。

    Returns:
        list[dict]:
        [
            {
                "page"1: 1,                      # PDF 页码，从 1 开始
                "text": "第一页文本...",          # page.get_text() 的原始输出
                "headings": ["磨合期", "…"],     # 本页字号 >= HEADING_MIN_SIZE 的行
            },
            ...
        ]
    """
    document = pymupdf.open(file_path)

    pdf_pages = []

    for page_number, page in enumerate(document, start=1):
        pdf_pages.append({
            "page": page_number,
            "text": page.get_text(),
            "headings": extract_headings(page),
        })

    document.close()

    return pdf_pages


def extract_headings(page) -> list[str]:
    """抽取一页里的小节标题，按自上而下的阅读顺序返回。

    同一条标题可能被拆成多个 span（中英文字体切换），这里按行合并；
    相邻重复（同一标题跨行）只保留一次。
    """
    headings: list[str] = []

    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue
            if max(s["size"] for s in spans) < HEADING_MIN_SIZE:
                continue

            title = "".join(s["text"] for s in spans).strip()
            if not title or title in CALLOUT_LABELS:
                continue
            if not headings or headings[-1] != title:
                headings.append(title)

    return headings
