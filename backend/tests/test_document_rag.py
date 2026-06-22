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
from services.document_parser import DocumentParseError, parse_document
from services.document_worker import process_one_document_job
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



class FakeReranker:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls = []

    def rerank(self, query, chunks, limit):
        self.calls.append((query, chunks, limit))
        if self.fail:
            raise RuntimeError("rerank failed")
        ranked = list(reversed(chunks))[:limit]
        for index, chunk in enumerate(ranked, start=1):
            chunk.metadata = {**chunk.metadata, "rerank_score": 100 - index}
        return ranked


def test_repository_retriever_reranks_candidates_when_enabled():
    repo = InMemoryResearchRepository()
    first = repo.save_document(filename="a.txt", content_type="text/plain", raw_text="alpha beta first", size_bytes=20)
    second = repo.save_document(filename="b.txt", content_type="text/plain", raw_text="alpha beta second", size_bytes=20)
    reranker = FakeReranker()
    retriever = RepositoryRetriever(repo, limit=1, reranker=reranker, rerank_top_n=2)

    chunks = retriever.retrieve("alpha beta")

    assert len(chunks) == 1
    assert chunks[0].document_id == second.id
    assert chunks[0].metadata["rerank_score"] == 99
    assert reranker.calls
    assert first.id != second.id


def test_repository_retriever_falls_back_when_rerank_fails():
    repo = InMemoryResearchRepository()
    repo.save_document(filename="a.txt", content_type="text/plain", raw_text="alpha beta first", size_bytes=20)
    repo.save_document(filename="b.txt", content_type="text/plain", raw_text="alpha beta second", size_bytes=20)
    retriever = RepositoryRetriever(repo, limit=1, reranker=FakeReranker(fail=True), rerank_top_n=2)

    chunks = retriever.retrieve("alpha beta")

    assert len(chunks) == 1
    assert "rerank_score" not in chunks[0].metadata


def test_repository_retriever_does_not_rerank_when_disabled():
    repo = InMemoryResearchRepository()
    repo.save_document(filename="a.txt", content_type="text/plain", raw_text="alpha beta first", size_bytes=20)
    reranker = FakeReranker()
    retriever = RepositoryRetriever(repo, limit=1)

    chunks = retriever.retrieve("alpha beta")

    assert chunks
    assert reranker.calls == []


def test_pdf_parse_uses_native_text_before_ocr(monkeypatch):
    def fail_ocr(payload, config):
        raise AssertionError("OCR should not run when PDF text exists")

    monkeypatch.setattr("services.document_parser._extract_pdf_text", lambda payload: "native pdf text")
    monkeypatch.setattr("services.document_parser._ocr_pdf", fail_ocr)

    text, content_type = parse_document("paper.pdf", "application/pdf", b"pdf", Configuration(pdf_ocr_enabled=True))

    assert text == "native pdf text"
    assert content_type == "application/pdf"


def test_pdf_parse_empty_without_ocr_fails(monkeypatch):
    monkeypatch.setattr("services.document_parser._extract_pdf_text", lambda payload: "")

    try:
        parse_document("scan.pdf", "application/pdf", b"pdf", Configuration(pdf_ocr_enabled=False))
    except DocumentParseError as exc:
        assert "OCR is disabled" in str(exc)
    else:
        raise AssertionError("expected DocumentParseError")


def test_pdf_parse_empty_with_ocr_uses_ocr(monkeypatch):
    monkeypatch.setattr("services.document_parser._extract_pdf_text", lambda payload: "")
    monkeypatch.setattr("services.document_parser._ocr_pdf", lambda payload, config: "ocr extracted text")

    text, content_type = parse_document("scan.pdf", "application/pdf", b"pdf", Configuration(pdf_ocr_enabled=True))

    assert text == "ocr extracted text"
    assert content_type == "application/pdf"


