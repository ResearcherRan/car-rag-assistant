def split_text(page_data, chunk_size=300, overlap=30):
    chunks = []
    chunk_id = 0
    prev_suffix = ""

    for w in page_data:
        curr_text = w["text"]
        page = w["page"]
        combine_text = prev_suffix + curr_text
        start = 0
        # 滑动窗口：只生成完整达到chunk_size的块
        while start + chunk_size <= len(combine_text):
            end = start + chunk_size
            chunk = combine_text[start:end]
            chunks.append({
                "chunk_id": chunk_id,
                "page": page,
                "text": chunk
            })
            chunk_id += 1
            start = end - overlap
        
        # 循环结束，剩下不足chunk_size的残余，不入库，作为下一页的前缀
        remain = combine_text[start:]
        prev_suffix = remain

    # 全部页面处理完毕，如果还有残余文本，生成最后的chunk入库
    if len(prev_suffix) > 0:
        chunks.append({
            "chunk_id": chunk_id,
            "page": page_data[-1]["page"],
            "text": prev_suffix
        })
    return chunks
