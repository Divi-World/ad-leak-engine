"""SQLite persistence layer via SQLModel for Ad-Leak-Engine [SEED: 2399]."""
from __future__ import annotations

import os
from pathlib import Path

from sqlmodel import SQLModel, create_engine

DB_PATH = os.getenv("DB_PATH", "data/db/adleak.db")
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)


def init_db() -> None:
    from . import models  # noqa: F401  register tables with SQLModel.metadata
    SQLModel.metadata.create_all(engine)