def test_pdf_ocr_failure_is_clear(monkeypatch):
    monkeypatch.setattr("services.document_parser._extract_pdf_text", lambda payload: "")

    def fail_ocr(payload, config):
        raise DocumentParseError("PDF OCR failed; check Tesseract and Poppler installation")

    monkeypatch.setattr("services.document_parser._ocr_pdf", fail_ocr)

    try:
        parse_document("scan.pdf", "application/pdf", b"pdf", Configuration(pdf_ocr_enabled=True))
    except DocumentParseError as exc:
        assert "Tesseract and Poppler" in str(exc)
    else:
        raise AssertionError("expected DocumentParseError")


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
    assert upload.json()["document"]["status"] == "processing"
    assert len(repo.document_jobs) == 1
    assert next(iter(repo.document_jobs.values()))["status"] == "pending"
    assert process_one_document_job(repo) is True

    listed = client.get("/documents")
    detail = client.get(f"/documents/{document_id}")
    deleted = client.delete(f"/documents/{document_id}")
    missing_detail = client.get(f"/documents/{document_id}")
    missing_delete = client.delete(f"/documents/{document_id}")
    listed_after_delete = client.get("/documents")
    rejected = client.post(
        "/documents/upload",
        files={"file": ("sheet.csv", b"a,b", "text/csv")},
    )

    assert listed.status_code == 200
    assert listed.json()["documents"][0]["filename"] == "memo.md"
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert listed.json()["documents"][0]["status"] == "ready"
    assert listed.json()["documents"][0]["processed_at"]
    assert detail_payload["status"] == "ready"
    assert detail_payload["chunks"]
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True, "document_id": document_id}
    assert missing_detail.status_code == 404
    assert missing_delete.status_code == 404
    assert listed_after_delete.json()["documents"] == []
    assert rejected.status_code == 400



def test_memory_repository_document_processing_status_flow():
    repo = InMemoryResearchRepository()
    pending = repo.create_pending_document(
        filename="async.md",
        content_type="text/markdown",
        size_bytes=32,
    )

    assert repo.get_document(pending.id)["status"] == "processing"
    assert repo.get_document(pending.id)["chunks"] == []
    job = repo.enqueue_document_job(pending.id, b"async document text for retrieval")
    claimed = repo.claim_next_document_job()
    assert claimed["id"] == job["id"]
    assert claimed["status"] == "running"
    assert claimed["attempts"] == 1

    assert repo.complete_document_processing(
        pending.id,
        raw_text="async document text for retrieval",
        content_type="text/markdown",
    ) is True
    ready = repo.get_document(pending.id)

    assert ready["status"] == "ready"
    assert ready["processed_at"]
    assert ready["chunks"]
    assert ready["created_at"] == pending.created_at.isoformat()
    assert repo.succeed_document_job(job["id"]) is True
    assert repo.document_jobs[job["id"]]["status"] == "succeeded"

    failed = repo.create_pending_document(
        filename="empty.pdf",
        content_type="application/pdf",
        size_bytes=10,
    )
    assert repo.fail_document_processing(failed.id, "empty pdf") is True
    failed_detail = repo.get_document(failed.id)

    assert failed_detail["status"] == "failed"
    assert failed_detail["error_message"] == "empty pdf"
    assert failed_detail["chunks"] == []


