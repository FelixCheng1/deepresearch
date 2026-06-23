import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from services.rag_eval import RagEvalCase, RagEvalDocument, evaluate_retrieval


def test_builtin_rag_eval_reports_recall_and_mrr():
    report = evaluate_retrieval(top_k=3)
    payload = report.to_dict()

    assert payload["summary"]["query_count"] >= 5
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