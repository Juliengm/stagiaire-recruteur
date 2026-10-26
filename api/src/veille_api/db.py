import os
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session


@lru_cache
def get_engine() -> Engine:
    return create_engine(os.environ["VEILLE_DB_URL"], pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
