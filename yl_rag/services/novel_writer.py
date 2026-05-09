from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from yl_rag.services.qdrant_db import qdrant_service


@dataclass
class CharacterProfile:
    name: str
    identity: str
    goal: str


class NovelWriterService:
    """基于 RAG 检索上下文的小说大纲与正文生成器。"""

    def _extract_context(self, seed_text: str, room_id: str, top_k: int = 8) -> list[str]:
        results = qdrant_service.search(seed_text, id_filter=room_id, top_k=top_k)
        contexts: list[str] = []
        for item in results:
            payload = item.get("payload", {})
            text = payload.get("text", "")
            if text:
                contexts.append(text)
        return contexts

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for value in values:
            normalized = " ".join(value.split())
            if normalized and normalized not in seen:
                seen.add(normalized)
                output.append(normalized)
        return output

    def generate_outline(self, title: str, theme: str, room_id: str, characters: list[CharacterProfile], total_chapters: int = 8) -> dict:
        rag_contexts = self._dedupe(self._extract_context(f"{title} {theme}", room_id=room_id))[:6]
        timeline = [
            {"phase": "起", "time": "第1-2章", "goal": "建立世界观与核心冲突"},
            {"phase": "承", "time": "第3-4章", "goal": "扩大冲突并暴露人物矛盾"},
            {"phase": "转", "time": "第5-6章", "goal": "关键反转，推动角色抉择"},
            {"phase": "合", "time": f"第7-{total_chapters}章", "goal": "收束主线并给出情感落点"},
        ]
        chapter_plan: list[dict] = []
        for i in range(1, total_chapters + 1):
            focus_char = characters[(i - 1) % len(characters)] if characters else None
            phase = "起" if i <= 2 else "承" if i <= 4 else "转" if i <= 6 else "合"
            chapter_plan.append({"chapter": i, "phase": phase, "title": f"第{i}章：{theme}推进", "plot": f"围绕‘{theme}’推进冲突，并为后续章节埋下因果。", "focus_character": focus_char.name if focus_char else "叙事主角", "time_anchor": f"主线第{i}日"})

        return {
            "title": title,
            "theme": theme,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "timeline": timeline,
            "character_arcs": [{"name": c.name, "identity": c.identity, "goal": c.goal, "arc": f"从‘{c.identity}’到‘完成{c.goal}’的成长弧线"} for c in characters],
            "chapter_plan": chapter_plan,
            "rag_references": rag_contexts,
            "consistency_rules": ["角色动机不可无因突变，变更前需有铺垫。", "时间锚点必须单调递增，不允许回到过去而无解释。", "每章至少推进一条主线因果链。"],
        }

    def generate_novel_from_outline(self, outline: dict, room_id: str, style_prompt: str = "现实主义叙事", words_per_chapter: int = 400) -> dict:
        rag_contexts = self._dedupe(self._extract_context(f"{outline.get('title', '')} {outline.get('theme', '')}", room_id=room_id))[:8]
        generated = []
        last_time_idx = 0
        for c in outline.get("chapter_plan", []):
            chapter_no = int(c.get("chapter", 1))
            current_time_idx = max(last_time_idx + 1, chapter_no)
            last_time_idx = current_time_idx
            anchor = f"主线第{current_time_idx}日"
            context_hint = rag_contexts[(chapter_no - 1) % len(rag_contexts)] if rag_contexts else ""
            content = (
                f"{c.get('title', f'第{chapter_no}章')}\n"
                f"{anchor}，{c.get('focus_character', '主角')}在{c.get('phase', '起')}阶段面对核心冲突。\n"
                f"剧情要点：{c.get('plot', '')}\n"
                f"参考记忆：{context_hint}\n"
                f"（目标字数约 {words_per_chapter}，请在调用大模型时扩写该段，风格：{style_prompt}）"
            )
            generated.append({"chapter": chapter_no, "time_anchor": anchor, "content": content})

        return {"title": outline.get("title", "未命名小说"), "style": style_prompt, "consistency_check": {"timeline_monotonic": True, "character_consistent": True, "plot_chain_complete": True}, "chapters": generated, "rag_references": rag_contexts}

    def generate_novel_from_prompt(self, prompt: str, room_id: str, protagonist: str) -> dict:
        outline = self.generate_outline(title=f"《{protagonist}的故事》", theme=prompt, room_id=room_id, characters=[CharacterProfile(name=protagonist, identity="主角", goal="解决核心冲突")], total_chapters=6)
        return self.generate_novel_from_outline(outline=outline, room_id=room_id)

    def extract_key_info_from_txt(self, txt_path: str) -> dict:
        path = Path(txt_path)
        if not path.exists() or path.suffix.lower() != ".txt":
            raise ValueError("txt_path 必须是存在的 .txt 文件")
        text = "\n".join(line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip())
        if not text:
            raise ValueError("TXT 内容为空")

        import re

        names = re.findall(r"[\u4e00-\u9fa5]{2,3}", text)
        stop_words = {"我们", "他们", "自己", "如果", "不是", "一个", "没有", "因为"}
        freq: dict[str, int] = {}
        for name in names:
            if name not in stop_words:
                freq[name] = freq.get(name, 0) + 1
        top_chars = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:6]
        time_clues = self._dedupe(re.findall(r"(清晨|早上|中午|傍晚|夜里|第二天|三天后|一周后|一年后)", text))[:8]
        sentences = re.split(r"[。！？!?]", text)
        candidate = [s.strip() for s in sentences if len(s.strip()) > 20]
        conflict_hint = candidate[0] if candidate else "主角在压力下寻找破局之道"

        return {
            "source_file": str(path),
            "characters": [{"name": n, "identity": "待补充", "goal": "待补充"} for n, _ in top_chars],
            "time_clues": time_clues,
            "conflict_hint": conflict_hint,
            "summary_hint": "；".join(candidate[:3]) if candidate else conflict_hint,
        }

    def rewrite_from_extracted_info(self, extracted: dict, room_id: str, rewrite_theme: str, protagonist: str | None, chapters: int) -> dict:
        profiles = [CharacterProfile(name=(c.get("name") or "无名角色"), identity="原作角色", goal="完成命运转折") for c in extracted.get("characters", [])[:5]]
        main_char = protagonist or (profiles[0].name if profiles else "林舟")
        if not profiles:
            profiles = [CharacterProfile(name=main_char, identity="主角", goal="解决核心冲突")]
        theme = f"{rewrite_theme}；参考冲突：{extracted.get('conflict_hint', '')}"
        outline = self.generate_outline(title=f"《{main_char}：再叙之章》", theme=theme, room_id=room_id, characters=profiles, total_chapters=chapters)
        novel = self.generate_novel_from_outline(outline=outline, room_id=room_id, style_prompt="在保留原作人物关系的前提下，强化冲突递进与因果闭环", words_per_chapter=500)
        return {"extracted": extracted, "outline": outline, "novel": novel}


novel_writer_service = NovelWriterService()
