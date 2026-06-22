# 数据库说明

这份说明只讲项目里实际用到的部分。可以把 PostgreSQL 理解成和 MySQL 同类的关系型数据库；本项目选择 PostgreSQL 是因为 `pgvector` 可以把普通业务表和向量检索放在同一个数据库里。

## 表结构

| 表 | 作用 |
| --- | --- |
| `research_runs` | 一次研究的主题、搜索引擎和创建时间 |
| `research_tasks` | 每次研究拆出来的子任务、查询词、状态和笔记路径 |
| `research_sources` | 研究过程中保存的网页或本地文档来源 |
| `research_reports` | 最终 Markdown 报告 |
| `documents` | 上传到文档库的文件记录，包含解析状态和摘要 |
| `document_chunks` | 文档切片；RAG 检索命中的是这里的片段 |
| `document_jobs` | 后台解析任务；上传文件后先入队，再由 worker 解析 |

## SQLAlchemy models

后端不用手写大量 SQL，而是在 [backend/src/services/database.py](../backend/src/services/database.py) 里用 Python 类描述表结构。例如：

- `DocumentRow` 对应 `documents`
- `DocumentChunkRow` 对应 `document_chunks`
- `DocumentJobRow` 对应 `document_jobs`

可以把它理解成“用 Python 写表结构和表关系”。

## Alembic migrations

迁移脚本在 [backend/migrations/versions](../backend/migrations/versions)。它们记录数据库如何一步步升级：

1. 创建研究历史表。
2. 创建文档和 chunk 表。
3. 给 chunk 增加 pgvector embedding 字段。
4. 给文档增加 `processing / ready / failed` 状态。
5. 增加 `document_jobs` 后台任务表。

常用命令：

```powershell
cd backend
python -m alembic upgrade head
python -m alembic heads
```

## pgvector 在哪用

`document_chunks.embedding` 是 `vector(1536)` 字段，用来保存每个文档片段的 embedding。

检索时流程是：

1. 根据关键词算 BM25 风格分数。
2. 如果配置了 embedding，再算向量相似度。
3. 把关键词分和向量分合成 hybrid score。
4. 返回最相关的 chunk，并生成 `document://{document_id}#chunk-{chunk_index}` 来源。

## 没有数据库时会怎样

如果不配置 `DATABASE_URL`，后端会使用内存仓库，适合快速演示，但服务重启后数据会丢失。

如果配置 `DATABASE_URL`，研究历史、文档库、解析任务和 embedding 都会保存到 PostgreSQL。

## 维护命令

```powershell
cd backend
python src/embedding_cli.py --backfill --limit 100
python src/embedding_cli.py --retry-failed-documents
python src/embedding_cli.py --rebuild-document --document-id <document_id>
```
