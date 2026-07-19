# Design

- Vue Router History 模式；访客页面使用 `guestOnly`，工作台使用 `requiresAuth`。
- 认证会话使用单例 composable，可靠性判断只依赖 `auth.getSession()` 且拒绝匿名会话。
- API 层集中附加 Bearer Token；401 产生单一认证失效事件。
- 注册验证函数仅保存在内存，sessionStorage 只保存待验证邮箱；刷新后要求重新注册发送，不保存密码。
- Workspace 组合 `useResearchFlow`、`useWorkflowState`、`useDocuments`、`useResearchHistory`。
- 视觉采用纸张、墨色、青绿强调的 editorial research dossier 设计系统。
- PostgreSQL 在 `LIMIT` 前按 `owner_id` 过滤。
