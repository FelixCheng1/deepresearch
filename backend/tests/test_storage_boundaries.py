import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from config import Configuration
from models import ResearchReport, ResearchRun, ResearchSource, ResearchTask
from services.note_store import NoteStore
from services.repository import InMemoryResearchRepository
from services.retriever import DisabledRetriever
from helpers import make_notes_dir


def test_repository_saves_research_snapshots():
    repo = InMemoryResearchRepository()

    repo.save_run(ResearchRun(id="run-1", topic="topic", search_api="duckduckgo"))
    repo.save_task(
        ResearchTask(
            run_id="run-1",
            task_id=1,
            title="背景",
            intent="了解背景",
            query="topic",
            status="completed",
        )
    )
    repo.save_source(ResearchSource(run_id="run-1", task_id=1, title="Source", url="https://example.com"))
    repo.save_report(ResearchReport(run_id="run-1", markdown="# 报告"))

    assert repo.runs["run-1"].topic == "topic"
    assert repo.tasks[("run-1", 1)].status == "completed"
    assert repo.sources[0].url == "https://example.com"
    assert repo.reports["run-1"].markdown == "# 报告"


def test_note_store_create_read_update():
    store = NoteStore(str(make_notes_dir()))

    created = store.run(
        {
            "action": "create",
            "note_id": "note-1",
            "title": "Task",
            "note_type": "task_state",
            "tags": ["deep_research", "task_1"],
            "content": "initial",
        }
    )
    assert "ID: note-1" in created
    assert "initial" in store.read("note-1")

    updated = store.run(
        {
            "action": "update",
            "note_id": "note-1",
            "title": "Task",
            "note_type": "task_state",
            "tags": ["deep_research", "task_1"],
            "content": "updated",
        }
    )
    assert "ID: note-1" in updated
    assert "updated" in store.read("note-1")


def test_disabled_retriever_returns_empty_context():
    retriever = DisabledRetriever(Configuration(rag_enabled=False))

    assert retriever.retrieve("query") == []
    assert retriever.calls == ["query"]
