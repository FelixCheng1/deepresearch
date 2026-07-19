import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import main as main_module
from config import Configuration
from models import ResearchRun
from services.auth import AuthenticatedUser, require_user
from services.database import Base
from services.repository import InMemoryResearchRepository, PostgresResearchRepository


def make_request(authorization: str | None = None) -> Request:
    headers = [] if authorization is None else [(b"authorization", authorization.encode())]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


def test_require_user_rejects_missing_and_invalid_token(monkeypatch):
    config = Configuration(auth_required=True, cloudbase_env_id="env-test")
    with pytest.raises(HTTPException) as missing:
        require_user(make_request(), config)
    assert missing.value.status_code == 401

    class InvalidResponse:
        status_code = 401

    monkeypatch.setattr("services.auth.requests.get", lambda *args, **kwargs: InvalidResponse())
    with pytest.raises(HTTPException) as invalid:
        require_user(make_request("Bearer invalid-token"), config)
    assert invalid.value.status_code == 401

    with pytest.raises(HTTPException) as expired:
        require_user(make_request("Bearer expired-token"), config)
    assert expired.value.status_code == 401


def test_require_user_extracts_subject(monkeypatch):
    config = Configuration(auth_required=True, cloudbase_env_id="env-test")

    class ValidResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"sub": "user-a"}

    monkeypatch.setattr("services.auth.requests.get", lambda *args, **kwargs: ValidResponse())
    assert require_user(make_request("Bearer valid-token-user-a"), config).id == "user-a"


def test_api_resources_are_isolated_by_authenticated_user(monkeypatch):
    repo = InMemoryResearchRepository()
    repo.save_run(ResearchRun(id="run-a", topic="A", search_api="duckduckgo", owner_id="user-a"))
    repo.save_run(ResearchRun(id="run-b", topic="B", search_api="duckduckgo", owner_id="user-b"))
    document_a = repo.save_document(filename="a.md", content_type="text/markdown", raw_text="alpha private", size_bytes=13, owner_id="user-a")
    document_b = repo.save_document(filename="b.md", content_type="text/markdown", raw_text="beta private", size_bytes=12, owner_id="user-b")

    monkeypatch.setattr(main_module, "create_research_repository", lambda config: repo)
    monkeypatch.setattr(
        main_module,
        "require_user",
        lambda request, config: AuthenticatedUser(id=request.headers.get("x-test-user", "missing")),
    )
    client = TestClient(main_module.create_app())
    headers_a = {"x-test-user": "user-a"}
    headers_b = {"x-test-user": "user-b"}

    assert [item["id"] for item in client.get("/research/runs", headers=headers_a).json()["runs"]] == ["run-a"]
    assert [item["id"] for item in client.get("/research/runs", headers=headers_b).json()["runs"]] == ["run-b"]
    assert client.get("/research/runs/run-b", headers=headers_a).status_code == 404
    assert [item["id"] for item in client.get("/documents", headers=headers_a).json()["documents"]] == [document_a.id]
    assert [item["id"] for item in client.get("/documents", headers=headers_b).json()["documents"]] == [document_b.id]
    assert client.get(f"/documents/{document_b.id}", headers=headers_a).status_code == 404
    assert client.post(f"/documents/{document_b.id}/retry", headers=headers_a).status_code == 404
    assert client.delete(f"/documents/{document_b.id}", headers=headers_a).status_code == 404
    assert repo.get_document(document_b.id, owner_id="user-b") is not None
    assert [chunk.document_id for chunk in repo.search_document_chunks("private", owner_id="user-a")] == [document_a.id]


def test_sql_repository_filters_owner_before_limit():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    repo = PostgresResearchRepository(session_factory=sessionmaker(bind=engine, expire_on_commit=False, future=True))
    older = datetime.now(timezone.utc) - timedelta(days=1)
    newer = datetime.now(timezone.utc)

    repo.save_run(ResearchRun(id="run-a", topic="A", search_api="duckduckgo", owner_id="user-a", created_at=older))
    for index in range(3):
        repo.save_run(ResearchRun(id=f"run-b-{index}", topic="B", search_api="duckduckgo", owner_id="user-b", created_at=newer + timedelta(seconds=index)))

    document_a = repo.save_document(filename="a.md", content_type="text/markdown", raw_text="alpha owner text", size_bytes=16, owner_id="user-a")
    for index in range(3):
        repo.save_document(filename=f"b-{index}.md", content_type="text/markdown", raw_text="beta owner text", size_bytes=15, owner_id="user-b")

    assert [item["id"] for item in repo.list_runs(limit=1, owner_id="user-a")] == ["run-a"]
    assert [item["id"] for item in repo.list_documents(limit=1, owner_id="user-a")] == [document_a.id]
    assert all(chunk.document_id == document_a.id for chunk in repo.search_document_chunks("owner text", owner_id="user-a"))
    assert repo.get_run("run-a", owner_id="user-b") is None
    assert repo.get_document(document_a.id, owner_id="user-b") is None
    assert repo.delete_document(document_a.id, owner_id="user-b") is False

