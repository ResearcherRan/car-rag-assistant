"""把文本映射成向量（BGE 中文小模型）。

两条约定，改之前先看：

1. **惰性加载**。import 本模块不加载模型——`python -m src.cli info` 这种命令
   不需要等 10 秒的模型启动。模型在第一次 encode 时才加载。
2. **query / passage 不对称**。`bge-*-zh-v1.5` 官方建议：query 侧加一条指令前缀，
   passage 侧不加。用 `is_query=True` 区分，不要在调用处手写前缀——
   前缀一旦不一致，库里存的向量和查询向量就不在同一个空间，分数全错但不会报错。

环境变量（都有默认值，换模型 / 换镜像时覆盖，别改代码）：

    EMBED_MODEL          BAAI/bge-small-zh-v1.5
    EMBED_QUERY_PREFIX   为这个句子生成表示以用于检索相关文章：
    HF_ENDPOINT          https://hf-mirror.com
    HF_HUB_OFFLINE       1
"""

from __future__ import annotations

import os

import numpy as np

MODEL_NAME = os.getenv("EMBED_MODEL", "BAAI/bge-small-zh-v1.5")
QUERY_PREFIX = os.getenv(
    "EMBED_QUERY_PREFIX", "为这个句子生成表示以用于检索相关文章："
)

_model = None


def _setup_env() -> None:
    """只在真要加载模型时设置，避免 import 阶段污染整个进程的环境。"""
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")


def get_model():
    """第一次调用时加载模型，之后复用。"""
    global _model
    if _model is None:
        _setup_env()
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME)
    return _model


def embedding_dim() -> int:
    return get_model().get_embedding_dimension()


def normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    """L2 归一化：归一化后余弦相似度 = 点积，检索只要一次矩阵乘法。"""
    vectors = np.asarray(vectors, dtype=np.float32)
    #计算向量范数
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def encode_text(texts, *, is_query: bool = False, normalize: bool = True) -> np.ndarray:
    """把若干文本编码成 (N, dim) float32；`is_query=True` 时加检索指令前缀。

    Args:
        texts: 字符串或字符串列表。
        is_query: 编码的是查询（True）还是库里的正文（False）。
        normalize: 是否做 L2 归一化。建索引和查询必须一致。
    """
    if isinstance(texts, str):
        texts = [texts]
    texts = list(texts)
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)

    if is_query and QUERY_PREFIX:
        texts = [QUERY_PREFIX + text for text in texts]

    vectors = get_model().encode(
        texts,
        batch_size=64,
        convert_to_numpy=True,
        show_progress_bar=len(texts) > 200,
    )
    vectors = np.asarray(vectors, dtype=np.float32)
    return normalize_vectors(vectors) if normalize else vectors
