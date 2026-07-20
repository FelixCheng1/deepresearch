# DeepResearch

> 融合网页搜索、文档 RAG 与可回放工作流的多用户深度研究工作台。

## 项目简介

DeepResearch 面向需要持续收集资料、拆解问题并形成可追溯报告的研究者与开发者。用户输入主题后，系统会规划 3～5 个互补子任务，并行执行本地文档检索与网页搜索，最后汇总为 Markdown 报告。前端实时呈现 LangGraph 节点、任务进度、引用来源、工具调用和实际搜索后端；研究历史、文档与检索结果按 CloudBase 用户身份隔离。

项目的重点不只是“调用一次大模型”，而是把规划、检索、总结、持久化、审计和历史回放组织成清晰的工程边界。它适合用作个人研究工作台、RAG 实验平台或 Agent 工作流参考实现。当前仓库已具备完整本地开发和云端部署基础，但仍应结合真实数据评测、外部任务队列和生产监控后再承担关键生产负载。

## 核心能力

### 多阶段深度研究

LangGraph 将主题规划、并行子任务、文档检索、网页搜索、总结和报告写作组织为显式工作流。每个节点都有清晰状态，便于实时观察、测试和历史回放。

### 可审计的实时工作台

后端通过 SSE 推送任务、节点、来源、工具调用、报告和错误事件。用户能够实时查看并行任务与证据链，完成后仍可从持久化快照恢复界面。

### 搜索能力协商与降级

系统支持 DuckDuckGo、Tavily、Perplexity、SearXNG 和“智能降级”。`/capabilities` 只暴露当前真正可用的选项；研究结果明确记录请求后端、实际后端和安全化降级原因。

### 文档库与混合 RAG

上传 `.txt`、`.md`、`.pdf`、`.docx` 后，后台完成解析、切块和可选 Embedding。检索支持词法排名、向量混排与 Cross-Encoder 重排，并以 `document://...#chunk-N` 保留片段级证据。

### 完整认证与用户隔离

CloudBase Auth 提供邮箱注册、验证码确认、邮箱或旧用户名登录、退出和密码重置。后端校验 Bearer Token，并以 `owner_id` 过滤研究、文档和检索数据；跨用户访问统一返回 404。

### 持久化、评测与质量门禁

PostgreSQL + pgvector 保存研究历史、任务、来源、工具调用和文档。仓库包含 pytest、Vitest、RAG 离线评测、合成基准和 GitHub Actions。

## 效果展示

**输入示例**：

```text
2026 年人工智能 Agent 的主要技术趋势
```

**预期输出**：

- 3～5 个互补研究任务及其状态；
- LangGraph 并行节点与整体进度；
- 网页来源和 `document://` RAG 命中片段；
- 搜索请求后端、实际后端及降级原因；
- 可回放的工具调用、任务笔记和最终 Markdown 报告。

<!-- TODO: 添加登录页、研究工作台和 RAG 命中效果截图或 GIF。 -->

## 应用场景

- **技术趋势研究**：上传内部资料，再结合网页搜索形成带来源的趋势报告。
- **私有知识调研**：以规范、论文、会议记录或产品文档为知识库，验证 RAG 效果。
- **Agent 工程实验**：比较不同 LLM、搜索引擎、Embedding、Top-K 和重排参数。
- **工作流教学**：观察 fan-out/fan-in、SSE 事件、任务持久化和历史回放如何协同。

## 项目亮点

1. **显式编排**：父图负责 fan-out/fan-in，任务子图负责 RAG、搜索和总结。
2. **可回放协议**：SSE 实时状态与持久化事件语义一致，历史恢复无需重新研究。
3. **渐进式 RAG**：词法检索可独立运行，向量与重排逐级增强并保留故障降级。
4. **能力透明**：前端只展示后端确认可用的搜索引擎，并呈现实际后端和降级原因。
5. **隔离验证**：认证、Repository 和 SQL 查询共同执行用户隔离，并有跨用户测试。

## 功能概览

- LangGraph 主流程：`plan_tasks -> dispatch_tasks -> run_task 并行 -> join_tasks -> write_report -> persist_report -> END`
- 子任务流程：准备任务、可选文档检索、网页搜索、任务总结、任务持久化
- SSE 流式事件：任务清单、节点状态、来源、工具调用、任务总结、最终报告
- 文档库：上传 `.txt` / `.md` / `.pdf` / `.docx`、后台解析、列表、详情、chunk 预览、删除、失败重试
- 持久化：内存仓库或 Postgres + pgvector
- RAG：轻量文本排序；配置 embedding 后写入向量字段并参与混合排序
- RAG 评测：内置小规模检索评测集，输出 Recall@K 和 MRR

