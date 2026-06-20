# DeepResearch

基于 FastAPI、LangChain、LangGraph 和 Vue 的本地深度研究工作台。后端使用 OpenAI-compatible Chat Model 作为 LLM 接入层，支持 Ollama、LM Studio、DeepSeek 或其他兼容 `/v1/chat/completions` 的服务；前端提供研究主题输入、LangGraph 工作流可视化、任务状态、引用来源、工具调用记录、最终报告和轻量文档库。

当前 RAG 处于文本检索阶段：支持上传 `.txt` / `.md`，自动切块入库，并在 `RAG_ENABLED=true` 时通过轻量 BM25 风格文本检索为 LangGraph 的 `retrieve_documents` 节点提供上下文。暂不支持 PDF、embedding、pgvector vector 列或多用户知识库。

## 功能概览

- LangGraph 主流程：`plan_tasks -> dispatch_tasks -> run_task 并行 -> join_tasks -> write_report -> persist_report -> END`
- 子任务流程：准备任务、可选文档检索、网页搜索、任务总结、任务持久化
- SSE 流式事件：任务清单、节点状态、来源、工具调用、任务总结、最终报告
- 三栏前端工作台：研究信息、DAG/任务/报告、节点详情/引用/工具调用
- 文档库：上传 `.txt` / `.md`、列表、详情、chunk 预览、删除
- 持久化：无 `DATABASE_URL` 时使用内存仓库；配置后使用 Postgres + pgvector 保存研究历史和文档库

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

后端从环境变量读取配置。至少需要配置一个 OpenAI-compatible LLM：

```powershell
$env:LLM_BASE_URL="http://127.0.0.1:11434/v1"
$env:LLM_API_KEY="ollama"
$env:LLM_MODEL_ID="llama3.2"
```

常用环境变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LLM_BASE_URL` | 空 | OpenAI-compatible API base URL |
| `LLM_API_KEY` | 空 | API Key；本地服务可填占位值 |
| `LLM_MODEL_ID` | `LOCAL_LLM` / `llama3.2` | 模型 ID |
| `SEARCH_API` | `duckduckgo` | 可选：`duckduckgo`、`tavily`、`perplexity`、`searxng`、`advanced` |
| `DATABASE_URL` | 空 | 配置后启用 Postgres 仓库 |
| `RAG_ENABLED` | `false` | 是否启用文档库检索 |
| `RAG_TOP_K` | `5` | 每个任务最多注入的文档片段数 |
| `RAG_CONTEXT_MAX_CHARS` | `6000` | 每个任务最多注入的文档上下文字符数 |
| `RAG_MIN_SCORE` | `0.1` | 文档片段最低匹配分 |
| `NOTES_WORKSPACE` | `./notes` | 任务笔记和报告输出目录 |
| `LANGSMITH_TRACING` | 由环境决定 | 可关闭为 `false`，不影响主流程 |

如果使用 LM Studio：

```powershell
$env:LLM_BASE_URL="http://127.0.0.1:1234/v1"
$env:LLM_API_KEY="lm-studio"
$env:LLM_MODEL_ID="你的模型名"
```

如果使用 DeepSeek 或其他云端兼容服务：

```powershell
$env:LLM_BASE_URL="https://api.deepseek.com/v1"
$env:LLM_API_KEY="你的 API Key"
$env:LLM_MODEL_ID="deepseek-chat"
```

## 启动后端

安装依赖后，在项目根目录运行：

```powershell
backend\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend\src --host 127.0.0.1 --port 8501
```

如果你的机器没有 8000 端口限制，也可以使用 8000：

```powershell
backend\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend\src --host 127.0.0.1 --port 8000
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8501/healthz
```

## 启动数据库

本地 Postgres + pgvector：

```powershell
docker compose up -d
```

设置连接串：

```powershell
$env:DATABASE_URL="postgresql+psycopg://deepresearch:deepresearch@127.0.0.1:5432/deepresearch"
```

运行 migration：

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
```

当前 migration 会创建研究历史表、文档表和文档 chunk 表，并启用 `vector` extension，但暂不创建 vector 列。

## 启动前端

前端默认使用 `VITE_API_BASE_URL` 指向后端。复制示例配置：

```powershell
Copy-Item frontend\.env.example frontend\.env.local
```

如果后端使用 8501，修改 `frontend/.env.local`：

```text
VITE_API_BASE_URL=http://127.0.0.1:8501
```

启动：

```powershell
cd frontend
npm install
npm run dev
```

打开 Vite 输出的地址，通常是 `http://localhost:5173`。如果端口被占用，Vite 会自动使用下一个端口，例如 `5174`。

## 使用流程

1. 打开前端页面。
2. 在首页先上传 `.txt` / `.md` 文档；上传完成后可查看文档详情和前 10 个 chunk。
3. 输入研究主题。
4. 点击“开始研究”。
5. 工作台会展示 LangGraph 节点状态、任务清单、当前任务总结、引用来源、工具调用和最终报告。

如果 `RAG_ENABLED=false`，文档库仍可上传和管理，但研究流程会跳过文档检索。若要让上传文档参与研究，需要在后端启动前设置：

```powershell
$env:RAG_ENABLED="true"
```

## API 摘要

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/healthz` | 健康检查 |
| `POST` | `/research` | 非流式研究 |
| `POST` | `/research/stream` | SSE 流式研究 |
| `GET` | `/research/runs?limit=20` | 研究历史列表 |
| `GET` | `/research/runs/{run_id}` | 研究历史详情 |
| `POST` | `/documents/upload` | 上传 `.txt` / `.md` 文档 |
| `GET` | `/documents` | 文档列表 |
| `GET` | `/documents/{document_id}` | 文档详情和 chunks |
| `DELETE` | `/documents/{document_id}` | 删除文档和 chunks |

## RAG 当前阶段

已实现：

- `.txt` / `.md` 上传
- UTF-8 文本解析
- 文本切块
- 文档和 chunk 入库
- 文档列表、详情、删除
- 轻量 BM25 风格排序
- 英文词、数字词、中文 bigram/短语匹配
- `retrieve_documents` 节点注入文档上下文
- `document://...` 来源引用

暂未实现：

- PDF 解析
- embedding
- pgvector 向量列和向量检索
- 文档重建索引
- 多知识库、多用户权限
- 每次研究绑定文档快照

## 验证命令

后端测试：

```powershell
$env:PYTHONDONTWRITEBYTECODE="1"
backend\.venv\Scripts\python.exe -m pytest backend\tests -q -p no:cacheprovider
```

Alembic head：

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic heads
```

前端类型检查：

```powershell
cd frontend
.\node_modules\.bin\vue-tsc.cmd --noEmit
```

前端生产构建：

```powershell
cd frontend
npm run build
```

在受限沙箱中，`npm run build` 可能因 esbuild 子进程启动被拦截而出现 `spawn EPERM`；在普通终端中运行即可。

## 开发注意事项

- 不要提交 `frontend/.env.local`。
- 没有 `DATABASE_URL` 时，后端会使用内存仓库，适合快速开发和测试。
- 文档最好在点击“开始研究”前上传；研究进行中新增文档不会回滚已经执行过的 LangGraph 节点。
- 当前 FastAPI `on_event` 会产生 deprecated warning，但不影响测试和运行。
