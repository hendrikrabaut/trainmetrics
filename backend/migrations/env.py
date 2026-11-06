from alembic import context

from app import models  # noqa: F401  (registers all tables on Base.metadata)
from app.database import Base, engine


with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        render_as_batch=True,
        # SQLite reports TEXT and REAL where the models say String and Float.
        compare_type=False,
    )

    with context.begin_transaction():
        context.run_migrations()