## 系统架构

```mermaid
flowchart TD
    U["用户浏览器"] --> V["Vue 3 研究工作台"]
    V --> A["CloudBase Auth"]
    V -->|"Bearer Token + HTTP/SSE"| F["FastAPI API"]
    F --> G["DeepResearchAgent"]
    G --> L["LangGraph 工作流"]
    L --> M["OpenAI-compatible LLM"]
    L --> S["搜索适配层"]
    L --> R["文档 RAG 检索"]
    F --> W["文档后台 Worker"]
    W --> P["解析、切块与 Embedding"]
    F --> O["按 owner_id 隔离的 Repository"]
    R --> O
    P --> O
    O --> D[("PostgreSQL + pgvector")]
```

| 模块 | 职责 |
| --- | --- |
| Vue 页面与组件 | 认证页面、研究表单、文档库、工作流、证据和历史展示 |
| Composables | 管理研究流、工作流状态、文档轮询、历史回放和会话生命周期 |
| API/Auth 服务 | 统一附加 Access Token、消费 SSE、处理 401 和 CloudBase 会话 |
| FastAPI | 认证、限额、HTTP/SSE 协议、文件校验和服务装配 |
| DeepResearchAgent | 驱动规划、子任务研究、总结、报告和事件输出 |
| Repository | 在内存或 PostgreSQL 上实现一致的研究与文档访问接口 |
| 文档 Worker | 解析、切块、Embedding 并更新文档任务状态 |

更细的职责边界和修改入口见 [项目地图](docs/project-map.md)。

## 核心工作流程

```mermaid
flowchart LR
    I["输入研究主题"] --> P["规划 3～5 个任务"]
    P --> D["分发并行任务"]
    D --> T["准备任务"]
    T --> R["可选文档检索"]
    R --> S["网页搜索"]
    T --> S
    S --> M["任务总结"]
    M --> N["持久化任务与笔记"]
    N --> J["汇合所有任务"]
    J --> W["撰写报告"]
    W --> O["保存并流式输出"]
```

1. **能力加载**：工作台读取 `/capabilities`，只显示当前部署可用的搜索引擎。
2. **任务规划**：规划 Prompt 将主题拆成 3～5 个互补任务；解析失败时使用后端兜底任务。
3. **并行执行**：父图分批分发任务，每个任务进入独立子图。
4. **双路取证**：开启 RAG 时先检索当前用户文档，再执行网页搜索。
5. **总结与报告**：任务总结持久化后汇合，由报告 Prompt 生成最终 Markdown。
6. **事件与回放**：SSE 驱动前端；结构化工具调用和报告写入历史以便恢复。

## AI 工作流程

### Agent 架构

```mermaid
flowchart TD
    O["DeepResearchAgent 编排器"] --> P["规划服务"]
    O --> TG["任务子图"]
    O --> RW["报告服务"]
    TG --> DR["文档检索器"]
    TG --> WS["网页搜索器"]
    TG --> TS["任务总结器"]
    P --> L["聊天模型"]
    TS --> L
    RW --> L
    DR --> DB[("用户文档库")]
    WS --> X["外部搜索服务"]
```

这里采用“单一编排器 + 显式服务边界”，而不是让多个自治 Agent 自由对话。任务并行由 LangGraph 的 `Send` 和父子图控制，因此事件顺序、持久化和失败边界更容易测试。

### Prompt Pipeline

Prompt 集中在 `backend/src/prompts.py`：

1. **规划 Prompt**：注入当前日期和主题，要求仅输出结构化任务 JSON。
2. **任务总结 Prompt**：组合任务意图、RAG 上下文与网页上下文，输出关键发现。
3. **报告 Prompt**：组合任务总结和来源，生成背景、洞见、证据、风险及参考来源。
4. **输出清洗**：移除思考标签和工具调用残留，避免内部协议进入报告。

### RAG 流程

