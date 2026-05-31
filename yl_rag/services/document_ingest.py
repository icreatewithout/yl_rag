from __future__ import annotations

import hashlib
import re
from pathlib import Path

try:
    from pypdf import PdfReader
except Exception:  # noqa: BLE001
    PdfReader = None

try:
    from docx import Document
except Exception:  # noqa: BLE001
    Document = None

SUPPORTED_SUFFIXES = {".txt", ".md", ".docx", ".pdf"}
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200
RECURSIVE_SEPARATORS = ["\n\n", "\n", "。", "！", "？", ".", "!", "?", "，", ",", " ", ""]


def _norm_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def compute_sha256(text: str) -> str:
    return hashlib.sha256(_norm_text(text).encode("utf-8")).hexdigest()


def _read_text_with_fallback(file_path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5"):
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return file_path.read_text(encoding="utf-8", errors="ignore")


def read_document(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return _read_text_with_fallback(file_path)
    if suffix == ".docx":
        if Document is None:
            raise RuntimeError("python-docx is not installed")
        doc = Document(str(file_path))
        return "\n".join(p.text for p in doc.paragraphs)
    if suffix == ".pdf":
        if PdfReader is None:
            raise RuntimeError("pypdf is not installed")
        reader = PdfReader(str(file_path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    raise ValueError(f"Unsupported file format: {suffix}")


def iter_supported_files(folder: Path) -> list[Path]:
    return [
        p
        for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
    ]


def _recursive_split(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []
    if len(cleaned) <= chunk_size:
        return [cleaned]

    sep = separators[0]
    if sep == "":
        return [cleaned[i : i + chunk_size] for i in range(0, len(cleaned), chunk_size)]

    parts = cleaned.split(sep)
    if len(parts) == 1:
        return _recursive_split(cleaned, chunk_size, separators[1:])

    chunks: list[str] = []
    current = ""
    for part in parts:
        candidate = f"{current}{sep}{part}" if current else part
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.extend(_recursive_split(current, chunk_size, separators[1:]))
        current = part

    if current:
        chunks.extend(_recursive_split(current, chunk_size, separators[1:]))

    return [c for c in chunks if c.strip()]


def _apply_overlap(chunks: list[str], chunk_overlap: int) -> list[str]:
    if not chunks or chunk_overlap <= 0:
        return chunks

    merged: list[str] = []
    for idx, chunk in enumerate(chunks):
        if idx == 0:
            merged.append(chunk)
            continue
        prefix = chunks[idx - 1][-chunk_overlap:]
        merged.append(f"{prefix}{chunk}")
    return merged


def split_text_chunks(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []

    safe_chunk_size = max(200, chunk_size)
    safe_overlap = min(max(0, chunk_overlap), safe_chunk_size // 3)

    base_chunks = _recursive_split(normalized, safe_chunk_size, RECURSIVE_SEPARATORS)
    return _apply_overlap(base_chunks, safe_overlap)
