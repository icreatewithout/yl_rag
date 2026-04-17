# YL-RAG

一个基于 FastAPI + Qdrant 的轻量级记忆检索服务，支持“写入记忆 + 语义检索 + 重排 + 图关系持久化”。

## 1. 项目定位

YL-RAG 主要用于“可检索记忆”的业务场景：
- 把用户对话/事件写入长期记忆；
- 按语义相似度召回历史内容；
- 结合时间衰减与重排获得更稳的 Top-K 结果；
- 使用图谱结构记录记忆与标签/会话空间关系。

---

## 2. 整体设计方案（Architecture）

### 2.1 核心模块

- **API 层（FastAPI）**：对外提供写入与检索接口。  
- **EmbeddingService**：负责向量化与重排，并提供离线降级能力（模型不可用时用哈希向量与词重合打分）。  
- **QdrantService**：负责向量存储与检索；当 Qdrant 不可用时自动切换本地内存模式，避免服务不可启动。  
- **MemoryGraph**：使用 NetworkX 维护记忆-房间-标签关系图，后台定时持久化。  

### 2.2 检索流程

1. 输入 query，生成 query 向量；
2. 在 Qdrant（或本地 fallback）召回候选；
3. 应用时间衰减分数（近期信息更高）；
4. 调用 rerank 对候选进行二次排序；
5. 返回 top_k 结果。

### 2.3 可用性与容错

- 模型下载失败时，服务仍可启动并支持基础检索（离线 fallback）；
- Qdrant 不可达时，切换本地存储模式；
- API 层统一异常返回，避免内部栈信息直接泄漏。

---

## 3. 安装与启动

### 3.1 本地（推荐 uv）

```bash
uv sync
uv run -m yl_rag
```

启动后默认地址：`http://127.0.0.1:8000`  
文档地址：`/api/docs`

### 3.2 Docker

```bash
docker-compose up --build
```

开发模式：

```bash
docker-compose -f docker-compose.yml -f deploy/docker-compose.dev.yml --project-directory . up --build
```

---

## 4. 配置说明

通过 `.env.<env>` 文件配置，变量前缀为 `YL_RAG_`。

示例：

```bash
YL_RAG_ENVIRONMENT=dev
YL_RAG_HOST=127.0.0.1
YL_RAG_PORT=8000
YL_RAG_QDRANT_HOST=localhost
YL_RAG_QDRANT_PORT=6333
YL_RAG_COLLECTION_NAME=memory_palace
YL_RAG_EMBED_BATCH_SIZE=32
YL_RAG_RERANK_BATCH_SIZE=32
```

---

## 5. 使用说明（API）

### 5.1 写入记忆

`POST /api/memory/add`

```json
{
  "text": "小明在2026年4月买了一本 Python 异步编程书籍",
  "id": "user_001",
  "role": "user",
  "tags": ["小明", "Python", "购物"]
}
```

### 5.2 检索记忆

`POST /api/memory/search`

```json
{
  "text": "小明最近买了什么书？",
  "id_filter": "user_001",
  "top_k": 3
}
```

---

## 6. 可以支撑哪些业务工作

- **智能客服记忆**：保存用户历史问题、偏好、订单上下文，支持后续精准回复。
- **销售/顾问跟进**：记录客户需求、时间线事件、关注点，检索出“最近关键事项”。
- **知识助理**：对企业知识片段进行语义检索，结合标签做更细粒度召回。
- **个人助理/待办回顾**：把对话中的事实与事项写入长期记忆，按人/主题/时间追溯。
- **多会话场景记忆隔离**：基于 `id_filter` 做租户或用户级隔离检索。

---

## 7. 测试

```bash
uv run pytest -q
```

