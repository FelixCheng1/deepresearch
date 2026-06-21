# DeepResearch

基于 FastAPI、LangChain、LangGraph 和 Vue 的本地深度研究工作台。后端用 OpenAI-compatible Chat Model 接入 Ollama、LM Studio、DeepSeek 或其他兼容服务；前端展示文档库、LangGraph 工作流、任务状态、引用来源、工具调用和最终报告。

当前版本已经支持上传 `.txt` / `.md` / `.pdf` / `.docx`，后台解析、切块入库，并在 `RAG_ENABLED=true` 时把文档检索结果注入 LangGraph 的 `retrieve_documents` 节点。没有 `DATABASE_URL` 时使用内存仓库；配置 Postgres 后保存研究历史、文档库和 embedding 字段。

## 功能概览

- LangGraph 主流程：`plan_tasks -> dispatch_tasks -> run_task 并行 -> join_tasks -> write_report -> persist_report -> END`
- 子任务流程：准备任务、可选文档检索、网页搜索、任务总结、任务持久化
- SSE 流式事件：任务清单、节点状态、来源、工具调用、任务总结、最终报告
- 文档库：上传 `.txt` / `.md` / `.pdf` / `.docx`、后台解析、列表、详情、chunk 预览、删除、失败重试
- 持久化：内存仓库或 Postgres + pgvector
- RAG：轻量文本排序；配置 embedding 后写入向量字段并参与混合排序

## 目录结构

```text
backend/                 FastAPI + LangGraph 后端
  src/
    agent.py             DeepResearchAgent 入口
    main.py              HTTP/SSE API
    config.py            环境变量配置
    services/            图编排、检索、搜索、仓库、数据库等边界
  migrations/            Alembic migration
  tests/                 后端测试
frontend/                Vue + Vite 前端
docker-compose.yml       本地 Postgres + pgvector
notes/                   研究过程笔记输出目录
```

## 环境要求

- Python 3.10+
- Node.js 18+
- npm
- 可选：Docker / Docker Compose，用于本地 Postgres + pgvector

## 后端配置

复制示例配置：

```powershell
Copy-Item backend\.env.example backend\.env
```

至少配置一个 OpenAI-compatible LLM：

```text
LLM_PROVIDER=custom
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_API_KEY=ollama
LLM_MODEL_ID=llama3.2
```

常用环境变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PORT` | `8000` | 后端端口 |
| `LLM_BASE_URL` | 空 | OpenAI-compatible API base URL |
| `LLM_API_KEY` | 空 | API Key；本地服务可填占位值 |
| `LLM_MODEL_ID` | `LOCAL_LLM` / `llama3.2` | 模型 ID |
| `SEARCH_API` | `duckduckgo` | `duckduckgo`、`tavily`、`perplexity`、`searxng`、`advanced` |
| `DATABASE_URL` | 空 | 配置后启用 Postgres 仓库 |
| `RAG_ENABLED` | `false` | 是否启用文档库检索 |
| `RAG_TOP_K` | `5` | 每个任务最多注入的文档片段数 |
| `RAG_CONTEXT_MAX_CHARS` | `6000` | 每个任务最多注入的文档上下文字符数 |
| `NOTES_WORKSPACE` | `./notes` | 任务笔记和报告输出目录 |

## 启动后端

```powershell
cd backend
uv sync
uv run python src/main.py
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/healthz
```

也可以从项目根目录直接运行：

```powershell
backend\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend\src --host 127.0.0.1 --port 8000
```

## 启动数据库

数据库是可选的；不配置 `DATABASE_URL` 时使用内存仓库。

```powershell
docker compose up -d
$env:DATABASE_URL="postgresql+psycopg://deepresearch:deepresearch@127.0.0.1:5432/deepresearch"
cd backend
uv run alembic upgrade head
```

如果要启用文档 RAG：

```powershell
$env:RAG_ENABLED="true"
```

如需 embedding，额外配置：

```text
EMBEDDING_BASE_URL=https://your-compatible-embedding-api/v1
EMBEDDING_API_KEY=your-key
EMBEDDING_MODEL=text-embedding-3-small
```

历史 chunk 回填：

```powershell
cd backend
uv run python src/embedding_cli.py --backfill
```

## 启动前端

前端默认请求 `http://localhost:8000`。如果你改了后端端口，再创建 `frontend/.env.local`：

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

启动：

```powershell
cd frontend
npm install
npm run dev
```

打开 Vite 输出的地址，通常是 `http://localhost:5173`。

## 使用流程

1. 打开前端页面。
2. 上传 `.txt` / `.md` / `.pdf` / `.docx` 文档，等待状态变成“可检索”。
3. 输入研究主题。
4. 点击“开始研究”。
5. 工作台会展示 LangGraph 节点状态、任务清单、引用来源、工具调用和最终报告。

## API 摘要

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/healthz` | 健康检查 |
| `POST` | `/research` | 非流式研究 |
| `POST` | `/research/stream` | SSE 流式研究 |
| `GET` | `/research/runs?limit=20` | 研究历史列表 |
| `GET` | `/research/runs/{run_id}` | 研究历史详情 |
| `POST` | `/documents/upload` | 上传文档 |
| `GET` | `/documents` | 文档列表 |
| `GET` | `/documents/{document_id}` | 文档详情和 chunks |
| `POST` | `/documents/{document_id}/retry` | 重试失败文档解析 |
| `DELETE` | `/documents/{document_id}` | 删除文档和 chunks |

## 验证

```powershell
cd backend
uv run pytest
```

```powershell
cd frontend
npm run build
```

## 开发注意事项

- 不要提交 `.env`、`frontend/.env.local`、`notes/`、`node_modules/`、`.venv/`。
- 没有 `DATABASE_URL` 时，后端使用内存仓库，适合快速演示。
- 配置 Postgres 后先跑 `uv run alembic upgrade head`。
- 当前 FastAPI `on_event` 有 deprecated warning，不影响运行；真要清 warning 再换 lifespan。
