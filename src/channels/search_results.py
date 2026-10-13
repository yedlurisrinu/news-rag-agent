from typing import TypedDict, Required
from channels.article_reference import ArticleReference

class SearchResult(TypedDict):
    """Output of Search node"""
    articles: Required[list[ArticleReference]]
    duration_seconds: Required[dict[str, int]]  # Time took
