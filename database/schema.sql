-- Reference for the current schema. Changes are applied through the Alembic
-- migrations in backend/migrations; keep this file in step with them.

PRAGMA foreign_keys = ON;

-- ============================================
-- USERS
-- ============================================

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    max_heart_rate INTEGER,
    resting_heart_rate INTEGER,
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
    source_hash TEXT UNIQUE, -- imported file and session, NULL if entered by hand

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
    average_speed REAL,         -- m/s
    average_heart_rate INTEGER, -- bpm
    max_heart_rate INTEGER,     -- bpm
    elevation_gain REAL,        -- meters
    calories INTEGER,
    running_index INTEGER,      -- from Polar, NULL for other sources

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
    sport TEXT,
    is_default INTEGER NOT NULL DEFAULT 0,
    replace_after_km REAL,

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

-- ============================================
-- POLAR
-- ============================================

CREATE TABLE polar_accounts (
    user_id INTEGER PRIMARY KEY,
    polar_user_id TEXT,
    access_token TEXT NOT NULL,
    last_sync_at TEXT,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);


-- ============================================
-- TRAINING PLANS
-- ============================================

CREATE TABLE training_plans (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    goal TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    race_date TEXT,
    status TEXT NOT NULL, -- ACTIVE or ARCHIVED
    warning TEXT,
    weekdays TEXT,        -- comma separated, 0 is Monday
    first_long_run REAL,  -- meters

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);


CREATE TABLE plan_sessions (
    id INTEGER PRIMARY KEY,
    plan_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    week INTEGER NOT NULL,
    sport TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    distance REAL,    -- meters
    duration INTEGER, -- seconds
    phase TEXT,       -- BASE, BUILD, PEAK, TAPER or RACE

    FOREIGN KEY (plan_id) REFERENCES training_plans(id) ON DELETE CASCADE
);


-- ============================================
-- SLEEP AND RECOVERY
-- ============================================

CREATE TABLE sleep_nights (
    user_id INTEGER NOT NULL,
    night TEXT NOT NULL,
    sleep_start TEXT,
    sleep_end TEXT,
    asleep_seconds INTEGER,
    light_seconds INTEGER,
    deep_seconds INTEGER,
    rem_seconds INTEGER,
    interruption_seconds INTEGER,
    continuity REAL,
    sleep_score REAL,
    hrv_ms REAL,
    heart_rate REAL,      -- bpm
    breathing_rate REAL,  -- breaths per minute
    recharge_status INTEGER, -- Polar's verdict: 1 very poor to 6 very good
    ans_charge REAL,         -- Polar's -10 to +10

    PRIMARY KEY (user_id, night),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);


-- ============================================
-- ROUTES
-- ============================================

CREATE TABLE workout_routes (
    workout_id INTEGER PRIMARY KEY,
    points TEXT NOT NULL, -- JSON list of [latitude, longitude], simplified

    FOREIGN KEY (workout_id) REFERENCES workouts(id) ON DELETE CASCADE
);


-- ============================================
-- MEASUREMENTS, RACES AND SEGMENTS
-- ============================================

CREATE TABLE workout_streams (
    workout_id INTEGER PRIMARY KEY,
    interval_seconds INTEGER NOT NULL,
    data TEXT NOT NULL,         -- JSON, thinned series
    splits TEXT NOT NULL,       -- JSON
    zones TEXT NOT NULL,        -- JSON
    best_efforts TEXT NOT NULL, -- JSON

    FOREIGN KEY (workout_id) REFERENCES workouts(id) ON DELETE CASCADE
);

CREATE TABLE races (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    date TEXT NOT NULL,
    priority TEXT NOT NULL, -- A, B or C
    goal TEXT,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE segments (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    sport TEXT NOT NULL,
    points TEXT NOT NULL, -- JSON list of [latitude, longitude]
    length_meters REAL NOT NULL,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE segment_efforts (
    segment_id INTEGER NOT NULL,
    workout_id INTEGER NOT NULL,
    seconds INTEGER NOT NULL,

    PRIMARY KEY (segment_id, workout_id),
    FOREIGN KEY (segment_id) REFERENCES segments(id) ON DELETE CASCADE,
    FOREIGN KEY (workout_id) REFERENCES workouts(id) ON DELETE CASCADE
);
