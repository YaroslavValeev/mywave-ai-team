# alembic env.py
import os
import sys
from pathlib import Path

# Project root: app/storage/migrations -> parents[3]
_project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_project_root))

from alembic import context
from sqlalchemy import create_engine
from app.storage.models import Base
from app.storage.repositories import get_database_url  # noqa: E402

config = context.config
target_metadata = Base.metadata


def run_migrations_offline():
    url = get_database_url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    url = get_database_url()
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
