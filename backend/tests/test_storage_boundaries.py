import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from helpers import make_notes_dir
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import Configuration
from models import (
    ResearchReport,
    ResearchRun,
    ResearchSource,
    ResearchTask,
    ResearchToolCall,
)
from services.database import Base
from services.note_store import NoteStore
from services.repository import (
    InMemoryResearchRepository,
    PostgresResearchRepository,
    create_research_repository,
)
from services.retriever import DisabledRetriever


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
            summary="summary",
            sources_summary="sources",
        )
    )
    repo.save_source(ResearchSource(run_id="run-1", task_id=1, title="Source", url="https://example.com"))
    repo.save_tool_call(
        ResearchToolCall(
            run_id="run-1",
            event_id=1,
            agent="research",
            tool="search",
            parameters={"query": "topic"},
            result="ok",
            task_id=1,
            step=1,
        )
    )
    repo.save_report(ResearchReport(run_id="run-1", markdown="# 报告"))

    assert repo.runs["run-1"].topic == "topic"
    assert repo.tasks[("run-1", 1)].status == "completed"
    assert repo.get_run("run-1")["tasks"][0]["summary"] == "summary"
    assert repo.sources[0].url == "https://example.com"
    assert repo.reports["run-1"].markdown == "# 报告"
    assert repo.get_run("run-1")["tool_calls"][0]["tool"] == "search"


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


def test_repository_factory_uses_memory_without_database_url():
    repo = create_research_repository(Configuration(database_url=None))

    assert isinstance(repo, InMemoryResearchRepository)


def test_sqlalchemy_repository_saves_and_reads_history():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    repo = PostgresResearchRepository(
        session_factory=sessionmaker(bind=engine, expire_on_commit=False, future=True)
    )

    repo.save_run(ResearchRun(id="run-db", topic="数据库", search_api="duckduckgo"))
    repo.save_task(
        ResearchTask(
            run_id="run-db",
            task_id=1,
            title="背景",
            intent="了解背景",
            query="database background",
            status="in_progress",
            note_id="note-1",
            note_path="notes/note-1.md",
        )
    )
    repo.save_task(
        ResearchTask(
            run_id="run-db",
            task_id=1,
            title="背景",
            intent="了解背景",
            query="database background",
            status="completed",
            summary="数据库任务总结",
            sources_summary="数据库来源",
            note_id="note-1",
            note_path="notes/note-1.md",
        )
    )
    repo.save_source(
        ResearchSource(
            run_id="run-db",
            task_id=1,
            title="Source",
            url="https://example.com",
            content="content",
        )
    )
    repo.save_tool_call(
        ResearchToolCall(
            run_id="run-db",
            event_id=1,
            agent="research",
            tool="note",
            parameters={"note_id": "note-1"},
            result="saved",
            task_id=1,
            note_id="note-1",
            step=1,
        )
    )
    repo.save_report(ResearchReport(run_id="run-db", markdown="# 报告", note_id="report-1"))

    runs = repo.list_runs()
    detail = repo.get_run("run-db")

    assert runs[0]["id"] == "run-db"
    assert detail is not None
    assert detail["topic"] == "数据库"
    assert detail["tasks"][0]["status"] == "completed"
    assert detail["tasks"][0]["summary"] == "数据库任务总结"
    assert detail["tasks"][0]["sources_summary"] == "数据库来源"
    assert len(detail["tasks"]) == 1
    assert detail["sources"][0]["url"] == "https://example.com"
    assert detail["report"]["markdown"] == "# 报告"
    assert detail["tool_calls"][0]["parameters"] == {"note_id": "note-1"}