def test_fastapi_pdf_docx_upload_uses_background_parser(monkeypatch):
    repo = InMemoryResearchRepository()
    monkeypatch.setattr(main_module, "create_research_repository", lambda config: repo)

    calls = []

    def fake_parse_document(filename, content_type, payload, config=None):
        calls.append((filename, content_type, payload))
        if filename.endswith(".pdf"):
            return "pdf extracted local retrieval text", "application/pdf"
        return "docx paragraph text\n\ntable cell text", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    monkeypatch.setattr("services.document_worker.parse_document", fake_parse_document)
    app = main_module.create_app()

    from fastapi.testclient import TestClient

    client = TestClient(app)
    pdf_upload = client.post(
        "/documents/upload",
        files={"file": ("paper.pdf", b"%PDF sample", "application/pdf")},
    )
    docx_upload = client.post(
        "/documents/upload",
        files={
            "file": (
                "memo.docx",
                b"docx sample",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert pdf_upload.status_code == 200
    assert docx_upload.status_code == 200
    assert pdf_upload.json()["document"]["status"] == "processing"
    assert docx_upload.json()["document"]["status"] == "processing"
    assert process_one_document_job(repo) is True
    assert process_one_document_job(repo) is True
    assert [call[0] for call in calls] == ["paper.pdf", "memo.docx"]

    documents = client.get("/documents").json()["documents"]
    assert {document["filename"]: document["status"] for document in documents} == {
        "memo.docx": "ready",
        "paper.pdf": "ready",
    }
    assert all(document["chunk_count"] >= 1 for document in documents)


def test_fastapi_pdf_upload_failure_marks_document_failed(monkeypatch):
    repo = InMemoryResearchRepository()
    monkeypatch.setattr(main_module, "create_research_repository", lambda config: repo)

    def fake_parse_document(filename, content_type, payload, config=None):
        raise DocumentParseError("empty pdf")

    monkeypatch.setattr("services.document_worker.parse_document", fake_parse_document)
    app = main_module.create_app()

    from fastapi.testclient import TestClient

    client = TestClient(app)
    upload = client.post(
        "/documents/upload",
        files={"file": ("scan.pdf", b"%PDF empty", "application/pdf")},
    )
    document_id = upload.json()["document"]["id"]
    assert process_one_document_job(repo) is True
    detail = client.get(f"/documents/{document_id}").json()

    assert upload.status_code == 200
    assert upload.json()["document"]["status"] == "processing"
    assert detail["status"] == "failed"
    assert detail["error_message"] == "empty pdf"
    assert detail["chunks"] == []


def test_fastapi_retry_failed_document_requeues_job(monkeypatch):
    repo = InMemoryResearchRepository()
    monkeypatch.setattr(main_module, "create_research_repository", lambda config: repo)

    def fail_parse(filename, content_type, payload, config=None):
        raise DocumentParseError("empty pdf")

    monkeypatch.setattr("services.document_worker.parse_document", fail_parse)
    app = main_module.create_app()

    from fastapi.testclient import TestClient

    client = TestClient(app)
    upload = client.post(
        "/documents/upload",
        files={"file": ("scan.pdf", b"%PDF empty", "application/pdf")},
    )
    document_id = upload.json()["document"]["id"]
    assert process_one_document_job(repo) is True

    ready_retry = client.post(f"/documents/{document_id}/retry")
    assert ready_retry.status_code == 200
    assert ready_retry.json()["document"]["status"] == "processing"
    assert len([job for job in repo.document_jobs.values() if job["status"] == "pending"]) == 1

    processing_retry = client.post(f"/documents/{document_id}/retry")
    assert processing_retry.status_code == 400


def test_retry_ready_document_returns_400(monkeypatch):
    repo = InMemoryResearchRepository()
    monkeypatch.setattr(main_module, "create_research_repository", lambda config: repo)
    app = main_module.create_app()

    from fastapi.testclient import TestClient

    document = repo.save_document(
        filename="ready.md",
        content_type="text/markdown",
        raw_text="ready document",
        size_bytes=20,
    )
    client = TestClient(app)

    response = client.post(f"/documents/{document.id}/retry")

    assert response.status_code == 400


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
    assert "BM25" in source_events[0]["latest_sources"]
    assert "命中:" in source_events[0]["latest_sources"]


def test_document_sources_include_rerank_score():
    deep_agent = agent_module.DeepResearchAgent(
        config=Configuration(enable_notes=True, notes_workspace=str(make_notes_dir()), rag_enabled=True),
        repository=InMemoryResearchRepository(),
        chat_model=FakeChatModel(),
    )
    chunk = ResearchDocumentChunk(
        id="chunk-1",
        document_id="doc-1",
        document_title="local.md",
        chunk_index=2,
        text="reranked local evidence",
        metadata={"score": 12.3, "bm25_score": 1.2, "vector_score": 45.6, "rerank_score": 98.7},
    )

    summary = deep_agent._format_document_sources([chunk])

    assert "document://doc-1#chunk-2" in summary
    assert "重排 98.70" in summary


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
