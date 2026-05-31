# yl_rag

This project was generated using fastapi_template.

## UV

This project uses uv. It's a modern dependency management
tool.

To run the project use this set of commands:

```bash
sudo uv sync --locked
```

```bash
sudo uv run -m yl_rag
```

This will start the server on the configured host.

You can find swagger documentation at `/api/docs`.

You can read more about uv here: https://docs.astral.sh/ruff/

## Docker

You can start the project with docker using this command:

```bash
docker-compose up --build
```

If you want to develop in docker with autoreload and exposed ports add `-f deploy/docker-compose.dev.yml` to your docker command.
Like this:

```bash
docker-compose -f docker-compose.yml -f deploy/docker-compose.dev.yml --project-directory . up --build
```

This command exposes the web application on port 8000, mounts current directory and enables autoreload.

But you have to rebuild image every time you modify `uv.lock` or `pyproject.toml` with this command:

```bash
docker-compose build
```

## Project structure

```bash
$ tree "yl_rag"
yl_rag
├── conftest.py  # Fixtures for all tests.
├── __main__.py  # Startup script. Starts uvicorn.
├── services  # Package for different external services such as rabbit or redis etc.
├── settings.py  # Main configuration settings for project.
├── static  # Static content.
├── tests  # Tests for project.
└── web  # Package contains web server. Handlers, startup config.
    ├── api  # Package with all handlers.
    │   └── router.py  # Main router.
    ├── application.py  # FastAPI application configuration.
    └── lifespan.py  # Contains actions to perform on startup and shutdown.
```

## Configuration

This application can be configured with environment variables.

You can create `.env` file in the root directory and place all
environment variables here. 

All environment variables should start with "YL_RAG_" prefix.

For example if you see in your "yl_rag/settings.py" a variable named like
`random_parameter`, you should provide the "YL_RAG_RANDOM_PARAMETER" 
variable to configure the value. This behaviour can be changed by overriding `env_prefix` property
in `yl_rag.settings.Settings.Config`.

An example of .env file:
```bash
YL_RAG_RELOAD="True"
YL_RAG_PORT="8000"
YL_RAG_ENVIRONMENT="dev"
```

You can read more about BaseSettings class here: https://pydantic-docs.helpmanual.io/usage/settings/

## Pre-commit

To install pre-commit simply run inside the shell:
```bash
pre-commit install
```

pre-commit is very useful to check your code before publishing it.
It's configured using .pre-commit-config.yaml file.

By default it runs:
* mypy (validates types);
* ruff (spots possible bugs);


You can read more about pre-commit here: https://pre-commit.com/


## Running tests

If you want to run it in docker, simply run:

```bash
docker-compose run --build --rm api pytest -vv .
docker-compose down
```

For running tests on your local machine.


2. Run the pytest.
```bash
pytest -vv .
```

```bash

curl -X 'POST' \
  'http://localhost:8000/api/vi/memory/add' 
  -H 'Content-Type: application/json' 
  -d '{
  "text": "小明在2024年4月16日买了一本关于Python异步编程的书，存放在书房的第三个书架上。",
  "room": "study_room",
  "shelf": "shelf_03",
  "tags": ["小明", "Python", "异步编程", "购物"]
}'
```

```bash
curl -X 'POST' 
  'http://localhost:8000/api/vi/memory/search' 
  -H 'Content-Type: application/json' 
  -d '{
  "text": "小明最近买了什么书？",
  "id_filter": "study_room",
  "top_k": 3
}'

```

## 智能客服 RAG 数据格式与 Socket.IO 接入

本项目在保留现有 `yl_rag` 目录结构、环境变量前缀和 REST 配置的基础上，新增了客服知识库入库格式、REST 入库/问答接口，以及可供 Next.js 客户端连接的 Socket.IO 通道。

### 客服知识库入库文本格式

