from dataclasses import dataclass
from pydantic import BaseModel

@dataclass
class ArticleHit(BaseModel):
    """A single retrieved news article."""

    article_id: str
    title: str
    content: str
    source: str
    published_at: str
    link: str
    score: float = 0.0
