# Car RAG Assistant

一个面向汽车说明书和汽车知识文档的智能问答系统。

本项目希望利用 RAG（Retrieval-Augmented Generation，检索增强生成）技术，让用户能够使用自然语言查询汽车说明书中的内容。

例如用户可以提出：

- 胎压报警灯亮了怎么办？
- 如何开启自动驻车？
- 车辆亏电之后怎么进行辅助启动？
- 自适应巡航应该如何设置？

系统会先从汽车说明书中检索与问题相关的内容，再让大语言模型根据检索到的文档生成答案，并返回对应的文档来源。

## 1. Project Goal

本项目主要解决传统汽车说明书查询效率较低的问题。

传统说明书通常具有以下特点：

- 文档较长，可能包含数百页内容；
- 用户不一定知道说明书中的准确术语；
- 使用关键词搜索可能无法找到语义相关的内容；
- 大语言模型直接回答可能产生幻觉。

因此，本项目计划构建一个基于 Hybrid Retrieval + RAG 的汽车知识问答系统。

系统将结合：

- BM25 关键词检索
- Dense Retrieval 向量语义检索
- Hybrid Retrieval 混合检索
- Reranker 重排序
- Large Language Model 生成答案

最终实现更加准确、可追溯的汽车知识问答。

## 2. System Workflow

系统整体流程：

```text
汽车说明书 / FAQ 文档
        ↓
文档解析
        ↓
文本切分 Chunking
        ↓
建立 BM25 索引
        +
建立向量索引
        ↓

用户问题
        ↓
BM25 Retrieval
        +
Dense Retrieval
        ↓
Hybrid Retrieval
        ↓
Reranker
        ↓
Top-K Relevant Documents
        ↓
LLM
        ↓
Answer + Source Citation
```

## 3. Planned Features

计划实现以下功能：

### Document Processing

- PDF / TXT 文档读取
- 文本清洗
- 文档切块（Chunking）
- 保存文档页码、标题等 metadata

### Retrieval

实现并比较不同的检索方法：

1. BM25 Retrieval
2. Dense Retrieval
3. Hybrid Retrieval
4. Hybrid Retrieval + Reranker

### Generation

将检索到的相关文档作为上下文提供给大语言模型。

模型需要：

- 根据文档内容回答问题；
- 尽可能避免使用文档之外的信息；
- 返回对应的参考来源。

### Evaluation

使用以下指标评估检索效果：

- Recall@K
- MRR
- nDCG@K

计划比较：

```text
BM25
Dense Retrieval
Hybrid Retrieval
Hybrid Retrieval + Reranker
```

在汽车知识查询任务中的效果差异。

### API

后续计划使用 FastAPI 将系统封装成 API，例如：

```text
POST /search
POST /answer
POST /ingest
GET /health
```

### Deployment

后续计划使用 Docker 对项目进行容器化部署。

## 4. Project Structure

```text
car-rag-assistant/
│
├── README.md
├── requirements.txt
├── .gitignore
├── main.py
│
├── data/
│
├── src/
│   ├── __init__.py
│   │
│   ├── ingestion/
│   │   └── __init__.py
│   │
│   ├── retrieval/
│   │   └── __init__.py
│   │
│   ├── generation/
│   │   └── __init__.py
│   │
│   └── evaluation/
│       └── __init__.py
│
└── tests/
```

各模块预计负责：

```text
ingestion/
文档解析、数据清洗、文本切块

retrieval/
BM25、向量检索、Hybrid Retrieval、Reranker

generation/
调用大语言模型生成答案

evaluation/
Recall@K、MRR、nDCG 等评测代码
```

## 5. Development Plan

### Stage 1

完成基础 RAG：

```text
Document
↓
Chunk
↓
Embedding
↓
Vector Retrieval
↓
LLM
```

### Stage 2

增加 BM25 Retrieval：

```text
BM25
+
Dense Retrieval
```

### Stage 3

实现 Hybrid Retrieval 和 Reranker。

### Stage 4

构建汽车知识查询测试集，并比较不同检索方法的效果。

### Stage 5

使用 FastAPI 和 Docker 完成服务化和部署。

## 6. Current Status

项目目前处于初始化阶段。

当前任务：

- [x] 创建项目仓库
- [x] 设计项目目录结构
- [ ] 准备汽车知识文档
- [ ] 实现文档解析
- [ ] 实现文本 Chunking
- [ ] 实现 Dense Retrieval
- [ ] 实现基础 RAG
- [ ] 实现 BM25
- [ ] 实现 Hybrid Retrieval
- [ ] 实现 Reranker
- [ ] 构建评测数据集
- [ ] 实现检索评测
- [ ] FastAPI 服务化
- [ ] Docker 部署

## 7. Tech Stack

计划使用：

- Python
- PyTorch
- Sentence Transformers
- FAISS / Qdrant / Chroma
- BM25
- FastAPI
- Docker
- Large Language Model API / Local LLM

具体技术方案可能随着项目开发继续调整。