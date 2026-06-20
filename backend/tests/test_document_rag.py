import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import agent as agent_module
import main as main_module
from config import Configuration
from models import ResearchDocumentChunk
from services.chunker import chunk_text
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from services.database import Base, DocumentChunkRow
from services.repository import InMemoryResearchRepository, PostgresResearchRepository, _tokenize
from services.retriever import RepositoryRetriever
from test_agent_api import FakeChatModel, empty_search, fake_search
from helpers import make_notes_dir


def test_chunk_text_splits_paragraphs_with_overlap():
    text = "第一段内容。\n\n" + "第二段" * 500 + "\n\n第三段内容。"

    chunks = chunk_text(text, max_chars=120, overlap=12)

    assert len(chunks) > 1
    assert all(len(chunk) <= 140 for chunk in chunks)
    assert chunks[0].startswith("第一段内容")


def test_document_repository_saves_lists_gets_and_searches_chunks():
    repo = InMemoryResearchRepository()

    document = repo.save_document(
        filename="notes.md",
        content_type="text/markdown",
        raw_text="LangGraph 支持并行 fan-out。\n\nRAG 文档库会保存 chunk。",
        size_bytes=64,
    )

    documents = repo.list_documents()
    detail = repo.get_document(document.id)
    chunks = repo.search_document_chunks("LangGraph fan-out", limit=3)

    assert documents[0]["id"] == document.id
    assert documents[0]["chunk_count"] >= 1
    assert detail is not None
    assert detail["filename"] == "notes.md"
    assert detail["chunks"][0]["text"]
    assert chunks
    assert chunks[0].document_id == document.id

def test_memory_repository_delete_document_removes_chunks_from_search():
    repo = InMemoryResearchRepository()
    document = repo.save_document(
        filename="delete-me.md",
        content_type="text/markdown",
        raw_text="LangGraph 删除文档后不应再参与 RAG 检索。",
        size_bytes=80,
    )

    assert repo.delete_document(document.id) is True
    assert repo.get_document(document.id) is None
    assert repo.list_documents() == []
    assert repo.search_document_chunks("LangGraph 删除文档", limit=3) == []
    assert repo.delete_document(document.id) is False


def test_sqlalchemy_repository_delete_document_cascades_chunks():
    from sqlalchemy import create_engine

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    repo = PostgresResearchRepository(
        session_factory=sessionmaker(bind=engine, expire_on_commit=False, future=True)
    )
    document = repo.save_document(
        filename="db-delete.txt",
        content_type="text/plain",
        raw_text="数据库文档删除后 chunk 应级联消失。",
        size_bytes=80,
    )

    assert repo.delete_document(document.id) is True
    assert repo.get_document(document.id) is None
    assert repo.search_document_chunks("数据库文档删除", limit=3) == []
    with sessionmaker(bind=engine, expire_on_commit=False, future=True)() as session:
        assert session.scalars(select(DocumentChunkRow)).all() == []
    assert repo.delete_document(document.id) is False


def test_repository_retriever_returns_matching_document_chunks():
    repo = InMemoryResearchRepository()
    repo.save_document(
        filename="rag.txt",
        content_type="text/plain",
        raw_text="上传文档会切块入库，检索节点可以读取相关 chunk。",
        size_bytes=80,
    )
    retriever = RepositoryRetriever(repo)

    chunks = retriever.retrieve("检索 chunk")

    assert chunks
    assert "chunk" in chunks[0].text

def test_rag_tokenizer_supports_english_numbers_and_cjk_bigrams():
    tokens = _tokenize("LangGraph 2026 文档检索质量")

    assert "langgraph" in tokens
    assert "2026" in tokens
    assert "文档" in tokens
    assert "检索" in tokens


def test_ranker_prefers_title_and_phrase_matches():
    repo = InMemoryResearchRepository()
    title_doc = repo.save_document(
        filename="LangGraph-RAG.md",
        content_type="text/markdown",
        raw_text="这份资料讨论检索流程、任务上下文和引用来源。",
        size_bytes=90,
    )
    repo.save_document(
        filename="notes.txt",
        content_type="text/plain",
        raw_text="这份资料讨论检索流程、任务上下文和引用来源。",
        size_bytes=90,
    )

    chunks = repo.search_document_chunks("LangGraph RAG 检索流程", limit=2, min_score=0.1)

    assert chunks
    assert chunks[0].document_id == title_doc.id
    assert chunks[0].metadata["score"] > 0
    assert chunks[0].metadata["matched_terms"]
    assert chunks[0].metadata["snippet"]

