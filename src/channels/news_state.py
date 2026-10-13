from typing import TypedDict, NotRequired, Annotated
from channels.article_reference import ArticleReference


def merge_article_hits(
    current: list[ArticleReference], update: list[ArticleReference]
) -> list[ArticleReference]:
    # dedupe by article_id;
    # when both sides have the same ID, keep the higher score;
    # return a list sorted so the result is order-independent, with a deterministic tie-break;
    # pure: don't mutate either input. ArticleRef is a dataclass, so it's unhashable by default; key by ID, not by object.
    # get dictionaries
    # current = [{"article_id": "id_1", "score": 0.7}, {"article_id": "id_2", "score": 0.9}]
    # update  = [{"article_id": "id_1", "score": 0.8}, {"article_id": "id_3", "score": 0.5}, {"article_id": "id_0", "score": 0.8}]
    merged_by_id: dict[str, ArticleReference] = {}

    for record in current:
        article_id = record["article_id"]
        merged_by_id[article_id] = {"article_id": article_id, "score": record["score"]}

    for update_record in update:
        article_id = update_record["article_id"]
        if (
            article_id not in merged_by_id
            or update_record["score"] > merged_by_id[article_id]["score"]
        ):
            merged_by_id[article_id] = {
                "article_id": article_id,
                "score": update_record["score"],
            }

    return sorted(
        merged_by_id.values(), key=lambda r: (-float(r["score"]), r["article_id"])
    )

def append(current: dict[str, int], additional: dict[str, int]):
    appended = current | additional
    return appended

class NewsState(TypedDict):
    query: str
    is_news_query: NotRequired[bool]
    fetch_latest: NotRequired[bool]
    categories: NotRequired[list[str]]
    articles: Annotated[list[ArticleReference], merge_article_hits]
    summary: NotRequired[str]
    duration_seconds: Annotated[NotRequired[dict[str, int]], append]
