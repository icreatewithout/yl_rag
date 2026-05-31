import hashlib
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from yl_rag.core.models import (
    FolderUploadInput,
    MemoryInput,
    SearchQuery,
    SearchResult,
)
from yl_rag.services.document_ingest import (
    compute_sha256,
    iter_supported_files,
    read_document,
    split_text_chunks,
)
from yl_rag.services.qdrant_db import qdrant_service

router = APIRouter()


def _ingest_chunked_text(
    text: str,
    owner_id: str,
    role: str,
    source_name: str,
    tags: list[str],
) -> dict:
    content_sha256 = compute_sha256(text)
    if qdrant_service.has_document_sha256(content_sha256):
        return {
            "status": "skip",
            "chunks": 0,
            "message": "Duplicate content by sha256",
        }

    chunks = split_text_chunks(text)
    if not chunks:
        return {"status": "skip", "chunks": 0, "message": "Empty text"}

    document_id = hashlib.md5(
        f"{owner_id}:{source_name}:{content_sha256}".encode(),
    ).hexdigest()
    inserted = 0
    chunk_total = len(chunks)
    for idx, chunk in enumerate(chunks):
        ok = qdrant_service.add_memory(
            chunk,
            owner_id,
            tags,
            role,
            source_name,
            document_id=document_id,
            chunk_index=idx,
            chunk_total=chunk_total,
            document_sha256=content_sha256,
        )
        if ok:
            inserted += 1

    return {"status": "success", "chunks": inserted, "document_id": document_id}


@router.post("/memory/add", tags=["Memory"])
def add_memory(data: MemoryInput):
    try:
        source_name = data.source_name or "memory_add"
        result = _ingest_chunked_text(
            data.text,
            data.id,
            data.role or "user",
            source_name,
            data.tags,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/memory/upload/file", tags=["Memory"])
async def upload_file(id: str, role: str = "user", file: UploadFile = File(...)):
    try:
        suffix = Path(file.filename or "").suffix.lower()
        temp_path = Path("/tmp") / (file.filename or "uploaded.txt")
        temp_path.write_bytes(await file.read())
        text = read_document(temp_path)
        result = _ingest_chunked_text(
            text,
            id,
            role,
            file.filename or "uploaded.txt",
            [suffix],
        )
        result["file"] = file.filename
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/memory/upload/folder", tags=["Memory"])
def upload_folder(data: FolderUploadInput):
    folder = Path(data.folder_path)
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=400, detail="Folder does not exist")

    uploaded = 0
    skipped = 0
    uploaded_chunks = 0
    failed_files: list[str] = []
    for file_path in iter_supported_files(folder):
        try:
            text = read_document(file_path)
            result = _ingest_chunked_text(
                text,
                data.id,
                data.role or "user",
                file_path.name,
                [file_path.suffix.lower()],
            )
            if result["status"] == "success":
                uploaded += 1
                uploaded_chunks += int(result["chunks"])
            else:
                skipped += 1
        except Exception:
            failed_files.append(str(file_path))

    return {
        "uploaded_files": uploaded,
        "uploaded_chunks": uploaded_chunks,
        "skipped_files": skipped,
        "failed_files": failed_files,
    }


@router.post("/memory/search", response_model=list[SearchResult], tags=["Retrieval"])
def search(query: SearchQuery):
    try:
        return qdrant_service.search(
            query.text,
            query.id_filter,
            query.top_k,
            query.context_window,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
