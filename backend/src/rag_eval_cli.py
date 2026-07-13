"""Run the built-in lightweight RAG retrieval evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.rag_eval import evaluate_dataset, evaluate_retrieval, load_eval_dataset


def _metric_threshold(value: str) -> float:
    threshold = float(value)
    if not 0 <= threshold <= 1:
        raise argparse.ArgumentTypeError("metric threshold must be between 0 and 1")
    return threshold


def _print_text_report(report: dict) -> None:
    summary = report["summary"]
    print(
        "RAG eval summary: "
        f"dataset={summary['dataset']} "
        f"queries={summary['query_count']} "
        f"top_k={summary['top_k']} "
        f"recall@k={summary['recall_at_k']:.4f} "
        f"mrr={summary['mrr']:.4f}"
    )
    if summary["sample_only"]:
        print("NOTE: built-in data is a smoke set; do not treat these metrics as production quality.")
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
    parser.add_argument("--dataset", type=Path, help="versioned JSON dataset to evaluate")
    parser.add_argument(
        "--fail-below-recall",
        type=_metric_threshold,
        help="exit with status 1 below Recall@K",
    )
    parser.add_argument(
        "--fail-below-mrr",
        type=_metric_threshold,
        help="exit with status 1 below MRR",
    )
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    if args.dataset:
        dataset = load_eval_dataset(args.dataset)
        report = evaluate_dataset(dataset, top_k=args.top_k, min_score=args.min_score).to_dict()
    else:
        report = evaluate_retrieval(top_k=args.top_k, min_score=args.min_score).to_dict()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_text_report(report)

    summary = report["summary"]
    failed_recall = (
        args.fail_below_recall is not None
        and summary["recall_at_k"] < args.fail_below_recall
    )
    failed_mrr = args.fail_below_mrr is not None and summary["mrr"] < args.fail_below_mrr
    return 1 if failed_recall or failed_mrr else 0


if __name__ == "__main__":
    raise SystemExit(main())
