import os

from alembic import context
from sqlalchemy import create_engine

from db.models import Base

target_metadata = Base.metadata
url = os.environ["VEILLE_DB_URL"]


def run_migrations_online() -> None:
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
