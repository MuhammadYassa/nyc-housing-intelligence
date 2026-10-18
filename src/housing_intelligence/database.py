"""Connection representations derived from the same validated settings."""

import psycopg
from psycopg.conninfo import make_conninfo
from sqlalchemy import URL

from .config import Settings


def connection_parameters(settings: Settings) -> dict:
    return {
        "host": settings.database_host,
        "port": settings.database_port,
        "dbname": settings.database_name,
        "user": settings.database_user,
        "password": settings.database_password.get_secret_value(),
    }


def sqlalchemy_url(settings: Settings) -> URL:
    params = connection_parameters(settings)
    return URL.create(
        "postgresql+psycopg",
        username=params["user"],
        password=params["password"],
        host=params["host"],
        port=params["port"],
        database=params["dbname"],
    )


def gdal_connection(settings: Settings) -> str:
    params = connection_parameters(settings)
    del params["password"]
    return "PG:" + make_conninfo(**params)


def connect(settings: Settings) -> psycopg.Connection:
    # Autocommit makes run progress durable; the job opens an explicit atomic
    # transaction for validation/merge/completion. The connection owns the lock.
    return psycopg.connect(
        **connection_parameters(settings),
        autocommit=True,
        connect_timeout=10,
        options=f"-c statement_timeout={settings.database_statement_timeout_seconds * 1000}",
    )
