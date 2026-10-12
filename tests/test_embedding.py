from src.retrieval.embedding import encode_text
from sklearn.metrics.pairwise import cosine_similarity #计算向量的相似度
texts = [
    "汽车胎压报警怎么办",
    "轮胎压力监测系统异常如何处理",
    "如何打开空调"
]


vectors = encode_text(texts)
score = cosine_similarity(
    vectors
)
print(vectors.shape)
print(score)
