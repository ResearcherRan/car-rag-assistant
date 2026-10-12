import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
from sentence_transformers import SentenceTransformer #将文本映射为嵌入向量
from sklearn.metrics.pairwise import cosine_similarity #计算向量的相似度
model = SentenceTransformer(
    "BAAI/bge-small-zh-v1.5"
)
def encode_text(texts):
    embeddings = model.encode(texts)
    return embeddings
