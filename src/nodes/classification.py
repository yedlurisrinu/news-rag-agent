from channels.news_state import NewsState
from channels.category_search_results import CategorySearchResult
from langchain_core.language_models import BaseChatModel
from elasticsearch.client import Elasticsearch

""" Responsibility:
   1. Parse the user query to identify news categories of interest.
   2. Verify those categories exist in the news_articles index.
   3. Detect whether the user wants the *latest* articles (recency intent).
   4. Return a CategorySearchResult.
"""
""" Technology: LangGraph + OpenAI API calling + direct ES aggregation.
    Tracing: TODO open telemetry integration """
class ClassifyIntent:
    
    def __init__(self, llm: BaseChatModel, es: Elasticsearch):
        self.llm = llm
        self.es = es
    def __call__(self, state: NewsState) -> CategorySearchResult:
            # make intend call to model and get the response
    # check if query for latest news
    # make call to es for categories
    # capture response time
    # respond the details
        return {
            "is_news_query": state["query"] != "Not News",
            "fetch_latest": False,
            "categories": ["TECH", "FINANCE"],
            "duration_seconds": {"CLASSIFY": 10},
            }

