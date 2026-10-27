"""索引的落盘、加载与过期检查。

目录结构（`data/index/`，加进 .gitignore，用 `build` 重建）：

    chunks.jsonl    每行一个 chunk（UTF-8 JSON）
    vectors.npy     float32 (N, dim)，已 L2 归一化
    meta.json       元信息：PDF 指纹、模型名、切块参数、统计

为什么要 meta：`ask` 要能用一句话回答"这个索引还是不是这份 PDF 建的"。
PDF 换版本、`chunk_size` 改了、模型换了，索引都必须重建——否则检索结果
没法解释，面试官问"你这个数怎么来的"也答不上来。

本模块只依赖 numpy，不加载模型，所以测试和 `info` 命令都是秒回的。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# 索引格式版本。字段语义变了就 +1，旧索引会被判过期而不是读出乱码。
SCHEMA = 1

CHUNKS_FILE = "chunks.jsonl"
VECTORS_FILE = "vectors.npy"
META_FILE = "meta.json"

DEFAULT_INDEX_DIR = Path("data/index")


# ---------------------------------------------------------------------------
# 指纹
# ---------------------------------------------------------------------------
def sha256_file(path: str | Path, block: int = 1 << 20) -> str:
    """文件 sha256。13MB 的 PDF 大约 20ms，够快，不需要缓存。"""
    digest = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(block), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# 写
# ---------------------------------------------------------------------------
def build_index(
    index_dir: str | Path,
    *,
    chunks: list[dict],
    vectors: np.ndarray,
    pdf_path: str | Path | None = None,
    model_name: str,
    chunk_params: dict,
    query_prefix: str = "",
) -> dict:
    """把 chunk 与向量落盘，返回写进去的 meta。

    Args:
        chunks: `chunker.split_text` 的输出，每条至少含 chunk_id/page/text。
        vectors: (N, dim) float32，N 必须等于 len(chunks)。
        pdf_path: 用来记录 PDF 指纹；不传就只记录 None（测试用）。
        model_name: 生成这些向量的模型，换了模型必须重建。
        chunk_params: 切块参数（chunk_size/overlap_sents/min_chars），
                      改了同样必须重建。
    """
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.ndim != 2:
        raise ValueError(f"vectors 应该是二维 (N, dim)，实际 shape={vectors.shape}")
    if len(chunks) != vectors.shape[0]:
        raise ValueError(
            f"chunk 数 {len(chunks)} 与向量行数 {vectors.shape[0]} 不一致，"
            "八成是编码时漏了/多传了文本"
        )
    if len(chunks) == 0:
        raise ValueError("chunks 为空，没什么可建的")

    index_dir = Path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)

    with open(index_dir / CHUNKS_FILE, "w", encoding="utf-8", newline="\n") as fp:
        for chunk in chunks:
            fp.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    np.save(index_dir / VECTORS_FILE, vectors, allow_pickle=False)

    meta = {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "pdf": {
            "path": str(pdf_path) if pdf_path is not None else None,
            "sha256": sha256_file(pdf_path) if pdf_path is not None else None,
        },
        "model": {
            "name": model_name,
            "dim": int(vectors.shape[1]),
            "normalized": True,
            "query_prefix": query_prefix,
        },
        "chunk": dict(chunk_params),
        "counts": {
            "chunks": len(chunks),
            "chars": sum(len(c.get("text") or "") for c in chunks),
            "pages": len({c["page"] for c in chunks}),
        },
    }
    _write_meta(index_dir, meta)
    return meta


def _write_meta(index_dir: Path, meta: dict) -> None:
    with open(index_dir / META_FILE, "w", encoding="utf-8", newline="\n") as fp:
        json.dump(meta, fp, ensure_ascii=False, indent=2)
        fp.write("\n")


# ---------------------------------------------------------------------------
# 读
# ---------------------------------------------------------------------------
def index_exists(index_dir: str | Path = DEFAULT_INDEX_DIR) -> bool:
    index_dir = Path(index_dir)
    return all(
        (index_dir / name).exists()
        for name in (CHUNKS_FILE, VECTORS_FILE, META_FILE)
    )


def load_meta(index_dir: str | Path = DEFAULT_INDEX_DIR) -> dict:
    path = Path(index_dir) / META_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"{path} 不存在。先建索引：python -m src.cli build"
        )
    with open(path, encoding="utf-8") as fp:
        return json.load(fp)


def load_index(index_dir: str | Path = DEFAULT_INDEX_DIR) -> dict:
    """加载索引，返回 {"chunks": [...], "vectors": ndarray, "meta": {...}}。

    顺带做一致性检查：chunk 行数必须等于向量行数，维度必须等于 meta 记录。
    这类不一致只会在"建了一半"或"手改过文件"时出现，早报错比检索出怪结果好。
    """
    index_dir = Path(index_dir)
    if not index_exists(index_dir):
        raise FileNotFoundError(
            f"{index_dir} 下缺少索引文件（chunks.jsonl / vectors.npy / meta.json）。"
            "先建索引：python -m src.cli build"
        )

    meta = load_meta(index_dir)

    chunks: list[dict] = []
    with open(index_dir / CHUNKS_FILE, encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))

    vectors = np.load(index_dir / VECTORS_FILE, allow_pickle=False)

    if len(chunks) != vectors.shape[0]:
        raise ValueError(
            f"索引损坏：chunks.jsonl 有 {len(chunks)} 行，"
            f"vectors.npy 有 {vectors.shape[0]} 行。删掉 {index_dir} 重建。"
        )
    expected_dim = meta.get("model", {}).get("dim")
    if expected_dim and vectors.shape[1] != expected_dim:
        raise ValueError(
            f"索引损坏：向量维度 {vectors.shape[1]} 与 meta 记录的 {expected_dim} 不一致。"
            f"删掉 {index_dir} 重建。"
        )

    return {"chunks": chunks, "vectors": vectors, "meta": meta} 


# ---------------------------------------------------------------------------
# 过期检查
# ---------------------------------------------------------------------------
def staleness(
    meta: dict,
    *,
    pdf_path: str | Path | None = None,
    model_name: str | None = None,
    chunk_params: dict | None = None,
) -> list[str]:
    """返回"索引已经过期"的原因列表；空列表表示可放心用。

    这是 `build --force` 之外的安全网：改了切块参数却忘了重建，是最容易发生的
    事故——症状是检索结果"看起来还行但数字不对"，很难查。
    """
    reasons: list[str] = []

    if meta.get("schema") != SCHEMA:
        reasons.append(f"索引格式版本 {meta.get('schema')} != 当前 {SCHEMA}")

    if pdf_path is not None:
        recorded = (meta.get("pdf") or {}).get("sha256")
        if not recorded:
            reasons.append("索引没有记录 PDF 指纹")
        elif Path(pdf_path).exists() and sha256_file(pdf_path) != recorded:
            reasons.append("PDF 文件变了（sha256 不一致）")

    if model_name is not None:
        recorded = (meta.get("model") or {}).get("name")
        if recorded != model_name:
            reasons.append(f"embedding 模型变了：索引是 {recorded}，当前是 {model_name}")

    if chunk_params is not None:
        recorded = meta.get("chunk") or {}
        diff = {
            key: (recorded.get(key), value)
            for key, value in chunk_params.items()
            if recorded.get(key) != value
        }
        if diff:
            detail = "，".join(f"{k}: 索引 {old} / 当前 {new}" for k, (old, new) in diff.items())
            reasons.append(f"切块参数变了（{detail}）")

    return reasons
