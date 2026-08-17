from __future__ import annotations

import time
from collections.abc import Callable

from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


def create_database_engine(database_url: str) -> Engine:
    options: dict[str, object] = {"pool_pre_ping": True}
    if not database_url.startswith("sqlite"):
        options.update(pool_size=10, max_overflow=20)
    return create_engine(database_url, **options)


def create_session_factory(engine: Engine) -> Callable[[], Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def initialize_database(
    engine: Engine,
    base: type[DeclarativeBase],
    attempts: int = 30,
    delay_seconds: float = 2.0,
) -> None:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            base.metadata.create_all(engine)
            return
        except OperationalError as exc:
            last_error = exc
            time.sleep(delay_seconds)
    raise RuntimeError("Database did not become ready") from last_error
