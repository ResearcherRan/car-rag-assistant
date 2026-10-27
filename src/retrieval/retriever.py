"""从索引里取 top_k：余弦相似度 + 重叠去重。

两个必须做对的地方：

1. **归一化后点积**。建索引时向量已经 L2 归一化，查询向量也一样，所以
   `vectors @ query` 就是余弦相似度，一次矩阵乘法，不需要 sklearn。
2. **重叠去重**。切块有 1 句重叠，相邻两块会共享同一段文字。不去重的话
   top5 里可能出现两条 90% 相同的文本，白占名额——RAG 里这叫"上下文浪费"。

坐标约定：重叠判断只看同一页内 `[char_start, char_end)` 的区间交叠比例，
不比对文本，O(k²) 且 k 很小。
"""

from __future__ import annotations

import numpy as np

# 两条命中来自同一页、且较短的区间有超过一半被覆盖，就认为重复
DEFAULT_OVERLAP_THRESHOLD = 0.5

def cosine_scores(query_vector: np.ndarray, vectors: np.ndarray) -> np.ndarray:
    """(N, dim) × (dim,) → (N,) 余弦相似度；对未归一化的输入也安全。"""
    query_vector = np.asarray(query_vector, dtype=np.float32).ravel()
    vectors = np.asarray(vectors, dtype=np.float32)

    q_norm = np.linalg.norm(query_vector)
    v_norms = np.linalg.norm(vectors, axis=1)
    denom = v_norms * (q_norm if q_norm else 1.0)
    denom[denom == 0] = 1.0
    return (vectors @ query_vector) / denom


def _overlaps(candidate: dict, picked: dict, threshold: float) -> bool:
    if candidate.get("page") != picked.get("page"):
        return False
    a_start, a_end = candidate.get("char_start"), candidate.get("char_end")
    b_start, b_end = picked.get("char_start"), picked.get("char_end")
    if None in (a_start, a_end, b_start, b_end):
        return False

    overlap = min(a_end, b_end) - max(a_start, b_start)
    if overlap <= 0:
        return False
    shorter = min(a_end - a_start, b_end - b_start)
    return shorter > 0 and overlap / shorter > threshold


def select_topk(
    chunks: list[dict],
    similarities: np.ndarray,
    top_k: int = 5,
    *,
    min_score: float | None = None,
    overlap_threshold: float = DEFAULT_OVERLAP_THRESHOLD,
) -> list[dict]:
    """按分数取 top_k，跳过互相重叠的块。

    Args:
        chunks: 与 similarities 一一对应的 chunk 列表。
        similarities: 每个 chunk 的相似度。
        top_k: 最多返回几条。
        min_score: 低于这个分数直接截断（用来做"拒答"的检索侧判断）。
        overlap_threshold: 同页区间交叠比例超过多少算重复。

    Returns:
        list[dict]: chunk_id / page / section / text / char_start / char_end / score。
    """
    similarities = np.asarray(similarities)
    order = np.argsort(-similarities)
    picked: list[dict] = []

    for idx in order:
        score = float(similarities[idx])
        if min_score is not None and score < min_score:
            break
        chunk = chunks[int(idx)]
        if any(_overlaps(chunk, hit, overlap_threshold) for hit in picked):
            continue
        picked.append({
            "chunk_id": chunk["chunk_id"],
            "page": chunk["page"],
            "section": chunk.get("section"),
            "text": chunk["text"],
            "char_start": chunk.get("char_start"),
            "char_end": chunk.get("char_end"),
            "score": score,
        })
        if len(picked) >= top_k:
            break

    return picked


def retrieve(query_vector, chunk_vectors, chunks, top_k: int = 3) -> list[dict]:
    """旧接口，保留兼容：返回带 `similarity_score` 字段的命中列表。

    新代码请用 `select_topk`——它多了去重和阈值。
    """
    similarities = cosine_scores(query_vector, chunk_vectors)
    hits = select_topk(chunks, similarities, top_k)
    for hit in hits:
        hit["similarity_score"] = hit.pop("score")
    return hits