```mermaid
flowchart TD
    F["上传文档"] --> P["解析 TXT、MD、PDF、DOCX"]
    P --> C["按段落切块 1200 字符 + 120 重叠"]
    C --> E["可选 Embedding"]
    E --> DB[("document_chunks")]
    Q["任务查询"] --> QR["可选 LLM 查询改写"]
    QR --> H["BM25 风格词法 + 可选向量混排"]
    DB --> H
    H --> RR["可选 Cross-Encoder 重排"]
    RR --> A["合并相邻片段并注入上下文"]
```

- **数据来源**：当前用户上传的文本、Markdown、可提取文本 PDF 和 DOCX；扫描 PDF 可选 OCR。
- **分块策略**：优先按段落切分，默认最大 1200 字符、相邻块重叠 120 字符。
- **首阶段检索**：中英文词项、中文二元组、短语、标题加权和 BM25 风格归一化。
- **混合评分**：存在查询向量时使用 `0.55 × 向量相似度 + 0.45 × 归一化词法分`。
- **重排与降级**：可选 Cross-Encoder；Embedding 或重排异常不会阻断基本流程。
- **来源追踪**：命中片段生成 `document://{document_id}#chunk-{chunk_index}`。

评测边界和数据集格式见 [RAG 检索评测](docs/rag-evaluation.md)，选型依据见 [工程取舍](docs/engineering-decisions.md)。

### LLM 使用方式

| 配置方式 | 用途 | 说明 |
| --- | --- | --- |
| Ollama | 本地聊天与可选 Embedding | 默认本地提供方，自动补全 `/v1` 路径 |
| LM Studio | 本地 OpenAI-compatible 调用 | 适合桌面模型调试 |
| Custom | DeepSeek 或其他兼容网关 | 通过 Base URL、API Key 和模型 ID 接入 |
| 独立 Embedding 服务 | 文档与查询向量化 | 可与聊天模型使用不同服务和密钥 |

任务数、研究循环次数、是否抓取全文、RAG Top-K 和报告上下文长度都会影响延迟与调用成本。

## 技术栈

| 层级 | 技术 | 用途 | 选型理由 |
| --- | --- | --- | --- |
| 前端 | Vue 3、TypeScript、Vue Router | 页面、状态组合与路由守卫 | 组合式 API 适合长耗时业务状态 |
| 构建测试 | Vite、vue-tsc、Vitest、Vue Test Utils | 构建、类型检查与测试 | 开发反馈快，测试链路轻量 |
| 认证 | CloudBase JS SDK / Auth | 注册、登录、会话和密码重置 | 与 CloudBase 托管环境集成 |
| 后端 | Python、FastAPI、Uvicorn | HTTP、SSE、认证和文件上传 | 接口清晰，异步 Web 生态成熟 |
| Agent | LangChain、LangGraph | LLM 适配、父子图和并行编排 | 支持显式状态和 fan-out/fan-in |
| 搜索 | DuckDuckGo、Tavily、Perplexity、SearXNG | 外部检索与降级 | 覆盖零密钥、本地和托管方案 |
| RAG | 自定义词法排序、Embedding、Cross-Encoder | 文档召回、混排和重排 | 保留低依赖降级路径 |
| 数据 | PostgreSQL 16、pgvector、SQLAlchemy、Alembic | 业务数据和向量持久化 | 事务数据与向量字段统一管理 |
| 部署 | Docker、CloudBase Run、Cloudflare Pages / CloudBase 静态托管 | 后端容器与前端 SPA | 已提供相应构建配置 |
| CI | GitHub Actions、Ruff、pytest | 自动质量门禁 | Push 和 PR 自动验证 |

## 项目结构

```text
Deepresearch/
├── backend/
│   ├── src/
│   │   ├── agent.py                 # Agent 与 SSE 事件输出
│   │   ├── main.py                  # FastAPI 路由、认证和上传
│   │   ├── config.py                # 环境变量配置
│   │   ├── prompts.py               # 规划、总结和报告 Prompt
│   │   └── services/                # 图、LLM、搜索、RAG、仓库、数据库
│   ├── migrations/                  # Alembic 迁移
│   ├── tests/                       # 后端测试
│   ├── Dockerfile                   # 容器部署入口
│   └── pyproject.toml               # Python 依赖与工具
├── frontend/
│   ├── src/
│   │   ├── pages/                   # 认证页与 Workspace
│   │   ├── composables/             # 研究流、工作流、文档、历史、会话
│   │   ├── components/              # 业务组件与基础 UI
│   │   ├── services/                # Auth、HTTP/SSE 和历史回放
│   │   ├── router/                  # 路由与认证守卫
│   │   └── styles/                  # 设计变量和全局样式
│   ├── public/_redirects            # Cloudflare Pages SPA 回退
│   └── cloudbaserc.json             # CloudBase 构建配置
├── docs/                            # 项目地图、数据库、RAG 与工程文档
├── specs/frontend-auth-refactor/    # 认证重构规格
├── .github/workflows/ci.yml         # GitHub Actions
├── docker-compose.yml               # 本地 PostgreSQL + pgvector
└── README.md
```

