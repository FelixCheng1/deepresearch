"""Lightweight RAG retrieval evaluation helpers."""

from __future__ import annotations

from dataclasses import dataclass
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
) -> RagEvalReport:
    """Run a deterministic document-level retrieval evaluation."""

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
    mrr = sum(result.reciprocal_rank for result in results) / query_count if query_count else 0.0
    summary = {
        "query_count": query_count,
        "top_k": safe_top_k,
        "recall_at_k": round(hits / query_count, 4) if query_count else 0.0,
        "mrr": round(mrr, 4),
    }
    return RagEvalReport(summary=summary, cases=results)


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