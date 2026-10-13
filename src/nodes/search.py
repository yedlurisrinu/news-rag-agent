from channels.search_results import SearchResult
from channels.news_state import NewsState
from langchain_core.language_models import BaseChatModel
from elasticsearch.client import Elasticsearch

class Search:
    def __init__(self, llm: BaseChatModel, es: Elasticsearch):
            self.llm = llm
            self.es = es
    
    def __call__(self, state: NewsState) -> SearchResult:
        # Search es with query for the results
            # capture response time
            if "FINANCE" not in state["categories"]:
                return {"articles": [], "duration_seconds": {"SEARCH": 2}}
            if "GPU" in state["query"]:
                return {
                    "articles": [
                        {"article_id": "124", "score": 5.2},
                        {"article_id": "345", "score": 4.3},
                    ],
                    "duration_seconds": {"SEARCH": 15},
                }
            else:
                return {"articles": [], "duration_seconds": {"SEARCH": 20}}    

