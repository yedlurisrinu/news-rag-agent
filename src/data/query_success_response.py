from typing import Literal

from pydantic import BaseModel

class ArticleOut(BaseModel):
    title: str
    link: str
    source: str
    published_at: str

class QuerySuccessResponse(BaseModel):
    query: str
    categories: list[str]
    summary: str
    articles: list[ArticleOut]
    duration_seconds: float
    status: Literal["ok"] = "ok"
