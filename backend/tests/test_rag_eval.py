import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from helpers import make_test_dir

from services.rag_eval import (
    RagEvalCase,
    RagEvalDocument,
    evaluate_dataset,
    evaluate_retrieval,
    load_eval_dataset,
)


def test_builtin_rag_eval_reports_recall_and_mrr():
    report = evaluate_retrieval(top_k=3)
    payload = report.to_dict()

    assert payload["summary"]["query_count"] >= 5
    assert payload["summary"]["dataset"] == "builtin-smoke"
    assert payload["summary"]["sample_only"] is True
    assert payload["summary"]["top_k"] == 3
    assert payload["summary"]["recall_at_k"] >= 0.8
    assert payload["summary"]["mrr"] > 0
    assert all("top_results" in case for case in payload["cases"])


def test_rag_eval_handles_miss_case():
    documents = [
        RagEvalDocument(title="alpha.md", text="alpha beta gamma document"),
        RagEvalDocument(title="delta.md", text="delta epsilon zeta document"),
    ]
    cases = [RagEvalCase(query="alpha beta", expected_document="missing.md")]

    report = evaluate_retrieval(cases, documents, top_k=2)
    case = report.cases[0]

    assert report.summary["recall_at_k"] == 0.0
    assert case.hit is False
    assert case.rank is None
    assert case.reciprocal_rank == 0.0


def test_rag_eval_matches_chinese_query_without_spaces():
    documents = [
        RagEvalDocument(title="local.md", text="本地知识库支持中文文档检索质量评估。"),
        RagEvalDocument(title="other.md", text="网页搜索和摘要生成是另一个模块。"),
    ]
    cases = [
        RagEvalCase(
            query="文档检索质量",
            expected_document="local.md",
            expected_terms=("中文文档检索",),
        )
    ]

    report = evaluate_retrieval(cases, documents, top_k=1)
    case = report.cases[0]

    assert case.hit is True
    assert case.rank == 1
    assert case.expected_terms_found is True


def test_rag_eval_cli_json_output():
    script = Path(__file__).resolve().parents[1] / "src" / "rag_eval_cli.py"
    result = subprocess.run(
        [sys.executable, str(script), "--json", "--top-k", "2"],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)

    assert payload["summary"]["top_k"] == 2
    assert "recall_at_k" in payload["summary"]
    assert "mrr" in payload["summary"]
    assert payload["cases"]
    assert {"query", "expected_document", "hit", "rank", "top_results"}.issubset(payload["cases"][0])


def test_load_eval_dataset_preserves_provenance():
    dataset_path = make_test_dir() / "dataset.json"
    dataset_path.write_text(
        json.dumps(
            {
                "name": "project-docs-v1",
                "documents": [
                    {"title": "workflow.md", "text": "LangGraph 支持并行任务分发与汇总。"},
                    {"title": "storage.md", "text": "PostgreSQL 保存研究历史。"},
                ],
                "cases": [
                    {
                        "query": "并行研究任务",
                        "expected_document": "workflow.md",
                        "expected_terms": ["并行任务"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    dataset = load_eval_dataset(dataset_path)
    report = evaluate_dataset(dataset, top_k=1).to_dict()

    assert report["summary"]["dataset"] == "project-docs-v1"
    assert report["summary"]["sample_only"] is False
    assert report["summary"]["recall_at_k"] == 1.0


def test_load_eval_dataset_rejects_unknown_expected_document():
    dataset_path = make_test_dir() / "invalid.json"
    dataset_path.write_text(
        json.dumps(
            {
                "name": "invalid",
                "documents": [{"title": "known.md", "text": "known text"}],
                "cases": [{"query": "missing", "expected_document": "missing.md"}],
            }
        ),
        encoding="utf-8",
    )

    try:
        load_eval_dataset(dataset_path)
    except ValueError as exc:
        assert "不存在的文档" in str(exc)
    else:
        raise AssertionError("invalid dataset should be rejected")


def test_rag_eval_cli_can_enforce_metric_threshold():
    dataset_path = make_test_dir() / "miss.json"
    dataset_path.write_text(
        json.dumps(
            {
                "name": "threshold-check",
                "documents": [{"title": "known.md", "text": "alpha beta"}],
                "cases": [{"query": "unrelated query", "expected_document": "known.md"}],
            }
        ),
        encoding="utf-8",
    )
    script = Path(__file__).resolve().parents[1] / "src" / "rag_eval_cli.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--dataset",
            str(dataset_path),
            "--fail-below-recall",
            "0.5",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert json.loads(result.stdout)["summary"]["recall_at_k"] == 0.0
