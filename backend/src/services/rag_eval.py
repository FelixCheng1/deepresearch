"""Lightweight RAG retrieval evaluation helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.repository import InMemoryResearchRepository
from services.retriever import RepositoryRetriever


@dataclass(frozen=True)
class RagEvalDocument:
    """One document used by a retrieval evaluation case."""

    title: str
    text: str


@dataclass(frozen=True)
class RagEvalCase:
    """One query and its expected document-level hit."""

    query: str
    expected_document: str
    expected_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class RagEvalDataset:
    """A named retrieval dataset loaded from a versioned JSON file."""

    name: str
    documents: tuple[RagEvalDocument, ...]
    cases: tuple[RagEvalCase, ...]
    sample_only: bool = False


@dataclass(frozen=True)
class RagEvalCaseResult:
    """Evaluation result for one query."""

    query: str
    expected_document: str
    hit: bool
    rank: int | None
    reciprocal_rank: float
    expected_terms_found: bool
    top_results: list[dict[str, Any]]


@dataclass(frozen=True)
class RagEvalReport:
    """Aggregate evaluation report."""

    summary: dict[str, Any]
    cases: list[RagEvalCaseResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "cases": [
                {
                    "query": case.query,
                    "expected_document": case.expected_document,
                    "hit": case.hit,
                    "rank": case.rank,
                    "reciprocal_rank": case.reciprocal_rank,
                    "expected_terms_found": case.expected_terms_found,
                    "top_results": case.top_results,
                }
                for case in self.cases
            ],
        }


DEFAULT_DOCUMENTS: tuple[RagEvalDocument, ...] = (
    RagEvalDocument(
        title="langgraph_workflow.md",
        text=(
            "LangGraph 工作流支持 plan_tasks、dispatch_tasks 和 run_task fan-out。"
            "它适合把深度研究拆成并行子任务，再汇总为最终报告。"
        ),
    ),
    RagEvalDocument(
        title="rag_evaluation.md",
        text=(
            "RAG 检索质量可以用 Recall@K、MRR 和命中文档排名评估。"
            "评测集应包含 query、期望文档和实际召回结果。"
        ),
    ),
    RagEvalDocument(
        title="document_processing.md",
        text=(
            "文档处理流程支持 PDF、DOCX、Markdown 和 TXT 上传。"
            "扫描 PDF 可以通过 Tesseract 和 Poppler 执行 OCR。"
        ),
    ),
    RagEvalDocument(
        title="postgres_pgvector.md",
        text=(
            "PostgreSQL 配合 pgvector 可以保存 document_chunks.embedding。"
            "每个 chunk 存储文本、metadata、embedding_model 和 embedded_at。"
        ),
    ),
    RagEvalDocument(
        title="chinese_search.md",
        text=(
            "中文文档检索质量依赖分词、bigram 和短语匹配。"
            "没有空格的中文查询也应该能命中文档片段。"
        ),
    ),
    RagEvalDocument(
        title="rerank.md",
        text=(
            "Cross-Encoder rerank 可以对 RAG 候选片段重新排序。"
            "例如 BAAI bge-reranker-base 会给候选 chunk 计算重排分。"
        ),
    ),
    RagEvalDocument(
        title="streaming_api.md",
        text=(
            "FastAPI SSE stream 会持续推送 workflow_node、sources、"
            "task_summary_chunk 和 final_report 事件到前端。"
        ),
    ),
)


DEFAULT_EVAL_CASES: tuple[RagEvalCase, ...] = (
    RagEvalCase(
        query="LangGraph fan-out 并行工作流",
        expected_document="langgraph_workflow.md",
        expected_terms=("fan-out", "并行子任务"),
    ),
    RagEvalCase(
        query="RAG 评测 Recall@K MRR 命中文档排名",
        expected_document="rag_evaluation.md",
        expected_terms=("Recall@K", "MRR"),
    ),
    RagEvalCase(
        query="扫描 PDF OCR Tesseract Poppler",
        expected_document="document_processing.md",
        expected_terms=("Tesseract", "Poppler"),
    ),
    RagEvalCase(
        query="Postgres pgvector embedding chunk 字段",
        expected_document="postgres_pgvector.md",
        expected_terms=("pgvector", "embedding"),
    ),
    RagEvalCase(
        query="中文文档检索质量",
        expected_document="chinese_search.md",
        expected_terms=("中文文档检索",),
    ),
    RagEvalCase(
        query="Cross Encoder rerank BAAI 候选片段重排",
        expected_document="rerank.md",
        expected_terms=("rerank", "重排"),
    ),
    RagEvalCase(
        query="FastAPI SSE workflow_node final_report 事件",
        expected_document="streaming_api.md",
        expected_terms=("workflow_node", "final_report"),
    ),
)


def evaluate_retrieval(
    cases: tuple[RagEvalCase, ...] | list[RagEvalCase] = DEFAULT_EVAL_CASES,
    documents: tuple[RagEvalDocument, ...] | list[RagEvalDocument] = DEFAULT_DOCUMENTS,
    *,
    top_k: int = 3,
    min_score: float = 0.1,
    dataset_name: str = "builtin-smoke",
    sample_only: bool | None = None,
) -> RagEvalReport:
    """Run a deterministic document-level retrieval evaluation."""

    if sample_only is None:
        sample_only = cases is DEFAULT_EVAL_CASES and documents is DEFAULT_DOCUMENTS
    safe_top_k = max(1, min(top_k, 20))
    repo = InMemoryResearchRepository()
    for document in documents:
        repo.save_document(
            filename=document.title,
            content_type="text/markdown",
            raw_text=document.text,
            size_bytes=len(document.text.encode("utf-8")),
        )

    retriever = RepositoryRetriever(repo, limit=safe_top_k, min_score=max(0.0, min_score))
    results: list[RagEvalCaseResult] = []
    for case in cases:
        chunks = retriever.retrieve(case.query)
        top_results = [_chunk_summary(chunk, index) for index, chunk in enumerate(chunks, start=1)]
        rank = _first_document_rank(case.expected_document, top_results)
        hit = rank is not None and rank <= safe_top_k
        terms_found = _expected_terms_found(case.expected_terms, top_results, case.expected_document)
        results.append(
            RagEvalCaseResult(
                query=case.query,
                expected_document=case.expected_document,
                hit=hit,
                rank=rank,
                reciprocal_rank=(1.0 / rank) if rank else 0.0,
                expected_terms_found=terms_found,
                top_results=top_results,
            )
        )

    query_count = len(results)
    hits = sum(1 for result in results if result.hit)
    terms_found = sum(1 for result in results if result.expected_terms_found)
    mrr = sum(result.reciprocal_rank for result in results) / query_count if query_count else 0.0
    summary = {
        "dataset": dataset_name,
        "sample_only": sample_only,
        "query_count": query_count,
        "hit_count": hits,
        "miss_count": query_count - hits,
        "top_k": safe_top_k,
        "recall_at_k": round(hits / query_count, 4) if query_count else 0.0,
        "mrr": round(mrr, 4),
        "expected_terms_coverage": round(terms_found / query_count, 4) if query_count else 0.0,
    }
    return RagEvalReport(summary=summary, cases=results)


def evaluate_dataset(
    dataset: RagEvalDataset,
    *,
    top_k: int = 3,
    min_score: float = 0.1,
) -> RagEvalReport:
    """Evaluate a named dataset while preserving its provenance in the report."""

    return evaluate_retrieval(
        dataset.cases,
        dataset.documents,
        top_k=top_k,
        min_score=min_score,
        dataset_name=dataset.name,
        sample_only=dataset.sample_only,
    )


def load_eval_dataset(path: str | Path) -> RagEvalDataset:
    """Load and validate a retrieval evaluation dataset from JSON."""

    dataset_path = Path(path)
    try:
        payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取评测数据集 {dataset_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("评测数据集根节点必须是 JSON 对象")

    name = _required_string(payload, "name", "评测数据集")
    raw_documents = payload.get("documents")
    raw_cases = payload.get("cases")
    if not isinstance(raw_documents, list) or not raw_documents:
        raise ValueError("评测数据集 documents 必须是非空数组")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("评测数据集 cases 必须是非空数组")

    documents: list[RagEvalDocument] = []
    for index, item in enumerate(raw_documents, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"documents[{index}] 必须是对象")
        documents.append(
            RagEvalDocument(
                title=_required_string(item, "title", f"documents[{index}]"),
                text=_required_string(item, "text", f"documents[{index}]"),
            )
        )
    titles = [document.title for document in documents]
    if len(titles) != len(set(titles)):
        raise ValueError("评测数据集文档 title 必须唯一")

    cases: list[RagEvalCase] = []
    for index, item in enumerate(raw_cases, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"cases[{index}] 必须是对象")
        expected_document = _required_string(item, "expected_document", f"cases[{index}]")
        if expected_document not in titles:
            raise ValueError(f"cases[{index}] 引用了不存在的文档: {expected_document}")
        raw_terms = item.get("expected_terms", [])
        if not isinstance(raw_terms, list) or not all(
            isinstance(term, str) and term.strip() for term in raw_terms
        ):
            raise ValueError(f"cases[{index}].expected_terms 必须是字符串数组")
        cases.append(
            RagEvalCase(
                query=_required_string(item, "query", f"cases[{index}]"),
                expected_document=expected_document,
                expected_terms=tuple(term.strip() for term in raw_terms),
            )
        )

    sample_only = payload.get("sample_only", False)
    if not isinstance(sample_only, bool):
        raise ValueError("评测数据集 sample_only 必须是布尔值")

    return RagEvalDataset(
        name=name,
        documents=tuple(documents),
        cases=tuple(cases),
        sample_only=sample_only,
    )


def _required_string(payload: dict[str, Any], key: str, location: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{location}.{key} 必须是非空字符串")
    return value.strip()


def _chunk_summary(chunk: Any, rank: int) -> dict[str, Any]:
    metadata = getattr(chunk, "metadata", {}) or {}
    return {
        "rank": rank,
        "document": chunk.document_title,
        "chunk_index": chunk.chunk_index,
        "score": metadata.get("score"),
        "bm25_score": metadata.get("bm25_score"),
        "vector_score": metadata.get("vector_score"),
        "rerank_score": metadata.get("rerank_score"),
        "matched_terms": metadata.get("matched_terms") or [],
        "snippet": metadata.get("snippet") or chunk.text[:220],
    }


def _first_document_rank(expected_document: str, top_results: list[dict[str, Any]]) -> int | None:
    for result in top_results:
        if result["document"] == expected_document:
            return int(result["rank"])
    return None


def _expected_terms_found(
    expected_terms: tuple[str, ...],
    top_results: list[dict[str, Any]],
    expected_document: str,
) -> bool:
    if not expected_terms:
        return True
    expected_text = " ".join(
        str(result.get("snippet") or "")
        for result in top_results
        if result.get("document") == expected_document
    )
    return all(term.lower() in expected_text.lower() for term in expected_terms)
