PRAGMA foreign_keys = ON;

-- ============================================
-- USERS
-- ============================================

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================
-- WORKOUTS
-- ============================================

CREATE TABLE workouts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    duration INTEGER, -- duration in seconds
    notes TEXT,
    type TEXT NOT NULL CHECK (type IN ('STRENGTH', 'ENDURANCE')),

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);


-- ============================================
-- STRENGTH
-- ============================================

CREATE TABLE exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT,
    notes TEXT
);


CREATE TABLE workout_exercises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id INTEGER NOT NULL,
    exercise_id INTEGER NOT NULL,
    exercise_order INTEGER NOT NULL,

    FOREIGN KEY (workout_id) REFERENCES workouts(id) ON DELETE CASCADE,
    FOREIGN KEY (exercise_id) REFERENCES exercises(id)
);


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
);


-- ============================================
-- ENDURANCE
-- ============================================

CREATE TABLE endurance_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id INTEGER NOT NULL,
    activity_type TEXT NOT NULL
        CHECK (activity_type IN ('RUNNING', 'CYCLING', 'SWIMMING', 'OTHER')),

    distance REAL,              -- meters
    duration INTEGER,           -- seconds
    average_speed REAL,         -- km/h
    average_heart_rate INTEGER, -- bpm
    max_heart_rate INTEGER,     -- bpm
    elevation_gain REAL,        -- meters
    calories INTEGER,

    FOREIGN KEY (workout_id) REFERENCES workouts(id) ON DELETE CASCADE
);


-- ============================================
-- BODY MEASUREMENTS
-- ============================================

CREATE TABLE body_measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,

    weight REAL,       -- kg
    body_fat REAL,    -- %
    waist REAL,       -- cm
    chest REAL,       -- cm

    notes TEXT,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);


-- ============================================
-- EQUIPMENT / PERSONAL GEAR
-- ============================================

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
);


-- ============================================
-- WORKOUT ↔ EQUIPMENT
-- ============================================

CREATE TABLE workout_equipment (
    workout_id INTEGER NOT NULL,
    equipment_id INTEGER NOT NULL,

    PRIMARY KEY (workout_id, equipment_id),

    FOREIGN KEY (workout_id)
        REFERENCES workouts(id)
        ON DELETE CASCADE,

    FOREIGN KEY (equipment_id)
        REFERENCES equipment(id)
        ON DELETE CASCADE
);