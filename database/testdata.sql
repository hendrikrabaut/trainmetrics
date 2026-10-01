-- ============================================
-- TEST DATA
-- ============================================

-- USERS
INSERT INTO users (name, email)
VALUES ('Hendrik', 'hendrik@example.com');


-- ============================================
-- EXERCISES
-- ============================================

INSERT INTO exercises (name, category)
VALUES
    ('Bench Press', 'Chest'),
    ('Cable Row', 'Back'),
    ('Lat Pulldown', 'Back'),
    ('Lateral Raise', 'Shoulders');


-- ============================================
-- EQUIPMENT
-- ============================================

INSERT INTO equipment (
    user_id,
    name,
    category,
    brand,
    model,
    purchase_date,
    status,
    notes
)
VALUES
    (
        1,
        'Cube Agree',
        'BIKE',
        'Cube',
        'Agree',
        '2024-06-15',
        'ACTIVE',
        'Race bike'
    ),
    (
        1,
        'Polar Ignite 2',
        'WEARABLE',
        'Polar',
        'Ignite 2',
        '2023-01-10',
        'ACTIVE',
        'Main sports watch'
    );


-- ============================================
-- STRENGTH WORKOUT
-- ============================================

INSERT INTO workouts (
    user_id,
    date,
    duration,
    notes,
    type
)
VALUES (
    1,
    '2026-10-01 14:00:00',
    3600,
    'Upper body session',
    'STRENGTH'
);


-- Workout exercises

INSERT INTO workout_exercises (
    workout_id,
    exercise_id,
    exercise_order
)
VALUES
    (1, 1, 1), -- Bench Press
    (1, 2, 2), -- Cable Row
    (1, 4, 3); -- Lateral Raise


-- Bench Press sets

INSERT INTO exercise_sets (
    workout_exercise_id,
    set_number,
    weight,
    reps,
    notes
)
VALUES
    (1, 1, 60, 10, NULL),
    (1, 2, 60, 8, NULL),
    (1, 3, 65, 6, 'Last set was difficult');


-- Cable Row sets

INSERT INTO exercise_sets (
    workout_exercise_id,
    set_number,
    weight,
    reps,
    notes
)
VALUES
    (2, 1, 55, 10, NULL),
    (2, 2, 55, 10, NULL),
    (2, 3, 60, 8, NULL);


-- Lateral Raise sets

INSERT INTO exercise_sets (
    workout_exercise_id,
    set_number,
    weight,
    reps,
    notes
)
VALUES
    (3, 1, 10, 12, NULL),
    (3, 2, 10, 10, NULL),
    (3, 3, 8, 12, NULL);


-- ============================================
-- RUN
-- ============================================

INSERT INTO workouts (
    user_id,
    date,
    duration,
    notes,
    type
)
VALUES (
    1,
    '2026-09-29 17:30:00',
    3448,
    'Easy run',
    'ENDURANCE'
);

INSERT INTO endurance_activities (
    workout_id,
    activity_type,
    distance,
    duration,
    average_speed,
    average_heart_rate,
    max_heart_rate,
    elevation_gain,
    calories
)
VALUES (
    2,
    'RUNNING',
    10610,
    3448,
    3.08,
    171,
    185,
    62,
    720
);


-- ============================================
-- CYCLING
-- ============================================

INSERT INTO workouts (
    user_id,
    date,
    duration,
    notes,
    type
)
VALUES (
    1,
    '2026-09-27 09:00:00',
    5963,
    'Group ride',
    'ENDURANCE'
);

INSERT INTO endurance_activities (
    workout_id,
    activity_type,
    distance,
    duration,
    average_speed,
    average_heart_rate,
    max_heart_rate,
    elevation_gain,
    calories
)
VALUES (
    3,
    'CYCLING',
    47320,
    5963,
    7.93,
    148,
    178,
    310,
    1050
);


-- Cube Agree + Polar Ignite 2 used during cycling

INSERT INTO workout_equipment (workout_id, equipment_id)
VALUES
    (3, 1),
    (3, 2);


-- ============================================
-- BODY MEASUREMENTS
-- ============================================

INSERT INTO body_measurements (
    user_id,
    date,
    weight,
    body_fat,
    waist,
    chest,
    notes
)
VALUES
    (1, '2026-09-28 08:00:00', 90.8, NULL, 90, NULL, 'Morning measurement'),
    (1, '2026-10-01 08:00:00', 90.4, NULL, 89.5, NULL, 'Morning measurement');