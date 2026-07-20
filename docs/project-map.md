# Deepresearch 项目地图

## 一句话结构

Vue 工作台通过 CloudBase Auth 获取访问令牌，调用 FastAPI 研究服务；FastAPI 校验令牌中的用户 ID，再以 `owner_id` 访问 PostgreSQL 中的研究历史和文档。

```text
Cloudflare Pages (Vue/Vite)
  ├─ CloudBase Auth：注册、邮箱验证码、登录、刷新、退出、重置密码
  └─ Bearer Token
       ↓
CloudBase Run / FastAPI
  ├─ DeepResearchAgent：规划、检索、总结、报告
  ├─ 文档后台任务：解析、切块、向量化
  └─ Repository(owner_id)
       ↓
PostgreSQL：research_runs / documents / chunks / jobs
```

## 目录职责

| 区域 | 职责 | 修改入口 |
| --- | --- | --- |
| `frontend/src/pages` | 路由页面与领域组合 | 新页面、页面级导航 |
| `frontend/src/composables` | 研究流、工作流、文档、历史、认证会话 | 页面状态与副作用 |
| `frontend/src/components` | 工作台业务组件及共享 UI | 展示与局部交互 |
| `frontend/src/services` | CloudBase Auth、HTTP/SSE、历史回放 | 外部接口和协议 |
| `frontend/src/styles` | 设计变量与基础组件样式 | 全站视觉规则 |
| `backend/src/main.py` | HTTP 路由、鉴权入口、额度限制 | API 行为 |
| `backend/src/services/auth.py` | Access Token introspection | 服务端身份可信边界 |
| `backend/src/services/repository.py` | 按 `owner_id` 持久化和查询 | 数据隔离 |
| `backend/src/agent.py` | 深度研究工作流与流式事件 | 研究算法 |
| `backend/migrations` | PostgreSQL 结构演进 | 数据库迁移 |

## 核心调用链

### 登录与接口

1. 页面调用 `services/auth.ts`。
2. CloudBase SDK 保存和刷新会话。
3. `services/api.ts` 从 `getSession()` 读取 access token。
4. FastAPI `require_user()` introspect token 并读取 `sub`。
5. 所有用户资源查询传入该 `sub` 作为 `owner_id`。
6. HTTP 401 触发统一认证失效事件，清空工作区并返回 `/login`。

### 研究流

`WorkspacePage` → `useResearchFlow` → `runResearchStream` → `/research/stream` → `DeepResearchAgent` → SSE → `useWorkflowState.consumeEvent`。

进入工作台时，`useResearchFlow` 先调用 `/capabilities`，搜索选择器只显示当前部署已配置的后端。每个任务完成搜索后，后端通过 `search_backend` 事件返回请求后端、实际后端和降级原因，并复用工具调用存储供历史回放。

### 文档流

`useDocuments` → 上传 API → pending document/job → worker 解析与切块 → 轮询列表 → RAG 按当前 `owner_id` 检索。

### 历史回放

`useResearchHistory` 读取快照 → `buildHistoryReplay` 生成回放状态 → Workspace 分别恢复研究上下文和工作流，不形成 composable 循环依赖。

## 环境与部署

前端必需变量：

- `VITE_CLOUDBASE_ENV_ID`
- `VITE_CLOUDBASE_PUBLISHABLE_KEY`
- `VITE_API_BASE_URL`

后端必需变量见 `backend/src/config.py`，生产环境至少包括 CloudBase 环境 ID、认证开关、数据库连接和模型/搜索配置。

Cloudflare Pages：构建目录为 `frontend/dist`，`frontend/public/_redirects` 提供 History Router 的 SPA 回退。后端 CORS 必须包含最终 Pages 域名。

## 数据边界

- `research_runs.owner_id` 与 `documents.owner_id` 是用户隔离根字段。
- 任务、来源、报告、工具调用通过研究运行继承边界；chunks/jobs 通过文档继承边界。
- 对其他用户资源返回 404，不暴露资源存在性。
- 迁移生成的 `legacy` 数据不自动归属新用户。
