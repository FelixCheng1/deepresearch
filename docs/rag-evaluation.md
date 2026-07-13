# RAG 检索评测

内置数据集是一个离线 smoke set，只验证分词、排序、指标计算和 CLI 输出链路。它规模小、词面重合明显，因此即使 Recall@K 和 MRR 很高，也不能作为生产检索质量结论。

正式评测应维护独立、可版本化的 JSON 数据集：

```json
{
  "name": "project-docs-v1",
  "sample_only": false,
  "documents": [
    {
      "title": "workflow.md",
      "text": "完整的待检索文档正文"
    }
  ],
  "cases": [
    {
      "query": "用户真实问题",
      "expected_document": "workflow.md",
      "expected_terms": ["期望证据词"]
    }
  ]
}
```

运行评测：

```powershell
cd backend
uv run python src/rag_eval_cli.py --dataset eval/rag-dataset.json --top-k 3
uv run python src/rag_eval_cli.py --dataset eval/rag-dataset.json --json
```

作为 CI 或本地门禁使用：

```powershell
uv run python src/rag_eval_cli.py `
  --dataset eval/rag-dataset.json `
  --fail-below-recall 0.8 `
  --fail-below-mrr 0.6
```

低于任一阈值时 CLI 返回退出码 `1`。数据集加载器还会拒绝空数据、重复文档标题和引用不存在文档的 case，避免评测配置悄悄失效。

建议至少收集 30～50 条来自真实文档和用户问题的 case，并保留容易混淆的负样本文档。对 BM25、向量检索、混合检索和重排分别运行同一数据集，记录 Recall@K、MRR、延迟和调用成本。
