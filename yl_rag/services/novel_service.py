from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

TIME_WORDS = ["清晨", "上午", "中午", "下午", "傍晚", "夜里", "凌晨"]


@dataclass
class NovelState:
    chapter_no: int
    timeline: list[str]


class NovelService:
    def extract_outline(self, text: str) -> dict:
        paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
        summary = "；".join(paragraphs[:4])[:400]
        people = self._extract_people(text)
        keywords = self._extract_keywords(text)
        return {
            "summary": summary,
            "characters": people,
            "keywords": keywords,
            "timeline": self._extract_timeline(text),
        }

    def generate_chapter(self, prompt: str, outline: dict, chapter_no: int) -> dict:
        chars = outline.get("characters") or ["主角"]
        tline = outline.get("timeline") or [TIME_WORDS[(chapter_no - 1) % len(TIME_WORDS)]]
        current_time = tline[(chapter_no - 1) % len(tline)]
        lead = chars[0]
        support = chars[1] if len(chars) > 1 else "同伴"
        chapter_title = f"第{chapter_no}章·{current_time}的选择"
        content = (
            f"{current_time}，{lead}在{prompt[:20]}这件事上迟迟下不了决心。"
            f"{support}带来一条线索，让局势出现转机。"
            f"两人先核对旧账，再确认彼此立场，避免误会扩大。"
            "冲突并未立刻解决，但目标已经统一：先保住人，再保住真相。"
            "章节结尾留下一个小悬念：他们在门后听见了第三个人的脚步声。"
        )
        return {"chapter_title": chapter_title, "chapter_content": content, "timeline": current_time}

    def rewrite_with_outline(self, source_text: str, outline: dict, chapter_no: int) -> dict:
        seed = source_text[:120]
        prompt = f"基于原文线索：{seed}"
        return self.generate_chapter(prompt, outline, chapter_no)

    def _extract_people(self, text: str) -> list[str]:
        names = re.findall(r"[\u4e00-\u9fa5]{2,3}", text)
        c = Counter(names)
        return [k for k, _ in c.most_common(6)] or ["主角"]

    def _extract_keywords(self, text: str) -> list[str]:
        words = re.findall(r"[\u4e00-\u9fa5]{2,4}", text)
        counter = Counter(words)
        stop = {"我们", "他们", "这个", "一个", "没有", "自己", "时候"}
        return [w for w, _ in counter.most_common(12) if w not in stop][:8]

    def _extract_timeline(self, text: str) -> list[str]:
        found = [t for t in TIME_WORDS if t in text]
        return found or ["清晨", "傍晚", "夜里"]


novel_service = NovelService()
