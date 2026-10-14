from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI
from adapters.postgres import connect_postgres
from adapters.elasticsearch import get_es_client
from graph.build_graph import build
from adapters.llm import get_chat_model
from langgraph.checkpoint.postgres import PostgresSaver

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[Any, Any]:
    """
    A context manager to maintain postgres saver connection , model connection, elasticsearch connection
    and inject into graph.
    """
    with (connect_postgres() as pool,
            get_es_client() as es):
        app.state.graph = build(PostgresSaver(pool), get_chat_model(), es)
        yield