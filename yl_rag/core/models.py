
from pydantic import BaseModel, Field


class MemoryInput(BaseModel):
    # 限制长度防止大模型 Token 截断 (约 500 Token)
    text: str = Field(..., max_length=600, description="记忆文本内容")
    id: str = Field(default="id", description="记忆所属用户")
    role: str | None = Field(default="user", description="记忆角色")
    tags: list[str] = Field(default_factory=list, description="关联实体标签")


class SearchQuery(BaseModel):
    text: str = Field(..., max_length=200, description="查询内容")
    id_filter: str | None = Field(default=None, description="仅在此房间内搜索")
    top_k: int = Field(default=5, ge=1, le=20, description="返回结果数量")


class SearchResult(BaseModel):
    id: str
    payload: dict
    score: float
    created_at: float


class CharacterInput(BaseModel):
    name: str = Field(..., description="角色名")
    identity: str = Field(default="普通人", description="角色身份")
    goal: str = Field(default="完成成长", description="角色目标")


class OutlineGenerateInput(BaseModel):
    title: str = Field(..., description="小说标题")
    theme: str = Field(..., description="小说主题")
    room_id: str = Field(default="id", description="RAG 记忆空间")
    total_chapters: int = Field(default=8, ge=4, le=30, description="章节总数")
    characters: list[CharacterInput] = Field(default_factory=list, description="主要角色")


class NovelFromOutlineInput(BaseModel):
    outline: dict = Field(..., description="已生成大纲")
    room_id: str = Field(default="id", description="RAG 记忆空间")
    style_prompt: str = Field(default="现实主义叙事", description="文风提示")
    words_per_chapter: int = Field(default=400, ge=200, le=2000, description="每章字数")


class NovelFromPromptInput(BaseModel):
    prompt: str = Field(..., min_length=10, description="输入文案")
    room_id: str = Field(default="id", description="RAG 记忆空间")
    protagonist: str = Field(default="林舟", description="主角名")


class NovelExtractRewriteInput(BaseModel):
    txt_path: str = Field(..., description="服务端 txt 小说路径")
    room_id: str = Field(default="id", description="RAG 记忆空间")
    rewrite_theme: str = Field(default="宿命与选择", description="二次创作主题")
    protagonist: str | None = Field(default=None, description="指定主角，不填则自动提取")
    chapters: int = Field(default=8, ge=4, le=30, description="生成章节数")
