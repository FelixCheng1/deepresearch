"""轻量文本切块工具。"""

from __future__ import annotations

import re


def chunk_text(text: str, *, max_chars: int = 1200, overlap: int = 120) -> list[str]:
    """按段落优先切分文本，必要时按字符长度兜底。"""

    normalized = _normalize_text(text)
    if not normalized:
        return []
    if max_chars <= 0:
        raise ValueError("max_chars 必须大于 0")
    if overlap < 0:
        raise ValueError("overlap 不能为负数")

    chunks: list[str] = []
    current = ""
    for paragraph in _split_paragraphs(normalized, max_chars=max_chars):
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = paragraph

    if current:
        chunks.append(current)

    if not overlap or len(chunks) <= 1:
        return chunks

    overlapped: list[str] = [chunks[0]]
    for previous, chunk in zip(chunks, chunks[1:], strict=False):
        prefix = previous[-overlap:].strip()
        overlapped.append(f"{prefix}\n\n{chunk}".strip() if prefix else chunk)
    return overlapped


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_paragraphs(text: str, *, max_chars: int) -> list[str]:
    paragraphs: list[str] = []
    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= max_chars:
            paragraphs.append(paragraph)
            continue
        paragraphs.extend(_split_long_text(paragraph, max_chars=max_chars))
    return paragraphs


def _split_long_text(text: str, *, max_chars: int) -> list[str]:
    return [
        text[index : index + max_chars].strip()
        for index in range(0, len(text), max_chars)
        if text[index : index + max_chars].strip()
    ]
