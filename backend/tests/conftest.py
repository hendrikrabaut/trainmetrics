import os
import tempfile
from pathlib import Path

# Must be set before anything imports app.database, so tests never touch real data.
_directory = tempfile.TemporaryDirectory()
os.environ["TRAINMETRICS_DB"] = str(Path(_directory.name) / "test.db")

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import engine
from app.main import app


BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def schema():
    command.upgrade(Config(BACKEND / "alembic.ini"), "head")


@pytest.fixture(autouse=True)
def seeded_user(schema):
    with engine.begin() as connection:
        for table in (
            "workout_equipment",
            "equipment",
            "body_measurements",
            "endurance_activities",
            "exercise_sets",
            "workout_exercises",
            "exercises",
            "workouts",
            "users",
        ):
            connection.execute(text(f"DELETE FROM {table}"))

        connection.execute(
            text("INSERT INTO users (id, name, email) VALUES (1, 'Test', 'test@example.com')")
        )


@pytest.fixture
def client():
    return TestClient(app)
