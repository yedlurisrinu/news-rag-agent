"""
conftest.py — pytest fixtures shared across all test modules.

Provides:
  - A session-wide real application config load (nodes read query templates from it).
  - Factory fixtures for a fake chat model (FakeListChatModel) and a mock
    Elasticsearch client, so nodes/graph run with no external services.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture(scope="session", autouse=True)
def _load_app_config():
    """Load the real resources/application-config.yaml once for the whole test session.

    Nodes build their ES queries from get_config("CATEGORY_QUERY") /
    "SEARCH_QUERY_TEMPLATE" / "ES_INDEX", so the config dict must be populated.
    """
    from config.application_config import load_config

    load_config()


@pytest.fixture()
def make_llm():
    """Return a factory building a FakeListChatModel from canned responses.

    The fake model is a real Runnable, so ``prompt | llm | parser`` works; it
    cycles through ``responses`` in order (JSON for classify, prose for summary).
    """
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    def _make(responses: list[str]):
        return FakeListChatModel(responses=responses)

    return _make


@pytest.fixture()
def make_es():
    """Return a factory building a MagicMock Elasticsearch client.

    ``search_response`` feeds es.search(); ``mget_response`` feeds es.mget().
    """

    def _make(search_response: dict | None = None, mget_response: dict | None = None):
        es = MagicMock()
        es.search.return_value = search_response or {
            "hits": {"total": {"value": 0}, "hits": []}
        }
        es.mget.return_value = mget_response or {"docs": []}
        return es

    return _make


@pytest.fixture()
def es_hit():
    """A single ES search hit shaped like a real response document."""
    return {"_source": {"article_id": "a1"}, "_score": 1.23}


@pytest.fixture()
def es_doc():
    """A single ES mget document with full article content."""
    return {
        "_source": {
            "article_id": "a1",
            "title": "AI Revolutionises Healthcare",
            "source": "TechNews",
            "published_at": "2026-03-28T10:00:00Z",
            "link": "https://technews.example.com/ai-health",
            "content": "Artificial intelligence is transforming diagnosis. " * 60,
        }
    }
