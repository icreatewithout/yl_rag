
from pydantic import BaseModel, Field


class MemoryInput(BaseModel):
    # 限制长度防止大模型 Token 截断 (约 500 Token)
    text: str = Field(..., max_length=600, description="记忆文本内容")
    id: str = Field(default="id", description="记忆所属用户")
    role: str | None = Field(default="user", description="记忆角色")
    tags: list[str] = Field(default_factory=list, description="关联实体标签")
    source_name: str | None = Field(default=None, description="来源文件名")


class SearchQuery(BaseModel):
    text: str = Field(..., max_length=200, description="查询内容")
    id_filter: str | None = Field(default=None, description="仅在此房间内搜索")
    top_k: int = Field(default=5, ge=1, le=20, description="返回结果数量")


class SearchResult(BaseModel):
    id: str
    payload: dict
    score: float
    created_at: float


class FolderUploadInput(BaseModel):
    folder_path: str = Field(..., description="本地文件夹路径")
    id: str = Field(default="id", description="记忆所属用户")
    role: str | None = Field(default="user", description="记忆角色")


class NovelExtractInput(BaseModel):
    text: str = Field(..., min_length=100, description="小说原文txt内容")


class NovelGenerateInput(BaseModel):
    prompt: str = Field(..., description="创作指令文案")
    outline: dict = Field(default_factory=dict, description="提取后的大纲信息")
    chapter_no: int = Field(default=1, ge=1, description="章节号")


class NovelRewriteInput(BaseModel):
    source_text: str = Field(..., description="需要二创的原文")
    outline: dict = Field(default_factory=dict, description="大纲信息")
    chapter_no: int = Field(default=1, ge=1, description="章节号")
