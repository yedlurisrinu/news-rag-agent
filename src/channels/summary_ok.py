from typing import TypedDict, Required

from channels.article_reference import ArticleReference

class SummaryOk(TypedDict):
    query: Required[str]
    is_news_query: Required[bool]
    fetch_latest: Required[bool]
    categories: Required[list[str]]
    articles: Required[list[ArticleReference]]
    summary: Required[str]
    duration_seconds: Required[dict[str, int]]
