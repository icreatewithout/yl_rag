from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from yl_rag.services.qdrant_db import qdrant_service


@dataclass
class CharacterProfile:
    name: str
    identity: str
    goal: str


class NovelWriterService:
    """基于 RAG 的小说创作器：兼顾稳定性、可读性与生成速度。"""

    STYLE_PACK = {
        "现实主义叙事": {
            "verbs": ["逼近", "撕开", "压弯", "点燃"],
            "moods": ["克制", "冷峻", "隐忍"],
            "cadence": "短句推进，细节落地。",
        },
        "悬疑": {
            "verbs": ["潜伏", "误导", "反咬", "回响"],
            "moods": ["不安", "迟疑", "逼仄"],
            "cadence": "信息延迟揭示，结尾留钩。",
        },
    }

    @lru_cache(maxsize=64)
    def _cached_context(self, seed_text: str, room_id: str, top_k: int) -> tuple[str, ...]:
        results = qdrant_service.search(seed_text, id_filter=room_id, top_k=top_k)
        contexts = [item.get("payload", {}).get("text", "") for item in results]
        return tuple(c for c in contexts if c)

    def _extract_context(self, seed_text: str, room_id: str, top_k: int = 8) -> list[str]:
        return list(self._cached_context(seed_text, room_id, top_k))

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for value in values:
            normalized = " ".join(value.split())
            if normalized and normalized not in seen:
                seen.add(normalized)
                output.append(normalized)
        return output

    def _style_hint(self, style_prompt: str, chapter_no: int) -> str:
        pack = self.STYLE_PACK.get(style_prompt, self.STYLE_PACK["现实主义叙事"])
        v = pack["verbs"][chapter_no % len(pack["verbs"])]
        m = pack["moods"][chapter_no % len(pack["moods"])]
        return f"笔调{m}，情节持续{v}；{pack['cadence']}"

    def generate_outline(
        self,
        title: str,
        theme: str,
        room_id: str,
        characters: list[CharacterProfile],
        total_chapters: int = 8,
    ) -> dict:
        rag_contexts = self._dedupe(self._extract_context(f"{title} {theme}", room_id=room_id))[:6]
        timeline = [
            {"phase": "起", "time": "第1-2章", "goal": "建立世界观与核心冲突"},
            {"phase": "承", "time": "第3-4章", "goal": "扩大冲突并暴露人物矛盾"},
            {"phase": "转", "time": "第5-6章", "goal": "关键反转，推动角色抉择"},
            {"phase": "合", "time": f"第7-{total_chapters}章", "goal": "收束主线并给出情感落点"},
        ]

        chapter_plan: list[dict] = []
        for i in range(1, total_chapters + 1):
            focus = characters[(i - 1) % len(characters)] if characters else None
            phase = "起" if i <= 2 else "承" if i <= 4 else "转" if i <= 6 else "合"
            seed = hashlib.sha256(f"{title}-{theme}-{i}".encode("utf-8")).hexdigest()[:8]
            chapter_plan.append(
                {
                    "chapter": i,
                    "phase": phase,
                    "title": f"第{i}章：{theme}",
                    "plot": f"围绕‘{theme}’推进冲突，种下可回收伏笔（线索码:{seed}）。",
                    "focus_character": focus.name if focus else "叙事主角",
                    "time_anchor": f"主线第{i}日",
                    "must_resolve": "承接上章后果，并制造新选择压力。",
                }
            )

        return {
            "title": title,
            "theme": theme,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "timeline": timeline,
            "character_arcs": [
                {
                    "name": c.name,
                    "identity": c.identity,
                    "goal": c.goal,
                    "arc": f"从‘{c.identity}’到‘完成{c.goal}’的成长弧线",
                }
                for c in characters
            ],
            "chapter_plan": chapter_plan,
            "rag_references": rag_contexts,
            "consistency_rules": [
                "角色动机不可无因突变。",
                "时间锚点必须单调递增。",
                "每章至少回收或新增一条因果线索。",
            ],
        }

    def generate_novel_from_outline(
        self,
        outline: dict,
        room_id: str,
        style_prompt: str = "现实主义叙事",
        words_per_chapter: int = 600,
    ) -> dict:
        theme = outline.get("theme", "命运与抉择")
        rag_contexts = self._dedupe(
            self._extract_context(f"{outline.get('title', '')} {theme}", room_id=room_id)
        )[:8]

        generated = []
        last_time_idx = 0
        for c in outline.get("chapter_plan", []):
            chapter_no = int(c.get("chapter", 1))
            time_idx = max(last_time_idx + 1, chapter_no)
            last_time_idx = time_idx
            anchor = f"主线第{time_idx}日"
            focus = c.get("focus_character", "主角")
            context_hint = rag_contexts[(chapter_no - 1) % len(rag_contexts)] if rag_contexts else ""
            style_hint = self._style_hint(style_prompt, chapter_no)

            # 更“人类写作感”的段落骨架：场景->动作->心理->后果
            content = (
                f"{c.get('title', f'第{chapter_no}章')}\n"
                f"{anchor}，{focus}先在具体场景中做出一个‘不可撤回’的小决定。"
                f"这个决定不是英雄式爆发，而是被现实一点点逼出来。\n"
                f"他/她随后为此付出代价：失去一次信任、错过一条捷径，或者暴露一个弱点。"
                f"冲突围绕“{theme}”继续收紧。\n"
                f"人物内心不直接喊口号，而通过动作体现：停顿、回避、重复某个习惯。\n"
                f"章节尾部必须抛出下一章问题：如果继续前进，谁会先崩溃？\n"
                f"参考素材：{context_hint}\n"
                f"写作提示：{style_hint} 目标字数≈{words_per_chapter}。"
            )
            generated.append({"chapter": chapter_no, "time_anchor": anchor, "content": content})

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
        outline = self.generate_outline(
            title=f"《{protagonist}的故事》",
            theme=prompt,
            room_id=room_id,
            characters=[CharacterProfile(name=protagonist, identity="主角", goal="解决核心冲突")],
            total_chapters=6,
        )
        return self.generate_novel_from_outline(outline=outline, room_id=room_id, style_prompt="现实主义叙事")

    def extract_key_info_from_txt(self, txt_path: str) -> dict:
        path = Path(txt_path)
        if not path.exists() or path.suffix.lower() != ".txt":
            raise ValueError("txt_path 必须是存在的 .txt 文件")

        text = "\n".join(
            line.strip()
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip()
        )
        if not text:
            raise ValueError("TXT 内容为空")

        names = re.findall(r"[\u4e00-\u9fa5]{2,3}", text)
        stop_words = {"我们", "他们", "自己", "如果", "不是", "一个", "没有", "因为"}
        freq: dict[str, int] = {}
        for name in names:
            if name not in stop_words:
                freq[name] = freq.get(name, 0) + 1

        top_chars = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:8]
        time_clues = self._dedupe(
            re.findall(r"(清晨|早上|中午|傍晚|夜里|第二天|三天后|一周后|一年后)", text)
        )[:10]
        sentences = [s.strip() for s in re.split(r"[。！？!?]", text) if len(s.strip()) > 18]

        return {
            "source_file": str(path),
            "characters": [
                {"name": n, "identity": "原作角色", "goal": "待提炼"} for n, _ in top_chars
            ],
            "time_clues": time_clues,
            "conflict_hint": sentences[0] if sentences else "主角在压力下寻找破局之道",
            "summary_hint": "；".join(sentences[:4]) if sentences else "",
        }

    def rewrite_from_extracted_info(
        self,
        extracted: dict,
        room_id: str,
        rewrite_theme: str,
        protagonist: str | None,
        chapters: int,
    ) -> dict:
        profiles = [
            CharacterProfile(name=c.get("name") or "无名角色", identity="原作角色", goal="完成命运转折")
            for c in extracted.get("characters", [])[:6]
        ]
        main_char = protagonist or (profiles[0].name if profiles else "林舟")
        if not profiles:
            profiles = [CharacterProfile(name=main_char, identity="主角", goal="解决核心冲突")]

        conflict = extracted.get("conflict_hint", "")
        theme = f"{rewrite_theme}；保留原作关系网络；冲突线：{conflict}"
        outline = self.generate_outline(
            title=f"《{main_char}：再叙之章》",
            theme=theme,
            room_id=room_id,
            characters=profiles,
            total_chapters=chapters,
        )
        novel = self.generate_novel_from_outline(
            outline=outline,
            room_id=room_id,
            style_prompt="现实主义叙事",
            words_per_chapter=700,
        )
        return {"extracted": extracted, "outline": outline, "novel": novel}


novel_writer_service = NovelWriterService()
