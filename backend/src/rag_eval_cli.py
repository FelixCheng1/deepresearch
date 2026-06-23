"""Run the built-in lightweight RAG retrieval evaluation."""

from __future__ import annotations

import argparse
import json

from services.rag_eval import evaluate_retrieval


def _print_text_report(report: dict) -> None:
    summary = report["summary"]
    print(
        "RAG eval summary: "
        f"queries={summary['query_count']} "
        f"top_k={summary['top_k']} "
        f"recall@k={summary['recall_at_k']:.4f} "
        f"mrr={summary['mrr']:.4f}"
    )
    print()
    for case in report["cases"]:
        marker = "PASS" if case["hit"] else "FAIL"
        rank = case["rank"] if case["rank"] is not None else "-"
        print(f"[{marker}] rank={rank} expected={case['expected_document']} query={case['query']}")
        for result in case["top_results"]:
            score = result.get("score")
            score_text = f" score={score}" if score is not None else ""
            print(
                f"  {result['rank']}. {result['document']}#chunk-{result['chunk_index']}"
                f"{score_text}"
            )
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run lightweight RAG retrieval evaluation.")
    parser.add_argument("--top-k", type=int, default=3, help="number of retrieved chunks to evaluate")
    parser.add_argument("--min-score", type=float, default=0.1, help="minimum text score for retrieval")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    report = evaluate_retrieval(top_k=args.top_k, min_score=args.min_score).to_dict()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_text_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())