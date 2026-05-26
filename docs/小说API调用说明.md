# 小说创作 API 调用说明

小说创作接口已从 memory 模块独立到 `yl_rag/web/api/novel/views.py`。

## 接口列表

1. `POST /novel/outline`：提取/生成大纲。
2. `POST /novel/generate_from_outline`：按完整大纲生成全书草稿。
3. `POST /novel/chapter`：**每次只返回一个章节**（适合二次创作逐章调优）。
4. `POST /novel/generate_from_prompt`：输入文案直生。
5. `POST /novel/extract_rewrite_from_txt`：从 txt 提取关键信息后二创。

## 逐章生成推荐流程

1. 调 `/novel/outline` 获取 `chapter_plan`。
2. 从 `chapter_index=1` 开始调用 `/novel/chapter`。
3. 读取返回字段：
   - `chapter`：当前章节内容
   - `has_next`：是否还有下一章
   - `next_chapter_index`：下一章索引
4. 若 `has_next=true`，继续请求下一章，直至结束。

## /novel/chapter 请求示例

```json
{
  "outline": {"title": "长夜未央", "theme": "背叛与救赎", "chapter_plan": [{"chapter": 1, "title": "第1章", "phase": "起", "plot": "冲突建立", "focus_character": "林舟"}]},
  "chapter_index": 1,
  "room_id": "project_a",
  "style_prompt": "现实主义叙事",
  "words_per_chapter": 700
}
```

## 说明

- 逐章生成能显著提升二次创作可控性：可在每章返回后做人审、改写、补充设定。
- 建议在同一个 `room_id` 下先上传世界观/人物设定文档，以提高 RAG 召回质量。
