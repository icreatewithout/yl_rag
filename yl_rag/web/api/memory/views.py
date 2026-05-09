from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from yl_rag.core.models import MemoryInput, SearchQuery, SearchResult
from yl_rag.services.document_ingestion import parse_document, save_upload_file, split_text
from yl_rag.services.qdrant_db import qdrant_service

router = APIRouter()


@router.post("/memory/add", tags=["Memory"])
def add_memory(data: MemoryInput):
    try:
        qdrant_service.add_memory(data.text, data.id, data.tags, data.role)
        return {"status": "success", "message": f"Memory stored in {data.id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/search", response_model=list[SearchResult], tags=["Retrieval"])
def search(query: SearchQuery):
    try:
        return qdrant_service.search(query.text, query.id_filter, query.top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/upload/file", tags=["Memory"])
async def upload_single_document(
    file: UploadFile = File(...),
    user_id: str = Form("id"),
    role: str = Form("user"),
    tags: str = Form(""),
):
    """上传单个文档并写入 RAG 向量库。"""
    upload_dir = Path("./cache/uploads")
    file_name = file.filename or f"upload_{int(time.time())}.txt"
    destination = upload_dir / file_name

    try:
        payload = await file.read()
        save_upload_file(content=payload, destination=destination)
        parsed = parse_document(destination)
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

        chunk_count = 0
        for chunk in split_text(parsed.text):
            chunk_count += 1
            qdrant_service.add_memory(
                text=chunk,
                id=user_id,
                tags=tag_list + [parsed.file_name],
                role=role,
            )

        return {
            "status": "success",
            "file": parsed.file_name,
            "chunks": chunk_count,
            "message": "单文件已写入 RAG 数据库",
        }
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"缺少文档解析依赖: {exc.name}，请安装后重试",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"上传失败: {exc}") from exc


@router.post("/memory/upload/folder", tags=["Memory"])
def upload_folder_documents(
    folder_path: str = Form(...),
    user_id: str = Form("id"),
    role: str = Form("user"),
    tags: str = Form(""),
):
    """从服务器本地文件夹批量读取文档并写入 RAG 向量库。"""
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=400, detail="folder_path 不存在或不是目录")

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    supported = {".txt", ".pdf", ".doc", ".docx"}
    files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in supported]
    if not files:
        raise HTTPException(status_code=400, detail="目录下没有可解析的文档文件")

    success_files = 0
    total_chunks = 0
    failed: list[dict[str, str]] = []

    for file_path in files:
        try:
            parsed = parse_document(file_path)
            chunks = split_text(parsed.text)
            for chunk in chunks:
                qdrant_service.add_memory(
                    text=chunk,
                    id=user_id,
                    tags=tag_list + [parsed.file_name],
                    role=role,
                )
            success_files += 1
            total_chunks += len(chunks)
        except ModuleNotFoundError as exc:
            failed.append({"file": file_path.name, "error": f"缺少依赖: {exc.name}"})
        except Exception as exc:
            failed.append({"file": file_path.name, "error": str(exc)})

    return {
        "status": "success",
        "folder": str(folder),
        "files_total": len(files),
        "files_success": success_files,
        "chunks_total": total_chunks,
        "failed": failed,
        "message": "批量文档处理完成，内容已写入 RAG 数据库",
    }
