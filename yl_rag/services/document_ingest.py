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


def _norm_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def compute_sha256(text: str) -> str:
    return hashlib.sha256(_norm_text(text).encode("utf-8")).hexdigest()


def read_document(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return file_path.read_text(encoding="utf-8", errors="ignore")
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


def split_text_chunks(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []

    if chunk_overlap >= chunk_size:
        chunk_overlap = max(0, chunk_size // 5)

    chunks: list[str] = []
    start = 0
    text_len = len(normalized)
    step = max(1, chunk_size - chunk_overlap)

    while start < text_len:
        end = min(text_len, start + chunk_size)
        window = normalized[start:end]
        if end < text_len:
            split_pos = max(window.rfind("\n"), window.rfind("。"), window.rfind("."))
            if split_pos > chunk_size // 3:
                end = start + split_pos + 1
                window = normalized[start:end]

        chunk = window.strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break
        start = max(start + step, end - chunk_overlap)

    return chunks
