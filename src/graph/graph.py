from typing import TypedDict, NotRequired, Annotated, Required
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

# from agents.news_category_search_agent import run_category_search_agent
from typing import Literal

_OFF_TOPIC_REPLY = (
    "I'm a news search assistant and can only help with news-related queries. "
    "Please ask me about topics such as technology, politics, sports, business, "
    "science, health, climate, or world events."
)

_NO_NEWS_FOUND_REPLY = (
    "I searched for news articles matching your query but couldn't find any relevant results. "
    "Try broadening your search terms or asking about a different topic."
)

class NewsInput(TypedDict):
    query: str

class NewsOutput(TypedDict):
    summary: str

class SearchTask(TypedDict):
    query: str
    category: str

class ArticleRef(TypedDict):
    article_id: Required[str]
    score: Required[float]

def merge_article_hits(
    current: list[ArticleRef], update: list[ArticleRef]
) -> list[ArticleRef]:
    # dedupe by article_id;
    # when both sides have the same ID, keep the higher score;
    # return a list sorted so the result is order-independent, with a deterministic tie-break;
    # pure: don't mutate either input. ArticleRef is a dataclass, so it's unhashable by default; key by ID, not by object.
    # get dictionaries
    # current = [{"article_id": "id_1", "score": 0.7}, {"article_id": "id_2", "score": 0.9}]
    # update  = [{"article_id": "id_1", "score": 0.8}, {"article_id": "id_3", "score": 0.5}, {"article_id": "id_0", "score": 0.8}]
    merged_by_id: dict[str, ArticleRef] = {}

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

class NewsState(TypedDict):
    query: str
    is_news_query: NotRequired[bool]
    articles: Annotated[list[ArticleRef], merge_article_hits]
    categories: NotRequired[list[str]]
    summary: NotRequired[str]

class CategoryOutput(TypedDict):
    categories: list[str]
    is_news_query: bool

class SearchOutput(TypedDict):
    articles: Required[list[ArticleRef]]

class SummaryOutput(TypedDict):
    summary: Required[str]

def classify(state: NewsState) -> CategoryOutput:
    # call LLM and verify if the query is news
    # TODO  category_output   = run_category_search_agent(state["query"])
    # TODO  category_output.is_news_query
    return {
        "is_news_query": state["query"] != "Not News",
        "categories": ["TECH", "FINANCE"],
    }

def fan_out(state: NewsState) -> list[Send]:
    return [
        Send("search", {"query": state["query"], "category": c})
        for c in state["categories"]
    ]

# LangGraph's node protocol names it that, and ty matches on the name
# that is the reson we are keeping name
def search(state: SearchTask) -> SearchOutput:
    # TODO  search_result = run_news_search_agent(state["query"], state['categories'])
    # search_result = [{"article_id":"124", "score": 5.2}, {"article_id":"345", "score": 4.3}]; # some articles
    print("************", state["category"])
    if state["category"] == "FINANCE":
        return {"articles": []}
    if state["query"] == "GPU":
        return {
            "articles": [
                {"article_id": "124", "score": 5.2},
                {"article_id": "345", "score": 4.3},
            ]
        }
    else:
        return {"articles": []}

def summarize(state: NewsState) -> SummaryOutput:
    # LLM call for summrization
    # TODO summary = run_summary_agent(state["query"], state["articles"])
    summary = "All Good"
    return {"summary": summary}

def gate(state: NewsState) -> dict:
    return {}

def reply_off_topic(state: NewsState) -> SummaryOutput:
    return {"summary": _OFF_TOPIC_REPLY}

def reply_no_results(state: NewsState) -> SummaryOutput:
    return {"summary": _NO_NEWS_FOUND_REPLY}

# Making sure non news related queries are not honored guard rail 1
def route_after_classify(state: NewsState) -> list[Send] | Literal["reply_off_topic"]:
    return fan_out(state) if state["is_news_query"] else "reply_off_topic"

# Making sure empty news from ES does not trigger LLM call guard rail 2
def route_after_search(state: NewsState) -> Literal["found", "empty"]:
    return "found" if state["articles"] else "empty"

def build():
    g = StateGraph(NewsState, input_schema=NewsInput, output_schema=NewsOutput)  # ty: ignore[invalid-argument-type]
    for name, fn in [
        ("classify", classify),
        ("search", search),
        ("summarize", summarize),
        ("reply_off_topic", reply_off_topic),
        ("reply_no_results", reply_no_results),
        ("fan_out", fan_out),
    ]:
        g.add_node(name, fn)
    g.add_node("gate", gate, defer=True)
    g.add_edge(START, "classify")
    # g.add_conditional_edges("classify", route_after_classify,
    #                         {"news": "fan_out", "off_topic": "reply_off_topic"})
    g.add_conditional_edges(
        "classify", route_after_classify, ["search", "reply_off_topic"]
    )
    g.add_edge("search", "gate")
    g.add_conditional_edges(
        "gate", route_after_search, {"found": "summarize", "empty": "reply_no_results"}
    )

    for terminal in ("summarize", "reply_off_topic", "reply_no_results"):
        g.add_edge(terminal, END)
    return g.compile()

if __name__ == "__main__":
    # Move the config to /query route api level
    # where we build the config, not when calling invoke
    # this is only for local call
    out1 = build().invoke({"query": "GPU"}, {"recursion_limit": 10})
    out2 = build().invoke({"query": "Not News"}, {"recursion_limit": 10})
    out3 = build().invoke({"query": "Obscure"}, {"recursion_limit": 10})
    print(out1["summary"])
    print(out2["summary"])
    print(out3["summary"])
    # print(out3['dummy'])
