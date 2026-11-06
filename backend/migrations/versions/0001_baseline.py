"""Baseline: the schema as it existed before migrations were introduced.

A database that already has these tables must be stamped instead of upgraded:
    uv run alembic stamp 0001

Revision ID: 0001
Revises:
"""
from alembic import op


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


STATEMENTS = [
    """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE workouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        duration INTEGER,
        notes TEXT,
        type TEXT NOT NULL CHECK (type IN ('STRENGTH', 'ENDURANCE')),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE exercises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT,
        notes TEXT
    )
    """,
    """
    CREATE TABLE workout_exercises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workout_id INTEGER NOT NULL,
        exercise_id INTEGER NOT NULL,
        exercise_order INTEGER NOT NULL,
        FOREIGN KEY (workout_id) REFERENCES workouts(id) ON DELETE CASCADE,
        FOREIGN KEY (exercise_id) REFERENCES exercises(id)
    )
    """,
    """
    CREATE TABLE exercise_sets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workout_exercise_id INTEGER NOT NULL,
        set_number INTEGER NOT NULL,
        weight REAL,
        reps INTEGER,
        notes TEXT,
        FOREIGN KEY (workout_exercise_id)
            REFERENCES workout_exercises(id)
            ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE endurance_activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workout_id INTEGER NOT NULL,
        activity_type TEXT NOT NULL
            CHECK (activity_type IN ('RUNNING', 'CYCLING', 'SWIMMING', 'OTHER')),
        distance REAL,
        duration INTEGER,
        average_speed REAL,
        average_heart_rate INTEGER,
        max_heart_rate INTEGER,
        elevation_gain REAL,
        calories INTEGER,
        FOREIGN KEY (workout_id) REFERENCES workouts(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE body_measurements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        weight REAL,
        body_fat REAL,
        waist REAL,
        chest REAL,
        notes TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE equipment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        category TEXT,
        brand TEXT,
        model TEXT,
        purchase_date TEXT,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        notes TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE workout_equipment (
        workout_id INTEGER NOT NULL,
        equipment_id INTEGER NOT NULL,
        PRIMARY KEY (workout_id, equipment_id),
        FOREIGN KEY (workout_id) REFERENCES workouts(id) ON DELETE CASCADE,
        FOREIGN KEY (equipment_id) REFERENCES equipment(id) ON DELETE CASCADE
    )
    """,
]

TABLES = [
    "workout_equipment",
    "equipment",
    "body_measurements",
    "endurance_activities",
    "exercise_sets",
    "workout_exercises",
    "exercises",
    "workouts",
    "users",
]


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    for table in TABLES:
        op.drop_table(table)