def test_ranker_filters_low_score_and_respects_top_k():
    repo = InMemoryResearchRepository()
    repo.save_document(filename="a.txt", content_type="text/plain", raw_text="alpha beta gamma", size_bytes=20)
    repo.save_document(filename="b.txt", content_type="text/plain", raw_text="alpha beta delta", size_bytes=20)
    repo.save_document(filename="c.txt", content_type="text/plain", raw_text="completely unrelated", size_bytes=24)

    chunks = repo.search_document_chunks("alpha beta", limit=1, min_score=0.1)
    filtered = repo.search_document_chunks("alpha beta", limit=5, min_score=999)

    assert len(chunks) == 1
    assert "alpha" in chunks[0].text
    assert filtered == []


def test_ranker_matches_chinese_query_without_spaces():
    repo = InMemoryResearchRepository()
    repo.save_document(
        filename="local.txt",
        content_type="text/plain",
        raw_text="本地知识库支持中文文档检索质量评估。",
        size_bytes=80,
    )

    chunks = repo.search_document_chunks("文档检索质量", limit=3, min_score=0.1)

    assert chunks
    assert "中文文档检索" in chunks[0].text


def test_fastapi_document_upload_list_and_get(monkeypatch):
    repo = InMemoryResearchRepository()
    monkeypatch.setattr(main_module, "create_research_repository", lambda config: repo)
    app = main_module.create_app()

    from fastapi.testclient import TestClient

    client = TestClient(app)
    upload = client.post(
        "/documents/upload",
        files={"file": ("memo.md", "# 标题\n\n这里是 RAG 文档库内容。", "text/markdown")},
    )
    assert upload.status_code == 200
    document_id = upload.json()["document"]["id"]

    listed = client.get("/documents")
    detail = client.get(f"/documents/{document_id}")
    deleted = client.delete(f"/documents/{document_id}")
    missing_detail = client.get(f"/documents/{document_id}")
    missing_delete = client.delete(f"/documents/{document_id}")
    listed_after_delete = client.get("/documents")
    rejected = client.post(
        "/documents/upload",
        files={"file": ("paper.pdf", b"%PDF", "application/pdf")},
    )

    assert listed.status_code == 200
    assert listed.json()["documents"][0]["filename"] == "memo.md"
    assert detail.status_code == 200
    assert detail.json()["chunks"]
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True, "document_id": document_id}
    assert missing_detail.status_code == 404
    assert missing_delete.status_code == 404
    assert listed_after_delete.json()["documents"] == []
    assert rejected.status_code == 400


def test_rag_enabled_retrieve_documents_returns_uploaded_chunk(monkeypatch):
    monkeypatch.setattr(agent_module, "dispatch_search", empty_search)
    repo = InMemoryResearchRepository()
    repo.save_document(
        filename="local.txt",
        content_type="text/plain",
        raw_text="topic background 来自本地文档库。LangGraph RAG retrieval quality 也在这里。这个 chunk 应被 retrieve_documents 返回。",
        size_bytes=90,
    )
    config = Configuration(enable_notes=True, notes_workspace=str(make_notes_dir()), rag_enabled=True)
    deep_agent = agent_module.DeepResearchAgent(
        config=config,
        repository=repo,
        chat_model=FakeChatModel(),
    )

    events = list(deep_agent.run_stream("topic"))
    retrieval_done = [
        event
        for event in events
        if event["type"] == "workflow_node"
        and event["node"] == "retrieve_documents"
        and event["status"] == "completed"
    ]
    source_events = [event for event in events if event["type"] == "sources"]

    assert retrieval_done
    assert source_events
    assert "document://" in source_events[0]["latest_sources"]
    assert "本地文档库" in source_events[0]["raw_context"]
    assert "相关度" in source_events[0]["latest_sources"]
    assert "命中:" in source_events[0]["latest_sources"]


def test_rag_disabled_still_skips_without_touching_retriever(monkeypatch):
    monkeypatch.setattr(agent_module, "dispatch_search", fake_search)

    class ExplodingRetriever:
        def retrieve(self, query: str) -> list[ResearchDocumentChunk]:
            raise AssertionError("RAG 关闭时不应调用 retriever")

    config = Configuration(enable_notes=True, notes_workspace=str(make_notes_dir()), rag_enabled=False)
    deep_agent = agent_module.DeepResearchAgent(
        config=config,
        retriever=ExplodingRetriever(),
        chat_model=FakeChatModel(),
    )

    result = deep_agent.run("topic")

    assert result.todo_items[0].status == "completed"
