from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langchain_core.language_models import BaseChatModel
from channels.news_state import NewsState
from channels.summary_result import SummaryResult
from data.query_failed_response import QueryFailedResponse
from data.query_success_response import QuerySuccessResponse
from nodes.classification import ClassifyIntent #, classify
from nodes.search import Search #search
from nodes.summary import Summary #summarize
from data.news_input import NewsInput
from channels.summary_ok import SummaryOk
from data.seed_data import SeedData
from fastapi import status
from utils.fetch_article import fetch_article_by_id
from channels.summary_ok import SummaryOk
from data.query_success_response import ArticleOut
from langgraph.checkpoint.postgres import PostgresSaver
from elasticsearch.client import Elasticsearch
from langgraph.graph.state import CompiledStateGraph
import logging

logger = logging.getLogger(__file__)
from typing import Literal

# Gate is not needed for this phase
# def gate(state: NewsState) -> dict:
#     return {}

def reply_off_topic(state: NewsState) -> SummaryResult:
    """
    User is not allowed to send query that is off the allowed topics, this is the response agents will give
    Guard Rail #1
    """
    return {"summary": SeedData._OFF_TOPIC_REPLY}

def reply_no_results(state: NewsState) -> SummaryResult:
    """
    User requested query criteria did not yield any news articles to summarize
    Guard Rail #2
    """
    return {"summary": SeedData._NO_NEWS_FOUND_REPLY}

def route_after_classify(state: NewsState,) -> list[NewsState] | Literal["reply_off_topic"]:
    """Router to route to guard rail#1 node or search node - making sure non news related queries are not honored"""
    return "search" if state["is_news_query"] else "reply_off_topic"

def route_after_search(state: NewsState) -> Literal["found", "empty"]:
    """Router to route to guard rail#2 node or summary node - making sure empty news from ES does not trigger LLM call"""
    return "found" if state["articles"] else "empty"


def cfg(tid: str, rl: int) -> RunnableConfig:
    return {"configurable": {"thread_id": tid, "recursion_limit": rl}}

def build(saver: PostgresSaver, llm : BaseChatModel, es: Elasticsearch):
    """
    Building state graph workflow with nodes classify, search, summary, off topic (Guard #1), no result (Guard#2)
    """
    g = StateGraph(NewsState, input_schema=NewsInput, output_schema=SummaryOk)
    for name, fn in [
        ("classify", ClassifyIntent(llm, es)),
        ("search", Search(llm, es)),
        ("summarize", Summary(llm, es)),
        ("reply_off_topic", reply_off_topic),
        ("reply_no_results", reply_no_results),
    ]:
        g.add_node(name, fn)

    g.add_edge(START, "classify")
    g.add_conditional_edges(
        "classify", route_after_classify, ["search", "reply_off_topic"]
    )
    g.add_conditional_edges(
        "search",
        route_after_search,
        {"found": "summarize", "empty": "reply_no_results"},
    )
    for terminal in ("summarize", "reply_off_topic", "reply_no_results"):
        g.add_edge(terminal, END)
    return g.compile(checkpointer=saver)

def run_graph(user_input: NewsInput, graph: CompiledStateGraph) -> QuerySuccessResponse | QueryFailedResponse:
    try:
        out: SummaryOk = graph.invoke(user_input, cfg(hash(user_input['query']), 10))
        logging.info(f"Total Time Taken = {out['duration_seconds']}")
        response = QuerySuccessResponse(
           query=out["query"],
           categories=out["categories"],
           summary=out["summary"],
           articles=[ArticleOut(**fetch_article_by_id(a)) for a in out["articles"]],
           duration_seconds=sum(out["duration_seconds"].values()),
        )
    except Exception as e:
        logger.exception(f" Exception while agents are fetching news summary: {e}")
        response = QueryFailedResponse(
            query=user_input["query"],
            error=str(e) or type(e).__name__,
            error_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return response


if __name__ == "__main__":
    # Move the config to /query route api level
    # where we build the config, not when calling invoke
    # this is only for local call
    from adapters.postgres import open_saver
    with open_saver() as saver:
        out1 = build(saver).invoke({"query": "GPU"}, {"recursion_limit": 10})
        out2 = build(saver).invoke({"query": "Not News"}, {"recursion_limit": 10})
        out3 = build(saver).invoke({"query": "Obscure"}, {"recursion_limit": 10})
        print(out1)
        print(out2)
        print(out3)
    # print(out3['dummy'])
