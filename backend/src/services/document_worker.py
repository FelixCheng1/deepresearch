"""Tiny in-process worker for document jobs."""

from __future__ import annotations

import threading
from collections.abc import Callable

from loguru import logger

from config import Configuration
from services.document_parser import DocumentParseError, parse_document
from services.repository import ResearchRepository


def process_one_document_job(repository: ResearchRepository, config: Configuration | None = None) -> bool:
    job = repository.claim_next_document_job()
    if job is None:
        return False

    try:
        payload = job.get("payload")
        if not isinstance(payload, bytes):
            raise DocumentParseError("document payload is missing")
        raw_text, content_type = parse_document(
            job.get("filename") or "document",
            job.get("content_type") or "application/octet-stream",
            payload,
            config,
        )
        repository.complete_document_processing(
            job["document_id"],
            raw_text=raw_text,
            content_type=content_type,
        )
        repository.succeed_document_job(job["id"])
    except DocumentParseError as exc:
        message = str(exc)
        repository.fail_document_processing(job["document_id"], message)
        repository.fail_document_job(job["id"], message)
    except Exception:  # noqa: BLE001
        logger.exception("Document job failed")
        message = "document processing failed"
        repository.fail_document_processing(job["document_id"], message)
        repository.fail_document_job(job["id"], message)
    return True


def start_document_worker(
    *,
    config: Configuration,
    repository_factory: Callable[[Configuration], ResearchRepository],
    interval_seconds: float = 1.0,
) -> tuple[threading.Event, threading.Thread]:
    stop_event = threading.Event()

    def loop() -> None:
        repository = repository_factory(config)
        repository.reset_running_document_jobs()
        while not stop_event.is_set():
            did_work = process_one_document_job(repository, config)
            if not did_work:
                stop_event.wait(interval_seconds)

    thread = threading.Thread(target=loop, name="document-job-worker", daemon=True)
    thread.start()
    return stop_event, thread
