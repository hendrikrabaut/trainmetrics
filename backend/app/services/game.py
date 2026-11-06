"""XP, levels, quests and badges.

Everything is calculated from the training data on each request and nothing is
stored, so editing or deleting a workout can never leave the score out of step.
"""
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.body_measurement import BodyMeasurement
from app.models.training_plan import TrainingPlan
from app.services.analytics import estimated_one_rep_max, parse_day
from app.services.estimates import effort_score, heart_rate_limits, load_workouts
from app.services.plans import match_sessions


XP_WORKOUT = 50
XP_PERSONAL_RECORD = 100
XP_RUNNING_INDEX_RECORD = 50
XP_PLAN_SESSION = 50
XP_MEASUREMENT = 10
MAX_EFFORT_XP = 300

TITLES = [
    (1, "Groentje"),
    (5, "Doorzetter"),
    (10, "Straatvechter"),
    (15, "Zweetmachine"),
    (20, "Kampioen in spe"),
    (30, "IJzervreter"),
    (40, "Legende"),
]

QUESTS = [
    ("three_workouts", "Drie op een rij", "Train 3 keer deze week", 3, 100),
    ("mixed", "Allround", "Doe kracht én duur deze week", 2, 75),
    ("active_minutes", "Blijven bewegen", "Train 150 minuten deze week", 150, 75),
]


def xp_for_level(level: int) -> int:
    """Total XP needed to reach a level. Each level costs 300 XP more.

    At about 600 XP a week, the first levels take days and later ones weeks.
    """
    return 150 * level * (level - 1)


def level_for_xp(xp: int) -> int:
    level = 1

    while xp >= xp_for_level(level + 1):
        level += 1

    return level


def title_for_level(level: int) -> str:
    return [title for minimum, title in TITLES if level >= minimum][-1]


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _new_week_stats() -> dict:
    return {"workouts": 0, "seconds": 0, "strength": False, "endurance": False, "sports": set()}


def _quest_progress(stats: dict) -> list[dict]:
    values = {
        "three_workouts": stats["workouts"],
        "mixed": int(stats["strength"]) + int(stats["endurance"]),
        "active_minutes": stats["seconds"] // 60,
    }

    return [
        {
            "id": quest_id,
            "name": name,
            "description": description,
            "progress": min(values[quest_id], target),
            "target": target,
            "xp": xp,
            "completed": values[quest_id] >= target,
        }
        for quest_id, name, description, target, xp in QUESTS
    ]


def _streak(weeks: set[date], today: date) -> int:
    """Consecutive training weeks. This week can still be saved, so it may be empty."""
    week = _week_start(today)

    if week not in weeks:
        week -= timedelta(weeks=1)

    streak = 0

    while week in weeks:
        streak += 1
        week -= timedelta(weeks=1)

    return streak


class _Badges:
    """Remembers when each badge was first earned."""

    # (id, name, description, target)
    DEFINITIONS = [
        ("first_workout", "Eerste bel", "Doe je eerste training", 1),
        ("workouts_10", "Vaste klant", "Doe 10 trainingen", 10),
        ("workouts_50", "Zaalrat", "Doe 50 trainingen", 50),
        ("workouts_100", "Honderdklapper", "Doe 100 trainingen", 100),
        ("run_100", "Straatloper", "Loop 100 km in totaal", 100),
        ("run_500", "Zolenverslijter", "Loop 500 km in totaal", 500),
        ("ride_1000", "Kilometervreter", "Fiets 1000 km in totaal", 1000),
        ("swim_10", "Waterrat", "Zwem 10 km in totaal", 10),
        ("half_marathon", "Halve finale", "Loop 21,1 km in één keer", 1),
        ("heavy_day", "Vijf ton", "Til 5000 kg in één training", 1),
        ("personal_record", "Nieuw record", "Verbeter je geschatte 1RM", 1),
        ("triathlete", "Drie petten", "Zwem, fiets en loop in één week", 1),
        ("streak_4", "Vier op de vier", "Train 4 weken op rij", 4),
        ("streak_12", "IJzeren discipline", "Train 12 weken op rij", 12),
    ]

    def __init__(self):
        self.progress = defaultdict(float)
        self.earned = {}
        self.targets = {row[0]: row[3] for row in self.DEFINITIONS}

    def set_at_least(self, badge: str, value: float, day: date) -> None:
        self.progress[badge] = max(self.progress[badge], value)

        if badge not in self.earned and self.progress[badge] >= self.targets[badge]:
            self.earned[badge] = day

    def view(self) -> list[dict]:
        return [
            {
                "id": badge,
                "name": name,
                "description": description,
                "progress": min(int(self.progress[badge]), target),
                "target": target,
                "earned_on": (
                    self.earned[badge].isoformat() if badge in self.earned else None
                ),
            }
            for badge, name, description, target in self.DEFINITIONS
        ]