客服知识建议先用结构化 JSON 管理，再由服务端统一渲染成稳定的 RAG 文本块。推荐字段如下：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `doc_id` | 是 | 业务侧稳定文档 ID，例如 FAQ 编号、政策编号 |
| `tenant_id` | 是 | 租户/店铺/业务线 ID，用于检索隔离 |
| `locale` | 否 | 语言区域，默认 `zh-CN` |
| `doc_type` | 是 | `faq`、`policy`、`product`、`troubleshooting`、`workflow` |
| `title` | 是 | 方便检索的短标题 |
| `question` | 否 | FAQ 类文档的典型用户问法 |
| `answer` | 是 | 可直接回复用户的标准答案 |
| `keywords` | 否 | 同义词、实体、业务关键词 |
| `product_ids` | 否 | 关联商品/SKU/SPU ID |
| `source_url` | 否 | 原始知识来源 |
| `updated_at` | 否 | ISO-8601 更新时间 |
| `metadata` | 否 | 扩展字段，例如渠道、优先级、人工客服组 |

服务端会将上述 JSON 渲染成以下文本格式后写入现有向量库：

```text
[文档ID] faq_return_001
[租户] store_1001
[语言] zh-CN
[类型] faq
[标题] 7天无理由退货规则
[用户问题] 商品签收后多久可以申请无理由退货？
[标准答案] 自物流签收次日起7天内，商品保持完好且不影响二次销售，可在订单详情页申请无理由退货。定制商品、生鲜、拆封后影响安全或卫生的商品不支持无理由退货。
[关键词] 退货, 无理由退货, 售后, 7天
[商品ID] SKU-BOOK-001
[来源] https://example.com/help/return-policy
[更新时间] 2026-05-31T00:00:00+00:00
```

### REST 入库示例

```bash
curl -X POST 'http://localhost:8000/api/customer-service/ingest' \
  -H 'Content-Type: application/json' \
  -d '{
    "documents": [
      {
        "doc_id": "faq_return_001",
        "tenant_id": "store_1001",
        "locale": "zh-CN",
        "doc_type": "faq",
        "title": "7天无理由退货规则",
        "question": "商品签收后多久可以申请无理由退货？",
        "answer": "自物流签收次日起7天内，商品保持完好且不影响二次销售，可在订单详情页申请无理由退货。定制商品、生鲜、拆封后影响安全或卫生的商品不支持无理由退货。",
        "keywords": ["退货", "无理由退货", "售后", "7天"],
        "product_ids": ["SKU-BOOK-001"],
        "source_url": "https://example.com/help/return-policy",
        "updated_at": "2026-05-31T00:00:00+00:00"
      }
    ]
  }'
```

### REST 问答示例

```bash
curl -X POST 'http://localhost:8000/api/customer-service/chat' \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "store_1001",
    "session_id": "web-session-001",
    "message": "我签收5天了还能退货吗？",
    "top_k": 5
  }'
```

### Next.js + Socket.IO 客户端示例

安装客户端依赖：

```bash
npm install socket.io-client
```

在 Next.js 客户端组件中连接 `yl_rag`：

```tsx
"use client";

import { useEffect, useState } from "react";
import { io, Socket } from "socket.io-client";

export default function CustomerServiceChat() {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [answer, setAnswer] = useState("");

  useEffect(() => {
    const nextSocket = io("http://localhost:8000", {
      path: "/ws/socket.io",
      transports: ["websocket"],
    });

    nextSocket.on("customer:ready", () => console.log("客服已连接"));
    nextSocket.on("customer:answer", (payload) => setAnswer(payload.answer));
    nextSocket.on("customer:error", (payload) => setAnswer(payload.message));
    setSocket(nextSocket);

    return () => nextSocket.disconnect();
  }, []);

  const ask = () => {
    socket?.emit("customer:message", {
      tenant_id: "store_1001",
      session_id: "web-session-001",
      message: "我签收5天了还能退货吗？",
      top_k: 5,
    });
  };

  return (
    <main>
      <button onClick={ask}>咨询客服</button>
      <pre>{answer}</pre>
    </main>
  );
}
```

Socket.IO 事件约定：

| 方向 | 事件名 | 说明 |
| --- | --- | --- |
| 服务端 -> 客户端 | `customer:ready` | 连接成功确认 |
| 客户端 -> 服务端 | `customer:message` | 发送用户问题，字段同 REST `/chat` |
| 服务端 -> 客户端 | `customer:answer` | 返回 `answer`、`sources`、`fallback` |
| 服务端 -> 客户端 | `customer:error` | 参数错误或服务异常 |
