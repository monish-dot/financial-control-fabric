"""SQLite database connection management."""

from pathlib import Path
from typing import Final

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.database.models import Base

DEFAULT_DATABASE_PATH: Final = Path("data/financial_control.db")


class Database:
    """Own the SQLAlchemy engine and session factory for one SQLite database."""

    def __init__(self, database_url: str | Path = DEFAULT_DATABASE_PATH) -> None:
        if isinstance(database_url, Path):
            database_path = database_url.expanduser().resolve()
            database_path.parent.mkdir(parents=True, exist_ok=True)
            database_url = f"sqlite:///{database_path}"

        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine: Engine = create_engine(database_url, connect_args=connect_args)
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
        )

    def initialize(self) -> None:
        """Create the event-store schema if it does not exist."""

        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        """Return a new database session."""

        return self.session_factory()

    def dispose(self) -> None:
        """Release connections held by the engine."""

        self.engine.dispose()