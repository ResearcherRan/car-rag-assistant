import re
def clean_text(page_data):
    clean_data = []
    # 清洗pdf提取后的文本
    # 去除多余的空白
    for s in page_data:
        text = s["text"]
        page = s["page"]
        text = re.sub(r"\s+","",text)
    # 去除首尾空格
        text = text.strip()
        clean_data.append({
            "page":page,
            "text":text
        })
    return clean_data