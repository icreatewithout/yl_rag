from fastapi import APIRouter, HTTPException

from yl_rag.core.models import NovelExtractInput, NovelGenerateInput, NovelRewriteInput
from yl_rag.services.novel_service import novel_service

router = APIRouter()


@router.post("/novel/extract", tags=["Novel"])
def extract_outline(data: NovelExtractInput):
    try:
        return novel_service.extract_outline(data.text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/novel/generate", tags=["Novel"])
def generate_chapter(data: NovelGenerateInput):
    try:
        return novel_service.generate_chapter(data.prompt, data.outline, data.chapter_no)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/novel/rewrite", tags=["Novel"])
def rewrite(data: NovelRewriteInput):
    try:
        return novel_service.rewrite_with_outline(data.source_text, data.outline, data.chapter_no)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
