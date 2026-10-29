"""Database connection helper. Each process connects with its own role (least privilege)."""
import psycopg

from .config import get_settings


def connect(url: str | None = None, **kwargs) -> psycopg.Connection:
    """Open a psycopg connection. Caller owns the connection and must close it."""
    return psycopg.connect(url or get_settings().database_url, **kwargs)
