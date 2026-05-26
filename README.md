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

## 新增接口说明（文档上传 + 小说创作）

### 1) 单文件上传入库（自动 sha256 去重）
```bash
curl -X POST 'http://localhost:8000/api/memory/upload/file?id=user_1&role=user' \
  -F 'file=@./demo.pdf'
```

### 2) 文件夹批量上传（支持 txt/md/docx/pdf）
```bash
curl -X POST 'http://localhost:8000/api/memory/upload/folder' \
  -H 'Content-Type: application/json' \
  -d '{"folder_path":"/data/books","id":"user_1","role":"user"}'
```

### 3) 从 txt 小说提取大纲、人物、时间线
```bash
curl -X POST 'http://localhost:8000/api/novel/extract' \
  -H 'Content-Type: application/json' \
  -d '{"text":"这里放整本 txt 小说文本..."}'
```

### 4) 根据文案和大纲生成章节（每次返回一章）
```bash
curl -X POST 'http://localhost:8000/api/novel/generate' \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"主角在暴雨夜追查失踪案","outline":{"characters":["陈默","林晚"],"timeline":["夜里","凌晨"]},"chapter_no":1}'
```

### 5) 根据原文做二次创作（每次返回一章）
```bash
curl -X POST 'http://localhost:8000/api/novel/rewrite' \
  -H 'Content-Type: application/json' \
  -d '{"source_text":"原章节文本...","outline":{"characters":["陈默"],"timeline":["傍晚","夜里"]},"chapter_no":2}'
```

### 跨平台依赖说明
- Linux / Windows 都可使用 `python-docx`（解析 docx）和 `pypdf`（解析 pdf），避免因平台不同引入不同库导致功能不一致。
- 若环境缺少依赖，接口会返回明确错误信息（例如 `python-docx is not installed`）。
