"""Imports the data archive from account.polar.com into the database.

Usage: uv run python scripts/import_polar_export.py <folder> [user-id]

Running it twice is safe: what is already there is skipped.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import models  # noqa: E402,F401  (registers all tables)
from app.database import SessionLocal  # noqa: E402
from app.services.polar_export import import_export  # noqa: E402


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)

    user_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    with SessionLocal() as db:
        print(import_export(db, user_id, Path(sys.argv[1])))
