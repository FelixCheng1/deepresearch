import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rag_benchmark_cli import parse_chunk_counts, run_benchmark


def test_parse_chunk_counts():
    assert parse_chunk_counts("10, 100,1000") == [10, 100, 1000]


def test_benchmark_reports_each_corpus_size():
    report = run_benchmark([20, 50], query_count=6, top_k=3)

    assert report["synthetic"] is True
    assert report["hardware_dependent"] is True
    assert [run["chunk_count"] for run in report["runs"]] == [20, 50]
    assert all(run["query_count"] == 6 for run in report["runs"])
    assert all(run["recall_at_k"] == 1.0 for run in report["runs"])
    assert all(run["latency_p95_ms"] >= run["latency_p50_ms"] >= 0 for run in report["runs"])


def test_benchmark_cli_json_output():
    script = Path(__file__).resolve().parents[1] / "src" / "rag_benchmark_cli.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--chunk-counts",
            "10,25",
            "--queries",
            "4",
            "--top-k",
            "2",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["benchmark"] == "synthetic-lexical-v1"
    assert [run["chunk_count"] for run in payload["runs"]] == [10, 25]
    assert all(run["top_k"] == 2 for run in payload["runs"])
