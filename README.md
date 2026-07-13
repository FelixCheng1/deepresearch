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
- RAG 评测：内置小规模检索评测集，输出 Recall@K 和 MRR

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

可选增强能力：

```text
RAG_RERANK_ENABLED=false
RAG_RERANK_MODEL=BAAI/bge-reranker-base
RAG_RERANK_TOP_N=20
PDF_OCR_ENABLED=false
PDF_OCR_LANGUAGE=chi_sim+eng
PDF_OCR_DPI=200
PDF_OCR_MAX_PAGES=20
```

Cross-Encoder rerank 需要额外安装 `sentence-transformers`，首次启用会下载模型。PDF OCR 需要额外安装 `pdf2image`、`pytesseract`、`pillow`，并在系统中安装 Tesseract 和 Poppler；Windows 可通过 `TESSERACT_CMD`、`POPPLER_PATH` 指定路径。

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
| `GET` | `/research/runs/{run_id}` | 研究历史详情（任务、来源、报告、工具调用） |
| `POST` | `/documents/upload` | 上传文档 |
| `GET` | `/documents` | 文档列表 |
| `GET` | `/documents/{document_id}` | 文档详情和 chunks |
| `POST` | `/documents/{document_id}/retry` | 重试失败文档解析 |
| `DELETE` | `/documents/{document_id}` | 删除文档和 chunks |

## 验证

```powershell
cd backend
uv run pytest
uv run alembic heads
uv run python src/rag_eval_cli.py
uv run python src/rag_eval_cli.py --json
uv run python src/rag_eval_cli.py --dataset eval/rag-dataset.json --fail-below-recall 0.8 --fail-below-mrr 0.6
```

默认 RAG 评测使用内置 smoke 数据，不依赖数据库、LLM、embedding API 或网络，只用于验证评测链路，不代表生产检索质量。正式比较应传入版本化 JSON 数据集；格式和门禁用法见 [RAG 评测说明](docs/rag-evaluation.md)。指标含义：

- `Recall@K`：前 K 个检索结果中是否包含期望文档，越高表示召回越稳定。
- `MRR`：期望文档排名的倒数均值，越高表示正确文档越靠前。
- `expected_terms_coverage`：期望证据词是否出现在目标文档召回片段中。

```powershell
cd frontend
.\node_modules\.bin\vue-tsc.cmd --noEmit
npm run build
```
## 最终验收清单

- 上传 `.txt` / `.md` / `.pdf` / `.docx` 后，文档状态能从“解析中”变为“可检索”。
- 上传空 PDF 或无法解析文档时，状态显示“解析失败”，并可点击重试。
- 开始研究后，LangGraph 工作流一开始就显示，且可以收起/展开。
- 引用来源中出现本地 `document://...#chunk-...` 时，前端标记为 RAG 命中片段。
- 研究历史详情包含按 `event_id` 排序的结构化 `tool_calls`，可用于审计和回放。
- 最终报告以 Markdown 样式渲染，标题、列表、代码和链接可读。
- 后端测试、Alembic head、RAG 检索评测、前端类型检查通过。

## 数据库说明

如果你之前主要使用 MySQL，可以先看 [docs/database.md](docs/database.md)。里面按本项目实际表结构解释了 PostgreSQL、SQLAlchemy、Alembic 和 pgvector 的作用。

## 开发注意事项

- 不要提交 `.env`、`frontend/.env.local`、`notes/`、`node_modules/`、`.venv/`。
- 没有 `DATABASE_URL` 时，后端使用内存仓库，适合快速演示。
- 配置 Postgres 后先跑 `uv run alembic upgrade head`。
- 后端使用 FastAPI lifespan 管理后台文档 worker 的启动和停止。
