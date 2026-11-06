"""Imports the data archive from account.polar.com into the database.

Usage: uv run python scripts/import_polar_export.py <folder>

Running it twice is safe: what is already there is skipped.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import models  # noqa: E402,F401  (registers all tables)
from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.polar_export import import_export  # noqa: E402


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)

    with SessionLocal() as db:
        user_id = db.scalar(select(User.id).order_by(User.id))

        if user_id is None:
            sys.exit("Maak eerst je profiel aan in de app")

        print(import_export(db, user_id, Path(sys.argv[1])))
