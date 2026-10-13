from typing import TypedDict, Required

class ArticleReference(TypedDict):
    article_id: Required[str]
    score: Required[float]