## 环境要求

- Python 3.10+
- Node.js 22（CI 使用版本；Node.js 18+ 通常也可运行）
- npm 与 [uv](https://docs.astral.sh/uv/)
- Docker Desktop / Docker Compose
- CloudBase 环境及 Web 可发布密钥
- OpenAI-compatible 聊天模型服务

## 配置说明

### 前端环境变量

| 变量 | 必需 | 说明 |
| --- | --- | --- |
| `VITE_API_BASE_URL` | 是 | FastAPI 公网或本地地址 |
| `VITE_CLOUDBASE_ENV_ID` | 是 | CloudBase 环境 ID |
| `VITE_CLOUDBASE_PUBLISHABLE_KEY` | 是 | Web 可发布密钥，不要填写服务端私钥 |

Vite 变量在启动或构建时注入，不能用后端运行时变量替代。

### 后端环境变量

```powershell
Copy-Item backend\.env.example backend\.env
```

本地完整流程建议至少设置：

```dotenv
LLM_PROVIDER=custom
LLM_BASE_URL=https://your-openai-compatible-api/v1
LLM_API_KEY=replace-with-your-key
LLM_MODEL_ID=your-model-id

DATABASE_URL=postgresql+psycopg://deepresearch:deepresearch@127.0.0.1:5432/deepresearch
RAG_ENABLED=true

CLOUDBASE_ENV_ID=your-cloudbase-env-id
AUTH_REQUIRED=true
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

### 核心变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PORT` | `8000` | 后端端口 |
| `LLM_PROVIDER` | `ollama` | `ollama`、`lmstudio` 或 `custom` |
| `LLM_BASE_URL` | 空 | Custom OpenAI-compatible Base URL |
| `LLM_API_KEY` | 空 | 聊天模型 API Key |
| `LLM_MODEL_ID` / `LOCAL_LLM` | `llama3.2` | 模型 ID |
| `LLM_TIMEOUT` | `60` | 模型请求超时秒数 |
| `SEARCH_API` | `duckduckgo` | 默认搜索后端 |
| `TAVILY_API_KEY` | 空 | 配置后启用 Tavily |
| `PERPLEXITY_API_KEY` | 空 | 配置后启用 Perplexity |
| `SEARXNG_URL` | 空 | 配置后启用自建 SearXNG |
| `FETCH_FULL_PAGE` | `true` | 是否获取搜索原始正文 |
| `DATABASE_URL` | 空 | 无值时使用重启即丢失的内存仓库 |
| `CLOUDBASE_ENV_ID` | 空 | 后端 Token introspection 环境 ID |
| `AUTH_REQUIRED` | `false` | 生产环境必须显式设为 `true` |
| `CORS_ORIGINS` | 本地地址 | 逗号分隔的前端 Origin |
| `UPLOAD_MAX_BYTES` | `10485760` | 单文件上限，默认 10 MiB |
| `RESEARCH_DAILY_LIMIT` | `10` | 单用户每日研究次数 |
| `RESEARCH_COOLDOWN_SECONDS` | `60` | 研究冷却时间 |
| `UPLOAD_DAILY_LIMIT` | `20` | 单用户每日上传次数 |
| `NOTES_WORKSPACE` | `./notes` | 任务笔记和报告目录 |

### RAG、Embedding 与 OCR

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `RAG_ENABLED` | `false` | 启用文档检索 |
| `RAG_TOP_K` | `5` | 每个任务注入的片段数 |
| `RAG_CONTEXT_MAX_CHARS` | `6000` | 单任务上下文字符上限 |
| `RAG_MIN_SCORE` | `0.1` | 最低词法匹配分 |
| `RAG_QUERY_REWRITE_ENABLED` | `true` | 用 LLM 改写检索查询 |
| `RAG_MERGE_ADJACENT_CHUNKS` | `true` | 合并命中片段相邻块 |
| `RAG_ADJACENT_CHUNK_WINDOW` | `1` | 前后合并块数 |
| `EMBEDDING_BASE_URL` | 回退到 LLM 地址 | Embedding 服务地址 |
| `EMBEDDING_API_KEY` | 回退到 LLM Key | Embedding 密钥 |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding 模型 |
| `EMBEDDING_DIMENSION` | `1536` | 必须匹配数据库 `vector(1536)` |
| `RAG_RERANK_ENABLED` | `false` | 启用 Cross-Encoder 重排 |
| `RAG_RERANK_MODEL` | `BAAI/bge-reranker-base` | 重排模型 |
| `RAG_RERANK_TOP_N` | `20` | 重排候选数 |
| `PDF_OCR_ENABLED` | `false` | PDF 无文本时启用 OCR |
| `PDF_OCR_LANGUAGE` | `chi_sim+eng` | Tesseract 语言 |
| `PDF_OCR_DPI` | `200` | PDF 转图片 DPI |
| `PDF_OCR_MAX_PAGES` | `20` | OCR 页数上限 |
| `TESSERACT_CMD` / `POPPLER_PATH` | 空 | Windows OCR 工具路径 |

## 快速开始

每次本地启动都先启动数据库，再启动后端和前端。首次运行还需要复制并编辑前后端环境变量文件。

```powershell
docker compose up -d db
docker compose ps

Copy-Item backend\.env.example backend\.env
cd backend
uv sync --locked --group dev
uv run alembic upgrade head
uv run python src/main.py
```

另开 PowerShell 启动前端：

```powershell
cd frontend
Copy-Item .env.example .env.local
npm ci
npm run dev
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/healthz
```

## 数据库与 RAG 维护

完整研究、历史回放和文档 RAG 应使用 PostgreSQL。不配置 `DATABASE_URL` 时会回退到内存仓库，服务重启后数据丢失。

```powershell
docker compose up -d db
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

前端必须同时配置后端地址和 CloudBase Web 认证。在 `frontend/.env.local` 写入：

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_CLOUDBASE_ENV_ID=your-cloudbase-env-id
VITE_CLOUDBASE_PUBLISHABLE_KEY=your-publishable-key
```

启动：

```powershell
cd frontend
npm ci
npm run dev
```

打开 Vite 输出的地址，通常是 `http://localhost:5173`。Vite 环境变量在启动或构建时注入，修改后必须重启开发服务器。

## 使用流程

1. 注册邮箱账号并完成验证码确认，或使用已有邮箱/旧用户名登录。
2. 上传 `.txt`、`.md`、`.pdf` 或 `.docx`，等待状态变成“可检索”。
3. 输入研究主题并选择后端确认可用的搜索引擎。
4. 点击“开始研究”，观察 LangGraph 节点、任务、来源和工具调用。
5. 在引用来源确认 `document://...#chunk-N` 被标记为 RAG 命中片段。
6. 完成后刷新页面，从当前用户的研究历史恢复结果。

## API 摘要

除 `/healthz` 外，生产模式接口需要 `Authorization: Bearer <CloudBase access token>`。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/healthz` | 健康检查 |
| `GET` | `/capabilities` | 当前部署可供前端选择的搜索引擎（需登录，不返回密钥） |
| `POST` | `/research` | 非流式研究 |
| `POST` | `/research/stream` | SSE 流式研究 |
| `GET` | `/research/runs?limit=20` | 研究历史列表 |
| `GET` | `/research/runs/{run_id}` | 研究历史详情（任务、来源、报告、工具调用） |
| `POST` | `/documents/upload` | 上传文档 |
| `GET` | `/documents` | 文档列表 |
| `GET` | `/documents/{document_id}` | 文档详情和 chunks |
| `POST` | `/documents/{document_id}/retry` | 重试失败文档解析 |
| `DELETE` | `/documents/{document_id}` | 删除文档和 chunks |

搜索选项由 `/capabilities` 动态提供。研究流的 `search_backend` 事件会返回请求后端、实际使用的后端和安全化的降级原因；同一元数据也会作为 `search` 工具调用写入历史，供回放恢复。

请求示例：

```json
{
  "topic": "2026 年人工智能 Agent 的主要技术趋势",
  "search_api": "advanced"
}
```


## 测试与质量检查

```powershell
cd backend
uv run pytest
uv run alembic heads
uv run python src/rag_eval_cli.py
uv run python src/rag_benchmark_cli.py --chunk-counts 100,1000,5000 --queries 100
uv run python src/rag_eval_cli.py --json
uv run python src/rag_eval_cli.py --dataset eval/rag-dataset.json --fail-below-recall 0.8 --fail-below-mrr 0.6
```

默认 RAG 评测使用内置 smoke 数据，不依赖数据库、LLM、embedding API 或网络，只用于验证评测链路，不代表生产检索质量。正式比较应传入版本化 JSON 数据集；格式和门禁用法见 [RAG 评测说明](docs/rag-evaluation.md)。指标含义：

- `Recall@K`：前 K 个检索结果中是否包含期望文档，越高表示召回越稳定。
- `MRR`：期望文档排名的倒数均值，越高表示正确文档越靠前。
- `expected_terms_coverage`：期望证据词是否出现在目标文档召回片段中。


合成规模基准只用于比较同一台机器上的代码变化，不代表生产 QPS 或 SLA。框架、检索和切块参数的选择依据见 [工程取舍](docs/engineering-decisions.md)。

```powershell
cd frontend
npm test
.\node_modules\.bin\vue-tsc.cmd --noEmit
npm run build
```

GitHub Actions 会在 Push 和 Pull Request 上运行 Ruff、Alembic heads、pytest 和前端生产构建。

## 最终验收清单

- 上传 `.txt` / `.md` / `.pdf` / `.docx` 后，文档状态能从“解析中”变为“可检索”。
- 上传空 PDF 或无法解析文档时，状态显示“解析失败”，并可点击重试。
- 开始研究后，LangGraph 工作流一开始就显示，且可以收起/展开。
- 引用来源中出现本地 `document://...#chunk-...` 时，前端标记为 RAG 命中片段。
- 研究历史详情包含按 `event_id` 排序的结构化 `tool_calls`，可用于审计和回放。
- 最终报告以 Markdown 样式渲染，标题、列表、代码和链接可读。
- 后端测试、Alembic head、RAG 检索评测、前端类型检查通过。

## 数据库说明

熟悉 MySQL 的读者可先查看 [docs/database.md](docs/database.md)。该文档结合本项目的实际表结构，说明 PostgreSQL、SQLAlchemy、Alembic 和 pgvector 的作用。

## 开发注意事项

- 不要提交 `.env`、`frontend/.env.local`、`notes/`、`node_modules/`、`.venv/`。
- 没有 `DATABASE_URL` 时，后端使用内存仓库，适合快速演示。
- 配置 Postgres 后先跑 `uv run alembic upgrade head`。
- 后端使用 FastAPI lifespan 管理后台文档 worker 的启动和停止。

## 部署

### 后端容器 / CloudBase Run

`backend/Dockerfile` 使用 Python 3.12、uv 和 Uvicorn，容器监听环境变量 `PORT`：

```powershell
docker build -t deepresearch-api ./backend
docker run --rm -p 8000:8000 --env-file backend/.env deepresearch-api
```

部署到 CloudBase Run 时，以 `backend` 为构建目录并保留生产环境变量。生产环境至少设置：

- `AUTH_REQUIRED=true` 与 `CLOUDBASE_ENV_ID`；
- PostgreSQL `DATABASE_URL`；
- LLM、搜索和可选 Embedding 配置；
- 精确到协议和域名的 `CORS_ORIGINS`。

### 前端静态站点

```powershell
cd frontend
npm ci
npm run build
```

构建产物位于 `frontend/dist`。仓库同时提供：

- `frontend/cloudbaserc.json`：CloudBase 静态站点构建配置；
- `frontend/public/_redirects`：Cloudflare Pages 的 History Router SPA 回退；
- `VITE_API_BASE_URL`：构建时注入后端公网地址。

无论使用 CloudBase 静态托管还是 Cloudflare Pages，都需要把最终前端 Origin 加入 CloudBase 安全域名和后端 `CORS_ORIGINS`。直接访问 `/login`、`/register`、`/verify-email`、`/forgot-password` 或 `/workspace` 时必须回退到 `index.html`。

## 性能与扩展性

- **主要延迟**：并行 LLM 调用、网页全文抓取、Embedding 和 Cross-Encoder 重排。
- **检索边界**：当前在应用层对候选 chunks 排序；大规模数据应增加数据库向量索引和分页召回。
- **任务边界**：文档 Worker 是进程内线程；多实例部署应迁移到共享队列和幂等 Worker。
- **限流边界**：`DemoUsageLimiter` 仅在单实例内存生效；多实例应使用 Redis 或数据库计数器。
- **水平扩展**：研究状态、限流和后台任务迁移到共享基础设施后，再扩展 FastAPI 实例。

内置合成基准只用于比较同一机器上的代码变化，不代表生产 QPS、SLA 或真实数据质量。

## 安全设计

- CloudBase SDK 管理前端会话，API 客户端统一添加 Bearer Token。
- 后端通过 CloudBase Token introspection 读取可信 `sub`，并短暂缓存验证结果。
- 研究、文档、检索、删除和重试始终传入 `owner_id`；越权资源返回 404。
- HTTP 401 和 CloudBase `SIGNED_OUT` 进入统一失效流程，并保留登录回跳地址。
- 注册验证码句柄和密码重置句柄仅保存在内存中，不持久化明文密码。
- 文件上传校验扩展名、MIME、大小和空内容，仅支持四种明确格式。
- `/capabilities` 不返回搜索密钥，降级错误只暴露安全化原因。
- `.env`、`.env.local`、笔记、虚拟环境和依赖目录不应提交到 Git。

> `VITE_CLOUDBASE_PUBLISHABLE_KEY` 是前端可发布配置，不等同于服务端私钥；模型、数据库和第三方搜索密钥仍必须只保存在后端环境变量中。

## Roadmap

- [x] LangGraph 多任务并行研究与 SSE 实时工作流
- [x] 搜索能力协商、自动降级和后端透明度
- [x] 文档解析、混合 RAG、可选重排与 OCR
- [x] CloudBase 邮箱认证、密码重置和多用户隔离
- [x] 研究历史、工具调用审计与完整界面回放
- [x] 后端、前端、隔离和 RAG 评测测试
- [ ] 引入共享任务队列、分布式限流和生产监控
- [ ] 使用真实业务问答集持续评测检索和报告质量
- [ ] 为大规模 chunks 增加数据库向量索引
- [ ] 补充正式演示地址、产品截图、LICENSE 和贡献模板

## 贡献指南

1. Fork 仓库并创建分支：`git checkout -b feature/your-feature`。
2. 保持修改聚焦，新增行为应补充 pytest 或 Vitest。
3. 提交前运行测试与生产构建。
4. 建议使用中文 Conventional Commits，例如：`feat: 增加检索结果重排`。
5. 推送分支并提交 Pull Request，说明范围、验证结果和配置影响。

建议的提交类型：`feat`、`fix`、`refactor`、`test`、`docs`、`chore`。

## FAQ

### 浏览器打开前端为什么是空白页？

先查看浏览器控制台。常见原因是缺少 `VITE_CLOUDBASE_ENV_ID` 或 `VITE_CLOUDBASE_PUBLISHABLE_KEY`；Vite 变量在启动或构建时注入，修改后必须重启或重新构建。

### 后端出现 `WinError 10048` 怎么办？

端口已被占用。停止旧后端，或改用 `--port 8501`，并把前端 API 地址同步改为 `http://127.0.0.1:8501`。

### 浏览器请求显示 `OPTIONS 400` 怎么办？

把实际前端 Origin（协议、主机和端口必须完全一致）加入 `CORS_ORIGINS`，然后重启后端。多个值使用逗号分隔。

### 为什么上传文档后没有 RAG 命中？

确认数据库正在运行、迁移已升级、`DATABASE_URL` 和 `RAG_ENABLED=true` 已生效，并等待文档变成“可检索”。扫描 PDF 还需要 OCR 可选依赖。

### 为什么服务重启后历史和文档消失？

未设置 `DATABASE_URL` 时系统使用内存仓库。启动 PostgreSQL、设置连接串并执行迁移后，数据才会持久化。

### 为什么选择 Tavily，结果却显示 DuckDuckGo？

Tavily 未配置、请求异常或未返回有效内容时会自动降级。页面和历史都会记录实际后端与安全化原因。

## License

`backend/pyproject.toml` 当前声明项目采用 MIT License，但仓库根目录尚未包含正式 `LICENSE` 文件。对外发布或接受贡献前，请补充完整 MIT License 文本并确认版权归属。
