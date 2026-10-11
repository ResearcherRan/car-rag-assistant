import pymupdf

def load_pdf(file_path: str):
    """
    读取 PDF 文件，并按页返回文本。

    Returns:
        list[dict]:
        [
            {
                "page": 1,
                "text": "第一页文本..."
            },
            ...
        ]
    """
    document = pymupdf.open(file_path)

    pdf_pages = []

    for page_number, page in enumerate(document, start=1):
        text = page.get_text()

        pdf_pages.append({
            "page": page_number,
            "text": text
        })

    document.close()

    return pdf_pages