def profile(db: Session, user_id: int, today: date | None = None) -> dict:
    today = today or date.today()

    workouts = load_workouts(db, user_id)
    limits = heart_rate_limits(db, user_id, workouts)

    badges = _Badges()
    events = []
    workout_xp: dict[int, int] = {}
    weeks: dict[date, dict] = defaultdict(_new_week_stats)

    best_estimate: dict[int, float] = {}
    best_running_index = 0
    totals = defaultdict(float)
    count = 0

    for workout in workouts:
        day = parse_day(workout.date)
        activity = workout.endurance_activity
        effort = effort_score(workout, *limits)
        xp = XP_WORKOUT + min(effort, MAX_EFFORT_XP)
        label = "Training"

        count += 1

        for badge in ("first_workout", "workouts_10", "workouts_50", "workouts_100"):
            badges.set_at_least(badge, count, day)

        volume = 0.0
        record = False

        for item in workout.exercises:
            for exercise_set in item.sets:
                if not exercise_set.weight or not exercise_set.reps:
                    continue

                volume += exercise_set.weight * exercise_set.reps
                estimate = estimated_one_rep_max(exercise_set.weight, exercise_set.reps)
                previous = best_estimate.get(item.exercise_id)

                # The first time sets a baseline; only beating it is a record.
                if previous is not None and estimate > previous:
                    record = True

                if previous is None or estimate > previous:
                    best_estimate[item.exercise_id] = estimate

        if record:
            xp += XP_PERSONAL_RECORD
            label = "Training met nieuw record"
            badges.set_at_least("personal_record", 1, day)

        if volume >= 5000:
            badges.set_at_least("heavy_day", 1, day)

        if activity:
            sport = activity.activity_type
            distance = activity.distance or 0
            totals[sport] += distance

            badges.set_at_least("run_100", totals["RUNNING"] / 1000, day)
            badges.set_at_least("run_500", totals["RUNNING"] / 1000, day)
            badges.set_at_least("ride_1000", totals["CYCLING"] / 1000, day)
            badges.set_at_least("swim_10", totals["SWIMMING"] / 1000, day)

            if sport == "RUNNING" and distance >= 21098:
                badges.set_at_least("half_marathon", 1, day)

            if activity.running_index:
                if best_running_index and activity.running_index > best_running_index:
                    xp += XP_RUNNING_INDEX_RECORD
                    label = "Training met beste Running Index"

                best_running_index = max(best_running_index, activity.running_index)

        week = weeks[_week_start(day)]
        week["workouts"] += 1
        week["seconds"] += (activity.duration if activity else None) or workout.duration or 0
        week["strength"] = week["strength"] or workout.type == "STRENGTH"
        week["endurance"] = week["endurance"] or workout.type == "ENDURANCE"

        if activity:
            week["sports"].add(activity.activity_type)

        if {"RUNNING", "CYCLING", "SWIMMING"} <= week["sports"]:
            badges.set_at_least("triathlete", 1, day)

        streak_so_far = _streak(set(weeks), day)
        badges.set_at_least("streak_4", streak_so_far, day)
        badges.set_at_least("streak_12", streak_so_far, day)

        workout_xp[workout.id] = xp
        events.append({"date": day.isoformat(), "label": label, "xp": xp})

    for week_start, stats in weeks.items():
        for quest in _quest_progress(stats):
            if quest["completed"]:
                events.append(
                    {
                        "date": (week_start + timedelta(days=6)).isoformat(),
                        "label": f"Quest: {quest['name']}",
                        "xp": quest["xp"],
                    }
                )

    plans = db.scalars(
        select(TrainingPlan)
        .where(TrainingPlan.user_id == user_id)
        .options(selectinload(TrainingPlan.sessions))
    ).all()

    sessions = {session.id: session for plan in plans for session in plan.sessions}

    for session_id in match_sessions(list(sessions.values()), workouts):
        events.append(
            {
                "date": sessions[session_id].date,
                "label": f"Plan: {sessions[session_id].title}",
                "xp": XP_PLAN_SESSION,
            }
        )

    measurement_dates = db.scalars(
        select(BodyMeasurement.date).where(BodyMeasurement.user_id == user_id)
    ).all()

    for measurement_date in measurement_dates:
        events.append(
            {
                "date": parse_day(measurement_date).isoformat(),
                "label": "Meting",
                "xp": XP_MEASUREMENT,
            }
        )

    # Quests and plan sessions can carry a date later in the current week.
    events.sort(key=lambda event: event["date"], reverse=True)

    xp = sum(event["xp"] for event in events)
    level = level_for_xp(xp)
    floor = xp_for_level(level)
    ceiling = xp_for_level(level + 1)

    return {
        "xp": xp,
        "level": level,
        "title": title_for_level(level),
        "xp_into_level": xp - floor,
        "xp_for_next_level": ceiling - floor,
        "streak_weeks": _streak(set(weeks), today),
        "quests": _quest_progress(weeks[_week_start(today)]),
        "badges": badges.view(),
        "recent": events[:8],
        "workout_xp": workout_xp,
    }
