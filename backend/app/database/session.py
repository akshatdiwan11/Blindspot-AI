from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


def _register_numpy_adapters() -> None:
    """Let psycopg2 store numpy scalars (the stats code returns them) as plain numbers."""
    try:
        import numpy as np
        from psycopg2.extensions import AsIs, register_adapter
    except ImportError:  # pragma: no cover - psycopg2 is optional for SQLite-only setups
        return
    for t in (np.float64, np.float32, np.int64, np.int32):
        register_adapter(t, lambda v: AsIs(repr(v.item())))
    register_adapter(np.bool_, lambda v: AsIs("TRUE" if bool(v) else "FALSE"))


_register_numpy_adapters()


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # enforce ON DELETE CASCADE in SQLite
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    return engine


engine = _make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def configure_engine(url: str) -> None:
    """Rebind the global engine (used by tests)."""
    global engine
    engine = _make_engine(url)
    SessionLocal.configure(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
