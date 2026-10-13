from channels.summary_result import SummaryResult
from channels.news_state import NewsState
from langchain_core.language_models import BaseChatModel
from elasticsearch.client import Elasticsearch
class Summary:
    
    def __init__(self, llm: BaseChatModel, es: Elasticsearch):
            self.llm = llm
            self.es = es
    
    def __call__(self, state: NewsState) -> SummaryResult:
        # call model with news articles
        # capture the response
        # capture response time
        # LLM call for summarization
        # TODO summary = run_summary_agent(state["query"], state["articles"])
        summary = "All Good"
        return {"summary": summary, "duration_seconds": {"SUMMARY": 15}}
