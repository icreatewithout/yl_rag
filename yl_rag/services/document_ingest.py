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
