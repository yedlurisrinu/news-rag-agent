from contextlib import asynccontextmanager

from fastapi import FastAPI
from adapters.postgres import connect_postgres
from adapters.elasticsearch import get_es_client
from graph.graph import build
from adapters.llm import get_chat_model
from langgraph.checkpoint.postgres import PostgresSaver

@asynccontextmanager
async def lifespan(app: FastAPI):
    with (connect_postgres() as pool,
            get_es_client() as es):
        app.state.graph = build(PostgresSaver(pool), get_chat_model(), es)
        yield