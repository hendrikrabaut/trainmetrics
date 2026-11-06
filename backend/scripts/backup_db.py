"""Makes a consistent copy of the database and removes old local copies.

Usage: uv run python scripts/backup_db.py [backup-directory] [copies-to-keep]

SQLite's backup API is used because copying the file while the app writes to
it can produce a corrupt backup.
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import DATABASE_PATH  # noqa: E402


DEFAULT_DIRECTORY = Path(__file__).resolve().parents[2] / "data" / "backups"


def backup(directory: Path, keep: int) -> Path:
    directory.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = directory / f"trainmetrics-{stamp}.db"

    source = sqlite3.connect(f"file:{DATABASE_PATH}?mode=ro", uri=True)
    destination = sqlite3.connect(target)

    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()

    # Only timestamped copies made by this script are ever removed.
    copies = sorted(directory.glob("trainmetrics-[0-9]*-[0-9]*.db"))

    for old_copy in copies[:-keep]:
        old_copy.unlink()

    return target


if __name__ == "__main__":
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIRECTORY
    keep = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    print(backup(directory, keep))
