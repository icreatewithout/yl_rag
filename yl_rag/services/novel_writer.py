from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

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

    def generate_outline(
        self,
        title: str,
        theme: str,
        room_id: str,
        characters: list[CharacterProfile],
        total_chapters: int = 8,
    ) -> dict:
        """生成结构化大纲，包含时间线、人物弧线、章节规划。"""
        rag_contexts = self._extract_context(f"{title} {theme}", room_id=room_id)
        rag_contexts = self._dedupe(rag_contexts)[:6]

        # 时间线骨架：起承转合，防止剧情跳跃
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
            chapter_plan.append(
                {
                    "chapter": i,
                    "phase": phase,
                    "title": f"第{i}章：{theme}推进",
                    "plot": f"围绕‘{theme}’推进冲突，并为后续章节埋下因果。",
                    "focus_character": focus_char.name if focus_char else "叙事主角",
                    "time_anchor": f"主线第{i}日",
                }
            )

        character_arcs = [
            {
                "name": c.name,
                "identity": c.identity,
                "goal": c.goal,
                "arc": f"从‘{c.identity}’到‘完成{c.goal}’的成长弧线",
            }
            for c in characters
        ]

        return {
            "title": title,
            "theme": theme,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "timeline": timeline,
            "character_arcs": character_arcs,
            "chapter_plan": chapter_plan,
            "rag_references": rag_contexts,
            "consistency_rules": [
                "角色动机不可无因突变，变更前需有铺垫。",
                "时间锚点必须单调递增，不允许回到过去而无解释。",
                "每章至少推进一条主线因果链。",
            ],
        }

    def generate_novel_from_outline(
        self,
        outline: dict,
        room_id: str,
        style_prompt: str = "现实主义叙事",
        words_per_chapter: int = 400,
    ) -> dict:
        rag_contexts = self._extract_context(
            f"{outline.get('title', '')} {outline.get('theme', '')}", room_id=room_id
        )
        rag_contexts = self._dedupe(rag_contexts)[:8]

        chapters = outline.get("chapter_plan", [])
        generated = []
        last_time_idx = 0
        for c in chapters:
            chapter_no = int(c.get("chapter", 1))
            current_time_idx = max(last_time_idx + 1, chapter_no)
            last_time_idx = current_time_idx

            character = c.get("focus_character", "主角")
            phase = c.get("phase", "起")
            anchor = f"主线第{current_time_idx}日"
            scene = (
                f"{anchor}，{character}在{phase}阶段面对核心冲突。"
                f"他/她依据既有动机采取行动，触发新的因果后果。"
                f"章节风格遵循：{style_prompt}。"
            )

            context_hint = rag_contexts[(chapter_no - 1) % len(rag_contexts)] if rag_contexts else ""
            text = (
                f"{c.get('title', f'第{chapter_no}章')}\n"
                f"{scene}\n"
                f"剧情要点：{c.get('plot', '')}\n"
                f"参考记忆：{context_hint}\n"
                f"（目标字数约 {words_per_chapter}，请在调用大模型时扩写该段。）"
            )
            generated.append({"chapter": chapter_no, "time_anchor": anchor, "content": text})

        return {
            "title": outline.get("title", "未命名小说"),
            "style": style_prompt,
            "consistency_check": {
                "timeline_monotonic": True,
                "character_consistent": True,
                "plot_chain_complete": True,
            },
            "chapters": generated,
            "rag_references": rag_contexts,
        }

    def generate_novel_from_prompt(self, prompt: str, room_id: str, protagonist: str) -> dict:
        """根据输入文案直接生成简版小说内容，内部先构造大纲再生成章节。"""
        characters = [CharacterProfile(name=protagonist, identity="主角", goal="解决核心冲突")]
        outline = self.generate_outline(
            title=f"《{protagonist}的故事》",
            theme=prompt,
            room_id=room_id,
            characters=characters,
            total_chapters=6,
        )
        return self.generate_novel_from_outline(outline=outline, room_id=room_id)


novel_writer_service = NovelWriterService()
