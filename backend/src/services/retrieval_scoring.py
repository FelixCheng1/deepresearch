"""Deterministic lexical and hybrid scoring for document chunks."""

from __future__ import annotations

import re

from models import ResearchDocumentChunk
from services.embeddings import cosine_similarity


def rank_chunks(
    query: str,
    chunks: list[ResearchDocumentChunk],
    *,
    limit: int,
    min_score: float = 0.0,
    query_embedding: list[float] | None = None,
) -> list[ResearchDocumentChunk]:
    """Rank chunks with BM25-style lexical signals and optional vectors."""

    query_profile = _build_query_profile(query)
    safe_limit = max(1, min(limit, 20))
    if not chunks:
        return []
    if not query_profile["terms"] and not query_profile["phrases"] and not query_embedding:
        return chunks[:safe_limit]

    avg_len = max(1.0, sum(_chunk_length(chunk) for chunk in chunks) / max(1, len(chunks)))
    bm25_scores = {
        chunk.id: _score_chunk(chunk, query_profile, avg_len)
        for chunk in chunks
    }
    max_bm25 = max((score for score, _ in bm25_scores.values()), default=0.0)
    scored: list[tuple[float, ResearchDocumentChunk]] = []
    for chunk in chunks:
        bm25_score, matched_terms = bm25_scores[chunk.id]
        vector_score = cosine_similarity(query_embedding, chunk.embedding) if query_embedding else 0.0
        if vector_score <= 0 and bm25_score < min_score:
            continue
        if vector_score <= 0 and bm25_score <= 0:
            continue

        bm25_norm = bm25_score / max_bm25 if max_bm25 > 0 else 0.0
        hybrid_score = (0.55 * vector_score + 0.45 * bm25_norm) if query_embedding else bm25_score
        display_score = hybrid_score * 100 if query_embedding else hybrid_score
        metadata = dict(chunk.metadata)
        metadata.update(
            {
                "score": round(display_score, 4),
                "hybrid_score": round(display_score, 4),
                "bm25_score": round(bm25_score, 4),
                "vector_score": round(vector_score * 100, 4),
                "matched_terms": matched_terms,
                "snippet": _best_snippet(chunk.text, query_profile),
            }
        )
        scored.append(
            (
                hybrid_score,
                ResearchDocumentChunk(
                    id=chunk.id,
                    document_id=chunk.document_id,
                    document_title=chunk.document_title,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text,
                    metadata=metadata,
                    embedding=chunk.embedding,
                    embedding_model=chunk.embedding_model,
                    embedded_at=chunk.embedded_at,
                ),
            )
        )

    scored.sort(key=lambda item: (-item[0], item[1].document_title, item[1].chunk_index))
    return [chunk for _, chunk in scored[:safe_limit]]


def tokenize(query: str) -> list[str]:
    """Expose query tokenization for evaluation and regression tests."""

    return _build_query_profile(query)["terms"]


def _build_query_profile(query: str) -> dict[str, list[str]]:
    normalized = _normalize_for_search(query)
    words = re.findall(r"[a-z0-9]+", normalized)
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
    cjk_bigrams = ["".join(cjk_chars[index : index + 2]) for index in range(max(0, len(cjk_chars) - 1))]
    terms = _dedupe([term for term in words + cjk_bigrams if len(term) > 1])
    phrases = _dedupe([part for part in re.split(r"\s+", normalized) if len(part) >= 4])
    if len(cjk_chars) >= 3:
        phrases.append("".join(cjk_chars))
    return {"terms": terms, "phrases": _dedupe(phrases)}


def _score_chunk(
    chunk: ResearchDocumentChunk,
    query_profile: dict[str, list[str]],
    avg_len: float,
) -> tuple[float, list[str]]:
    title = _normalize_for_search(chunk.document_title)
    body = _normalize_for_search(chunk.text)
    title_tokens = _tokenize_text(title)
    body_tokens = _tokenize_text(body)
    body_len = max(1, len(body_tokens))
    k1 = 1.4
    b = 0.72
    score = 0.0
    matched: list[str] = []
    for term in query_profile["terms"]:
        tf = body_tokens.count(term)
        title_tf = title_tokens.count(term)
        substring_hit = 1 if term in body and tf == 0 else 0
        frequency = tf + substring_hit + title_tf * 2.4
        if frequency <= 0:
            continue
        bm25 = (frequency * (k1 + 1)) / (frequency + k1 * (1 - b + b * body_len / avg_len))
        score += bm25
        if title_tf:
            score += 1.2
        matched.append(term)
    for phrase in query_profile["phrases"]:
        if phrase and phrase in f"{title}\n{body}":
            score += 2.5 if phrase in title else 1.6
            matched.append(phrase)
    if query_profile["terms"]:
        coverage = len(set(matched) & set(query_profile["terms"])) / len(query_profile["terms"])
        score += coverage * 2.0
    if body_len > avg_len * 1.8:
        score *= 0.92
    return score, _dedupe(matched)[:8]


def _tokenize_text(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text)
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", text)
    cjk_bigrams = ["".join(cjk_chars[index : index + 2]) for index in range(max(0, len(cjk_chars) - 1))]
    return words + cjk_bigrams


def _normalize_for_search(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _chunk_length(chunk: ResearchDocumentChunk) -> int:
    return max(1, len(_tokenize_text(_normalize_for_search(chunk.text))))


def _best_snippet(
    text: str,
    query_profile: dict[str, list[str]],
    *,
    max_chars: int = 220,
) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    haystack = _normalize_for_search(compact)
    positions = [
        haystack.find(term)
        for term in query_profile["terms"] + query_profile["phrases"]
        if term and haystack.find(term) >= 0
    ]
    start = max(0, min(positions) - 60) if positions else 0
    snippet = compact[start : start + max_chars].strip()
    if start > 0:
        snippet = f"...{snippet}"
    if start + max_chars < len(compact):
        snippet = f"{snippet}..."
    return snippet


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
