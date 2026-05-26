from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from yl_rag.core.models import (
    FolderUploadInput,
    MemoryInput,
    SearchQuery,
    SearchResult,
)
from yl_rag.services.document_ingest import iter_supported_files, read_document
from yl_rag.services.qdrant_db import qdrant_service

router = APIRouter()


@router.post("/memory/add", tags=["Memory"])
def add_memory(data: MemoryInput):
    try:
        inserted = qdrant_service.add_memory(
            data.text,
            data.id,
            data.tags,
            data.role,
            data.source_name,
        )
        if not inserted:
            return {"status": "skip", "message": "Duplicate content by sha256"}
        return {"status": "success", "message": f"Memory stored in {data.id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/memory/upload/file", tags=["Memory"])
async def upload_file(id: str, role: str = "user", file: UploadFile = File(...)):
    try:
        suffix = Path(file.filename or "").suffix.lower()
        temp_path = Path("/tmp") / (file.filename or "uploaded.txt")
        temp_path.write_bytes(await file.read())
        text = read_document(temp_path)
        inserted = qdrant_service.add_memory(text, id, [suffix], role, file.filename)
        return {"status": "success" if inserted else "skip", "file": file.filename}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/memory/upload/folder", tags=["Memory"])
def upload_folder(data: FolderUploadInput):
    folder = Path(data.folder_path)
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=400, detail="Folder does not exist")

    uploaded = 0
    skipped = 0
    failed_files: list[str] = []
    for file_path in iter_supported_files(folder):
        try:
            text = read_document(file_path)
            inserted = qdrant_service.add_memory(
                text,
                data.id,
                [file_path.suffix.lower()],
                data.role,
                file_path.name,
            )
            if inserted:
                uploaded += 1
            else:
                skipped += 1
        except Exception:
            failed_files.append(str(file_path))

    return {"uploaded": uploaded, "skipped": skipped, "failed_files": failed_files}


@router.post("/memory/search", response_model=list[SearchResult], tags=["Retrieval"])
def search(query: SearchQuery):
    try:
        return qdrant_service.search(query.text, query.id_filter, query.top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
