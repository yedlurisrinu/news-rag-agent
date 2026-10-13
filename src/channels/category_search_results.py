from typing import TypedDict, Required
from pydantic import Field

class CategorySearchResult(TypedDict):
    """Output of ClassifyIntent node."""

    categories: list[str] = Field(
        description=(
            "List of news category names extracted from the user query. "
            "Use lowercase, singular nouns e.g. 'technology', 'politics', 'sports'. "
            "Return an empty list when is_news_query is false."
        )
    )
    fetch_latest: Required[bool] = Field(
        description=(
            "True if the user explicitly asks for latest, recent, today's, "
            "or newest articles. False otherwise."
        )
    )
    is_news_query: Required[bool] = Field(
        description=(
            "True if the query is asking about news, current events, articles, "
            "or any real-world topic that could appear in a news feed. "
            "False if the query is a general knowledge question, a request for "
            "opinions, creative writing, coding help, math, personal advice, "
            "or anything clearly unrelated to news."
        )
    )
    duration_seconds: Required[dict[str, int]] = Field(
        description=("Time spent in this node ")
    )
