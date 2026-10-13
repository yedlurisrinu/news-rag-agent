from data.article_hit import ArticleHit
from dataclasses import asdict


def fetch_article_by_id(id: str) -> ArticleHit:
    # TODO fetching actual article from ES
    return asdict(
        ArticleHit(
            "123",
            "testing title",
            "Test Content",
            "BBC",
            "12/10/2026T12:00:000",
            "http://testing.com",
            2.2,
        )
    )
