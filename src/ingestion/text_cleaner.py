import re
def clean_text(text:str):
    # 清洗pdf提取后的文本
    # 去除多余的空白
    text = re.sub(r"\s+","",text)

    # 去除首尾空格
    text = text.strip()
    return text