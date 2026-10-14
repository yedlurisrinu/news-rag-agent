"""Summary node — mget full article bodies and produce a grounded, cited LLM summary."""
from typing import Any

from elastic_transport import ObjectApiResponse
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from channels.article_hit import ArticleHit
from channels.summary_result import SummaryResult
from channels.news_state import NewsState
from langchain_core.language_models import BaseChatModel
from elasticsearch import Elasticsearch
import time
import logging
from config.application_config import get_config

logger = logging.getLogger(__file__)

_SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an expert news analyst. You will receive a user query and a
collection of news article snippets retrieved from a search engine.

Your task:
- Write a clear, factual summary of 3–5 paragraphs that directly answers the query.
- Lead with the most important finding.
- When referencing a specific fact, cite the article title in brackets, e.g. [Article Title].
- Remain objective and neutral in tone.

Strict grounding rules — you MUST follow these without exception:
- Use ONLY information explicitly stated in the retrieved articles below.
- Do NOT use your training knowledge, general world knowledge, or any information
  not present in the provided context.
- Do NOT speculate, infer, or fill in gaps beyond what the articles state.
- If the provided articles do not contain enough information to answer the query,
  say so explicitly: state what was found and what remains unanswered.""",
        ),
        ("human","""USER QUERY: {query} RETRIEVED ARTICLES: {context}
Write the summary:""",
        ),
    ]
)

class Summary:
    """Graph node: fetch article content by id and generate a cited, grounded summary."""

    def __init__(self, llm: BaseChatModel, es: Elasticsearch):
            """Store the shared chat model and Elasticsearch client."""
            self.llm = llm
            self.es = es

    def __call__(self, state: NewsState) -> SummaryResult:
        """mget article bodies, build context, invoke the summarization chain; returns summary + hits + timing."""
        logger.debug(f'summary intent incoming state : {state}')
        duration_seconds: dict[str, float] = {}
        # Get actual content
        MGET_START = time.time()
        response = self.es.mget(index=get_config("ES_INDEX"), ids=[article['article_id'] for article in state['article_refs']])   
        duration_seconds.setdefault("MGET_CAL", time.time() - MGET_START)
        #build context 
        SUMMARY_CALL = time.time()
        context: list[str] = []
        article_hits : list[ArticleHit] = []
        context, article_hits = Summary._build_context(response)
        # call model with news articles
        chain = _SUMMARY_PROMPT | self.llm | StrOutputParser()
        # LLM call for summarization
        summary : str = chain.invoke({"query": state['query'], "context": context})
        # capture response time
        duration_seconds.setdefault("SUMMARY_LLM_CALL", time.time() - SUMMARY_CALL)
        return {"summary": summary, "article_hits":article_hits, "duration_seconds": duration_seconds}

    @staticmethod
    def _build_context(response: ObjectApiResponse[Any]) -> tuple[list[str] , list[ArticleHit]]:
        """Turn an ES mget response into LLM context blocks and ArticleHit metadata (content truncated to 1000 chars)."""
        docs = response.get('docs', [])
        if not docs:
            return ["No article found for summary"], []
        # TODO temp for testing
        blocks : list[str] = []
        article_hits : list[ArticleHit] = []
        for i, doc in enumerate(docs):
             source = doc.get('_source',{})
             if not source:
                  continue
             pub_at = source.get('published_at')[:10] if source.get('published_at') is not None else "date unknown"
             article_hits.append({"title": source.get('title'), "source": source.get('source'), "published_at": pub_at, "link": source.get('link')})
             
             blocks.append(f'Article {i}: \n'
                           f'title: {source.get('title')}\n'
                           f'source:{source.get('source')}\n'
                           f'published at: {pub_at}\n'
                           f'content: {source.get('content', "")[:1000]}')

        return blocks, article_hits
        
              