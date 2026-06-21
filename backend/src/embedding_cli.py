"""Document embedding and maintenance commands."""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

from config import Configuration
from services.document_worker import process_one_document_job
from services.embeddings import EmbeddingService
from services.repository import PostgresResearchRepository


def _repo(config: Configuration) -> PostgresResearchRepository:
    if not config.database_url:
        raise SystemExit("DATABASE_URL is required for document maintenance")
    service = EmbeddingService(config)
    return PostgresResearchRepository(database_url=config.database_url, embedding_service=service)


def probe_embedding(config: Configuration, text: str) -> int:
    vector = EmbeddingService(config).embed_query(text)
    print(f"embedding probe ok: model={config.embedding_model} dimension={len(vector)}")
    return len(vector)


def backfill_embeddings(config: Configuration, limit: int) -> int:
    repo = _repo(config)
    count = repo.backfill_document_embeddings(limit=limit)
    print(f"embedding backfill ok: updated={count} model={repo.embedding_service.model if repo.embedding_service else 'none'}")
    return count


def retry_failed_documents(config: Configuration, limit: int) -> int:
    repo = _repo(config)
    count = 0
    for document in repo.list_documents(limit=limit):
        if document.get("status") == "failed" and repo.retry_failed_document(document["id"]):
            count += 1
    while process_one_document_job(repo):
        pass
    print(f"document retry ok: queued={count}")
    return count


def rebuild_document(config: Configuration, document_id: str) -> bool:
    repo = _repo(config)
    ok = repo.rebuild_document(document_id)
    if not ok:
        raise SystemExit(f"document rebuild failed: {document_id}")
    print(f"document rebuild ok: document_id={document_id}")
    return ok


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Probe embeddings and maintain document indexes.")
    parser.add_argument("--probe", action="store_true", help="send one embedding request")
    parser.add_argument("--backfill", action="store_true", help="backfill missing/outdated chunk embeddings")
    parser.add_argument("--retry-failed-documents", action="store_true", help="retry failed document parsing jobs")
    parser.add_argument("--rebuild-document", action="store_true", help="rebuild one document from stored raw_text")
    parser.add_argument("--document-id", default="", help="document id for --rebuild-document")
    parser.add_argument("--text", default="embedding probe", help="probe text")
    parser.add_argument("--limit", type=int, default=100, help="maximum rows/documents to process")
    args = parser.parse_args()

    config = Configuration.from_env()
    if args.probe:
        probe_embedding(config, args.text)
    if args.retry_failed_documents:
        retry_failed_documents(config, args.limit)
    if args.rebuild_document:
        if not args.document_id:
            raise SystemExit("--document-id is required with --rebuild-document")
        rebuild_document(config, args.document_id)
    if args.backfill or not (args.probe or args.retry_failed_documents or args.rebuild_document):
        backfill_embeddings(config, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
