"""Synthetic lexical retrieval benchmark for repeatable local measurements."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from time import perf_counter

from models import ResearchDocumentChunk
from services.retrieval_scoring import rank_chunks

TOPICS = (
    "langgraph workflow fanout state",
    "fastapi sse streaming event",
    "postgres pgvector embedding",
    "document parsing chunk retry",
    "hybrid retrieval rerank query",
    "research history source replay",
)


def parse_chunk_counts(value: str) -> list[int]:
    """Parse a comma-separated list while keeping benchmark sizes bounded."""

    try:
        counts = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("chunk counts must be comma-separated integers") from exc
    if not counts or any(count < 1 or count > 100_000 for count in counts):
        raise argparse.ArgumentTypeError("chunk counts must be between 1 and 100000")
    return counts


def build_chunks(count: int) -> list[ResearchDocumentChunk]:
    """Build a deterministic corpus with shared topics and one exact case id per chunk."""

    chunks: list[ResearchDocumentChunk] = []
    for index in range(count):
        topic = TOPICS[index % len(TOPICS)]
        case_id = f"case{index:05d}"
        chunks.append(
            ResearchDocumentChunk(
                id=f"chunk-{index}",
                document_id=f"document-{index}",
                document_title=f"{topic.split()[0]}-{index:05d}.md",
                chunk_index=1,
                text=(
                    f"{topic}. benchmark evidence {case_id}. "
                    "This deterministic paragraph measures lexical ranking cost and exact-id recall."
                ),
            )
        )
    return chunks


def run_benchmark(
    chunk_counts: list[int],
    *,
    query_count: int = 50,
    top_k: int = 5,
) -> dict:
    """Measure ranking latency and exact-id Recall@K over deterministic corpora."""

    safe_query_count = max(1, min(query_count, 1_000))
    safe_top_k = max(1, min(top_k, 20))
    runs = []
    for chunk_count in chunk_counts:
        chunks = build_chunks(chunk_count)
        targets = [((index * 9_973) + 17) % chunk_count for index in range(safe_query_count)]
        queries = [
            (
                f"{TOPICS[target % len(TOPICS)]} case{target:05d}",
                chunks[target].document_title,
            )
            for target in targets
        ]
        for query, _ in queries[: min(3, len(queries))]:
            rank_chunks(query, chunks, limit=safe_top_k, min_score=0.1)

        latencies_ms: list[float] = []
        hits = 0
        for query, expected_document in queries:
            started = perf_counter()
            ranked = rank_chunks(query, chunks, limit=safe_top_k, min_score=0.1)
            latencies_ms.append((perf_counter() - started) * 1_000)
            hits += int(any(chunk.document_title == expected_document for chunk in ranked))

        mean_ms = statistics.fmean(latencies_ms)
        runs.append(
            {
                "chunk_count": chunk_count,
                "query_count": safe_query_count,
                "top_k": safe_top_k,
                "recall_at_k": round(hits / safe_query_count, 4),
                "latency_p50_ms": round(statistics.median(latencies_ms), 3),
                "latency_p95_ms": round(_percentile(latencies_ms, 0.95), 3),
                "queries_per_second": round(1_000 / mean_ms, 2) if mean_ms else 0.0,
            }
        )
    return {
        "benchmark": "synthetic-lexical-v1",
        "synthetic": True,
        "hardware_dependent": True,
        "runs": runs,
    }


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark deterministic lexical retrieval.")
    parser.add_argument("--chunk-counts", type=parse_chunk_counts, default=[100, 1_000, 5_000])
    parser.add_argument("--queries", type=int, default=50)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = run_benchmark(args.chunk_counts, query_count=args.queries, top_k=args.top_k)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Synthetic benchmark; latency is hardware-dependent and not a production SLA.")
        for run in report["runs"]:
            print(
                f"chunks={run['chunk_count']} queries={run['query_count']} "
                f"recall@{run['top_k']}={run['recall_at_k']:.4f} "
                f"p50={run['latency_p50_ms']:.3f}ms "
                f"p95={run['latency_p95_ms']:.3f}ms "
                f"qps={run['queries_per_second']:.2f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
