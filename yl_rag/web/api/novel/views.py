from fastapi import APIRouter, HTTPException

from yl_rag.core.models import (
    NovelChapterGenerateInput,
    NovelExtractRewriteInput,
    NovelFromOutlineInput,
    NovelFromPromptInput,
    OutlineGenerateInput,
)
from yl_rag.services.novel_writer import CharacterProfile, novel_writer_service

router = APIRouter(prefix="/novel")


@router.post("/outline", tags=["Novel"])
def generate_outline(data: OutlineGenerateInput):
    try:
        characters = [CharacterProfile(name=c.name, identity=c.identity, goal=c.goal) for c in data.characters]
        return novel_writer_service.generate_outline(
            title=data.title,
            theme=data.theme,
            room_id=data.room_id,
            characters=characters,
            total_chapters=data.total_chapters,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"大纲生成失败: {exc}") from exc


@router.post("/generate_from_outline", tags=["Novel"])
def generate_novel_from_outline(data: NovelFromOutlineInput):
    try:
        return novel_writer_service.generate_novel_from_outline(
            outline=data.outline,
            room_id=data.room_id,
            style_prompt=data.style_prompt,
            words_per_chapter=data.words_per_chapter,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"小说生成失败: {exc}") from exc


@router.post("/chapter", tags=["Novel"])
def generate_one_chapter(data: NovelChapterGenerateInput):
    """二次创作分章返回：每次只生成并返回一个章节。"""
    try:
        return novel_writer_service.generate_single_chapter(
            outline=data.outline,
            chapter_index=data.chapter_index,
            room_id=data.room_id,
            style_prompt=data.style_prompt,
            words_per_chapter=data.words_per_chapter,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"章节生成失败: {exc}") from exc


@router.post("/generate_from_prompt", tags=["Novel"])
def generate_novel_from_prompt(data: NovelFromPromptInput):
    try:
        return novel_writer_service.generate_novel_from_prompt(
            prompt=data.prompt,
            room_id=data.room_id,
            protagonist=data.protagonist,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"文案生成小说失败: {exc}") from exc


@router.post("/extract_rewrite_from_txt", tags=["Novel"])
def extract_and_rewrite_from_txt(data: NovelExtractRewriteInput):
    try:
        extracted = novel_writer_service.extract_key_info_from_txt(data.txt_path)
        return novel_writer_service.rewrite_from_extracted_info(
            extracted=extracted,
            room_id=data.room_id,
            rewrite_theme=data.rewrite_theme,
            protagonist=data.protagonist,
            chapters=data.chapters,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"提取并改写失败: {exc}") from exc
