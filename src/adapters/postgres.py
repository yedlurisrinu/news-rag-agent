import os
from psycopg import Connection
from psycopg.rows import dict_row

def connect_postgres() -> Connection:
    return Connection.connect(
            host=os.environ.get("PG_HOST","localhost"),
            port=int(os.environ.get("PG_PORT", "5432")),
            dbname=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            autocommit=True,
            prepare_threshold=0,
            row_factory=dict_row,)