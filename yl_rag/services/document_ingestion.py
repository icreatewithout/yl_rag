from __future__ import annotations

import platform
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".doc", ".docx"}


@dataclass
class ParsedDocument:
    file_name: str
    text: str


def _load_optional_module(module_name: str):
    import importlib

    return importlib.import_module(module_name)


def _extract_text_from_txt(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8", errors="ignore")


def _extract_text_from_pdf(file_path: Path) -> str:
    pypdf = _load_optional_module("pypdf")
    reader = pypdf.PdfReader(str(file_path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _extract_text_from_docx(file_path: Path) -> str:
    docx = _load_optional_module("docx")
    document = docx.Document(str(file_path))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def _extract_text_from_doc(file_path: Path) -> str:
    """
    .doc 老格式优先用 textract 读取。
    Windows 上 textract 常见依赖链包含 fcntl（仅 Unix 可用），
    因此给出明确错误，避免调用时出现不友好的 ImportError。
    """
    if platform.system().lower() == "windows":
        raise RuntimeError(
            "Windows 环境暂不支持 .doc 解析（textract 依赖 fcntl）。"
            "建议先将 .doc 转换为 .docx 或 .txt 后上传。"
        )

    textract = _load_optional_module("textract")
    raw = textract.process(str(file_path))
    return raw.decode("utf-8", errors="ignore")


def parse_document(file_path: Path) -> ParsedDocument:
    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file extension: {ext}")

    if ext == ".txt":
        text = _extract_text_from_txt(file_path)
    elif ext == ".pdf":
        text = _extract_text_from_pdf(file_path)
    elif ext == ".docx":
        text = _extract_text_from_docx(file_path)
    else:
        text = _extract_text_from_doc(file_path)

    if not text.strip():
        raise ValueError(f"Document {file_path.name} is empty after parsing")

    return ParsedDocument(file_name=file_path.name, text=text)


def split_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    """将长文档分块，便于写入向量库并提升召回效果。"""
    normalized = " ".join(text.split())
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    text_len = len(normalized)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunks.append(normalized[start:end])
        if end >= text_len:
            break
        start = max(0, end - overlap)
    return chunks


def save_upload_file(content: bytes, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as out:
        out.write(content)
