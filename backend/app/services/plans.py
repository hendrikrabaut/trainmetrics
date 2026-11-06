"""Builds training plans with fixed rules, so they work without any AI model.

A long session grows at most 10% per week, every fourth week is lighter and the
last week before the end is a taper. Paces come from the user's own estimates.
"""
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.training_plan import PlanSession, TrainingPlan
from app.services.analytics import parse_day
from app.services.estimates import (
    best_recent_run,
    load_workouts,
    running_index_summary,
)


MAX_WEEKLY_GROWTH = 1.10
DELOAD_EVERY = 4
DELOAD_FACTOR = 0.7
TAPER_FACTOR = 0.55
BASELINE_WEEKS = 8

SLOTS = {
    2: [2, 6],
    3: [1, 3, 6],
    4: [1, 3, 5, 6],
    5: [0, 1, 3, 5, 6],
    6: [0, 1, 2, 3, 5, 6],
    7: [0, 1, 2, 3, 4, 5, 6],
}

# Peak long run, the shortest long run that still prepares you, and the race.
RUN_GOALS = {
    "5K": (9000, 6000, 5000),
    "10K": (14000, 10000, 10000),
    "HALF": (19000, 16000, 21098),
}
TRIATHLON_LONG_RUN = (15000, 10000)

GOAL_NAMES = {
    "5K": "5 km",
    "10K": "10 km",
    "HALF": "halve marathon",
    "TRIATHLON": "triatlon",
    "STRENGTH": "kracht",
    "FITNESS": "algemene conditie",
}

WEEKS_BY_GOAL = {
    "5K": 8,
    "10K": 10,
    "HALF": 12,
    "TRIATHLON": 12,
    "STRENGTH": 8,
    "FITNESS": 8,
}

MINIMUM_SESSIONS = {"TRIATHLON": 3}


class PlanError(ValueError):
    """The requested plan is not possible."""


@dataclass
class Draft:
    sport: str
    title: str
    description: str
    distance: float | None = None
    duration: int | None = None


def _clock(seconds: float) -> str:
    whole = round(seconds)
    return f"{whole // 60}:{whole % 60:02d}"


def _paces(workouts) -> dict[str, str] | None:
    """Training paces in seconds per km, from the user's own estimates."""
    index = running_index_summary(workouts)
    predictions = index["predictions"] if index else None

    if predictions is None:
        best = best_recent_run(workouts)
        predictions = best["predictions"] if best else None

    if predictions is None:
        return None

    five = predictions["5 km"] / 5
    ten = predictions["10 km"] / 10

    return {
        "easy": f"rond {_clock(ten * 1.20)} /km",
        "tempo": f"rond {_clock(ten * 1.03)} /km",
        "interval": f"rond {_clock(five)} /km",
    }


def _pace_text(paces, kind: str) -> str:
    return f" Tempo: {paces[kind]}." if paces else ""


def _longest_recent(workouts, sport: str, today: date) -> float:
    cutoff = today - timedelta(weeks=BASELINE_WEEKS)

    return max(
        (
            workout.endurance_activity.distance or 0
            for workout in workouts
            if workout.endurance_activity
            and workout.endurance_activity.activity_type == sport
            and parse_day(workout.date) >= cutoff
        ),
        default=0,
    )


def _build_curve(start: float, peak: float, weeks: int) -> list[float]:
    """Weekly size of the long session."""
    taper_weeks = 1 if weeks >= 4 else 0
    curve = []
    current = start

    for week in range(1, weeks + 1):
        if weeks - week < taper_weeks:
            curve.append(max(curve) * TAPER_FACTOR)
        elif week % DELOAD_EVERY == 0:
            curve.append(current * DELOAD_FACTOR)
        else:
            curve.append(current)
            current = min(current * MAX_WEEKLY_GROWTH, peak)

    return curve


def _kilometers(meters: float) -> str:
    return f"{meters / 1000:.1f}".replace(".", ",") + " km"


def _run_week(goal, long_run, week, paces) -> list[Draft]:
    intervals = {
        "5K": "6 × 400 m stevig, met 90 seconden wandelen of joggen ertussen.",
        "10K": "5 × 800 m stevig, met 2 minuten joggen ertussen.",
        "HALF": "4 × 1500 m stevig, met 2 minuten joggen ertussen.",
    }[goal]

    quality = (
        Draft(
            "RUNNING",
            "Intervallen",
            f"Eerst 15 minuten inlopen. Daarna {intervals}"
            f"{_pace_text(paces, 'interval')} Sluit af met 10 minuten uitlopen.",
        )
        if week % 2
        else Draft(
            "RUNNING",
            "Tempoloop",
            f"10 minuten inlopen, 20 minuten stevig maar beheerst, 10 minuten "
            f"uitlopen.{_pace_text(paces, 'tempo')}",
        )
    )

    easy = long_run * 0.6

    return [
        Draft(
            "RUNNING",
            "Lange duurloop",
            f"Rustig tempo, je moet kunnen praten.{_pace_text(paces, 'easy')}",
            distance=long_run,
        ),
        quality,
        Draft(
            "RUNNING",
            "Rustige loop",
            f"Herstelloop zonder druk.{_pace_text(paces, 'easy')}",
            distance=easy,
        ),
        _strength_session("A"),
        Draft(
            "RUNNING",
            "Rustige loop",
            f"Korte, ontspannen loop.{_pace_text(paces, 'easy')}",
            distance=easy * 0.8,
        ),
        Draft("CYCLING", "Rustige fietstocht", "Licht herstel op de fiets.", duration=3600),
        Draft("RUNNING", "Hersteljog", "Heel rustig, maximaal 30 minuten.", duration=1800),
    ]


def _triathlon_week(long_run, share, week, paces) -> list[Draft]:
    bike_minutes = round(60 + 90 * share)
    swim_meters = round((1000 + 1000 * share) / 100) * 100

    return [
        Draft(
            "RUNNING",
            "Lange duurloop",
            f"Rustig tempo.{_pace_text(paces, 'easy')}",
            distance=long_run,
        ),
        Draft(
            "CYCLING",
            "Lange rit",
            "Rustig en gelijkmatig. Oefen ook je eten en drinken onderweg."
            if week % 2
            else "Brick: fiets rustig en loop meteen daarna 15 minuten, om de "
            "overgang te oefenen.",
            duration=bike_minutes * 60,
        ),
        Draft(
            "SWIMMING",
            "Duurzwemmen",
            "Inzwemmen, dan lange stukken op een rustig tempo met aandacht "
            "voor je techniek.",
            distance=swim_meters,
        ),
        Draft(
            "RUNNING",
            "Tempoloop",
            f"10 minuten inlopen, 20 minuten stevig, 10 minuten uitlopen."
            f"{_pace_text(paces, 'tempo')}",
        ),
        Draft(
            "SWIMMING",
            "Intervalzwemmen",
            "8 × 100 m stevig met 20 seconden rust, met in- en uitzwemmen.",
            distance=swim_meters * 0.8,
        ),
        Draft(
            "CYCLING",
            "Fietsintervallen",
            "5 × 5 minuten stevig met 3 minuten rustig ertussen.",
            duration=3600,
        ),
        _strength_session("A"),
    ]


def _strength_session(variant: str, reps: str = "3 × 10") -> Draft:
    programs = {
        "A": "squat, bankdrukken, roeien",
        "B": "deadlift, schouderdrukken, lat pulldown",
        "C": "lunges, schuin bankdrukken, cable row",
    }

    return Draft(
        "STRENGTH",
        f"Kracht {variant}",
        f"{programs[variant].capitalize()}: {reps}. Stop met telkens nog één à "
        "twee herhalingen over. Lukt alles netjes, doe er dan de volgende keer "
        "een klein beetje gewicht bij.",
        duration=3000,
    )


def _strength_week(week, deload: bool) -> list[Draft]:
    reps = "2 × 8, licht" if deload else ("3 × 10" if week % 8 <= 4 else "4 × 6")

    return [
        _strength_session("A", reps),
        _strength_session("B", reps),
        _strength_session("C", reps),
        Draft("RUNNING", "Rustige loop", "30 minuten licht bewegen.", duration=1800),
        _strength_session("A", reps),
        Draft("CYCLING", "Rustige fietstocht", "Licht herstel op de fiets.", duration=3600),
        _strength_session("B", reps),
    ]


def _fitness_week(share) -> list[Draft]:
    minutes = round(30 + 30 * share)

    return [
        Draft("RUNNING", "Duurloop", "Rustig tempo, je moet kunnen praten.", duration=minutes * 60),
        _strength_session("A"),
        Draft("CYCLING", "Fietstocht", "Rustig en gelijkmatig.", duration=(minutes + 30) * 60),
        _strength_session("B"),
        Draft("SWIMMING", "Zwemmen", "Rustig baantjes trekken.", duration=minutes * 60),
        Draft("RUNNING", "Intervallen", "6 × 1 minuut stevig met 2 minuten rustig ertussen.", duration=1800),
        _strength_session("C"),
    ]


def next_monday(today: date) -> date:
    return today + timedelta(days=7 - today.weekday())


def _archive_active(db: Session, user_id: int, today: date) -> None:
    """Keeps past sessions for the XP history and drops the ones still to come."""
    plans = db.scalars(
        select(TrainingPlan).where(
            TrainingPlan.user_id == user_id,
            TrainingPlan.status == "ACTIVE",
        )
    ).all()

    for plan in plans:
        plan.status = "ARCHIVED"
        plan.sessions = [
            session
            for session in plan.sessions
            if parse_day(session.date) < today
        ]


def _check_weekdays(goal: str, weekdays: list[int]) -> list[int]:
    days = sorted(set(weekdays))

    if any(day not in range(7) for day in days):
        raise PlanError("Een weekdag is een getal van 0 (maandag) tot 6 (zondag)")

    minimum = MINIMUM_SESSIONS.get(goal, 2)

    if len(days) < minimum:
        raise PlanError(f"Dit doel vraagt minstens {minimum} trainingen per week")

    return days


def _first_long_run(goal: str, workouts, today: date) -> float | None:
    if goal not in RUN_GOALS and goal != "TRIATHLON":
        return None

    peak = RUN_GOALS[goal][0] if goal in RUN_GOALS else TRIATHLON_LONG_RUN[0]
    longest = _longest_recent(workouts, "RUNNING", today)

    return max(min(longest, peak * 0.9), peak * 0.4)


def _curve(goal: str, first: float | None, weeks: int) -> list[float]:
    if first is None:
        return [1.0] * weeks

    peak = RUN_GOALS[goal][0] if goal in RUN_GOALS else TRIATHLON_LONG_RUN[0]

    return _build_curve(first, peak, weeks)


def _build_sessions(
    goal: str,
    start: date,
    weeks: int,
    weekdays: list[int],
    race_date: date | None,
    curve: list[float],
    paces,
) -> list[PlanSession]:
    sessions = []

    for index in range(weeks):
        week = index + 1
        share = index / max(weeks - 1, 1)
        deload = week % DELOAD_EVERY == 0

        if goal in RUN_GOALS:
            drafts = _run_week(goal, curve[index], week, paces)
        elif goal == "TRIATHLON":
            drafts = _triathlon_week(curve[index], share, week, paces)
        elif goal == "STRENGTH":
            drafts = _strength_week(week, deload)
        else:
            drafts = _fitness_week(share)

        drafts = drafts[:len(weekdays)]

        # The most important sessions go on the last training days of the week.
        for draft, weekday in zip(drafts, reversed(weekdays)):
            day = start + timedelta(weeks=index, days=weekday)

            if race_date is not None and day >= race_date:
                continue

            sessions.append(
                PlanSession(
                    date=day.isoformat(),
                    week=week,
                    sport=draft.sport,
                    title=draft.title,
                    description=draft.description,
                    distance=round(draft.distance) if draft.distance else None,
                    duration=draft.duration,
                )
            )

    if race_date is not None:
        sessions.append(
            PlanSession(
                date=race_date.isoformat(),
                week=weeks,
                sport="SWIMMING" if goal == "TRIATHLON" else "RUNNING",
                title="Wedstrijddag",
                description="Dit is waar je voor getraind hebt. Begin rustig en geniet ervan.",
                distance=RUN_GOALS[goal][2] if goal in RUN_GOALS else None,
            )
        )

    return sessions


def create_plan(
    db: Session,
    user_id: int,
    goal: str,
    sessions_per_week: int,
    weeks: int | None = None,
    start: date | None = None,
    race_date: date | None = None,
    today: date | None = None,
    weekdays: list[int] | None = None,
) -> TrainingPlan:
    today = today or date.today()
    start = start or next_monday(today)
    start = start - timedelta(days=start.weekday())

    if start + timedelta(days=6) < today:
        raise PlanError("De startdatum ligt in het verleden")

    days = _check_weekdays(goal, weekdays or SLOTS[sessions_per_week])

    if race_date is not None:
        if race_date <= start:
            raise PlanError("De wedstrijd moet na de start van het plan liggen")

        weeks = math.ceil(((race_date - start).days + 1) / 7)

    weeks = weeks or WEEKS_BY_GOAL[goal]

    if not 2 <= weeks <= 30:
        raise PlanError("Een plan duurt 2 tot 30 weken")

    workouts = load_workouts(db, user_id)
    first = _first_long_run(goal, workouts, today)
    curve = _curve(goal, first, weeks)
    warning = None

    if first is not None:
        minimum = RUN_GOALS[goal][1] if goal in RUN_GOALS else TRIATHLON_LONG_RUN[1]

        if max(curve) < minimum:
            warning = (
                f"In {weeks} weken haal je veilig maar een lange duurloop van "
                f"{_kilometers(max(curve))}. Voor je doel is {_kilometers(minimum)} "
                "beter, dus neem liever meer tijd."
            )

    plan = TrainingPlan(
        user_id=user_id,
        goal=goal,
        start_date=start.isoformat(),
        end_date="",
        race_date=race_date.isoformat() if race_date else None,
        warning=warning,
        weekdays=",".join(str(day) for day in days),
        first_long_run=first,
    )

    plan.sessions = _build_sessions(
        goal, start, weeks, days, race_date, curve, _paces(workouts)
    )
    plan.sessions.sort(key=lambda session: session.date)
    plan.end_date = plan.sessions[-1].date

    _archive_active(db, user_id, today)
    db.add(plan)
    db.commit()
    db.refresh(plan)

    return plan


def plan_weekdays(plan: TrainingPlan) -> list[int]:
    if plan.weekdays:
        return [int(day) for day in plan.weekdays.split(",")]

    first_week = min(session.week for session in plan.sessions)

    return sorted(
        {
            parse_day(session.date).weekday()
            for session in plan.sessions
            if session.week == first_week
        }
    )


def reschedule_plan(
    db: Session,
    plan: TrainingPlan,
    weekdays: list[int],
    today: date | None = None,
) -> TrainingPlan:
    """Rebuilds everything from today on. What is already past stays as it was."""
    today = today or date.today()
    days = _check_weekdays(plan.goal, weekdays)
    weeks = max(session.week for session in plan.sessions)
    start = parse_day(plan.start_date)
    race_date = parse_day(plan.race_date) if plan.race_date else None

    if parse_day(plan.end_date) < today:
        raise PlanError("Dit plan is al voorbij. Maak een nieuw plan.")

    first = plan.first_long_run

    if first is None:
        # Plans made before this was stored: their first long run still says it.
        first = next(
            (
                session.distance
                for session in plan.sessions
                if session.title == "Lange duurloop"
            ),
            None,
        )

    workouts = load_workouts(db, plan.user_id)
    sessions = _build_sessions(
        plan.goal,
        start,
        weeks,
        days,
        race_date,
        _curve(plan.goal, first, weeks),
        _paces(workouts),
    )

    plan.sessions = [
        *(s for s in plan.sessions if parse_day(s.date) < today),
        *(s for s in sessions if parse_day(s.date) >= today),
    ]

    if not plan.sessions:
        raise PlanError("Er blijven geen trainingen over met deze dagen")

    plan.sessions.sort(key=lambda session: session.date)
    plan.weekdays = ",".join(str(day) for day in days)
    plan.end_date = plan.sessions[-1].date
    db.commit()
    db.refresh(plan)

    return plan


def update_session(
    db: Session,
    session: PlanSession,
    changes: dict,
) -> PlanSession:
    plan = session.plan

    if "date" in changes:
        day = changes["date"]
        start = parse_day(plan.start_date)

        if day < start:
            raise PlanError("Die dag ligt voor de start van het plan")

        limit = start + timedelta(weeks=30)

        if day > limit:
            raise PlanError("Die dag ligt te ver na de start van het plan")

        changes["date"] = day.isoformat()
        session.week = (day - start).days // 7 + 1

    for field, value in changes.items():
        setattr(session, field, value)

    db.flush()
    plan.end_date = max(item.date for item in plan.sessions)
    db.commit()

    return session


def delete_session(db: Session, session: PlanSession) -> None:
    plan = session.plan

    if len(plan.sessions) == 1:
        raise PlanError("Dit is de laatste training van het plan")

    plan.sessions.remove(session)
    db.flush()
    plan.end_date = max(item.date for item in plan.sessions)
    db.commit()


def _ical_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _ical_line(line: str) -> str:
    """Folds at 75 octets as RFC 5545 asks, without splitting a character."""
    parts = []
    current = b""

    for character in line:
        encoded = character.encode("utf-8")

        if len(current) + len(encoded) > (75 if not parts else 74):
            parts.append(current.decode("utf-8"))
            current = b""

        current += encoded

    parts.append(current.decode("utf-8"))

    return "\r\n ".join(parts)


def plan_to_ical(plan: TrainingPlan, now: datetime | None = None) -> str:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//TrainMetrics//Trainingsplan//NL",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_ical_text('TrainMetrics: ' + GOAL_NAMES[plan.goal])}",
    ]

    for session in plan.sessions:
        day = parse_day(session.date)

        details = [
            f"{session.distance / 1000:.1f}".replace(".", ",") + " km"
            if session.distance
            else None,
            f"{session.duration // 60} min" if session.duration else None,
            session.description,
        ]

        lines += [
            "BEGIN:VEVENT",
            # Stable for a day and sport, so importing again updates rather
            # than repeats a training that did not move.
            f"UID:plan-{plan.id}-{day:%Y%m%d}-{session.sport.lower()}@trainmetrics",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
            f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{_ical_text(session.title)}",
            f"DESCRIPTION:{_ical_text(chr(10).join(item for item in details if item))}",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")

    return "\r\n".join(_ical_line(line) for line in lines) + "\r\n"


def _workout_sport(workout) -> str:
    if workout.endurance_activity:
        return workout.endurance_activity.activity_type

    return workout.type


def match_sessions(sessions, workouts) -> dict[int, int]:
    """Session id -> workout id.

    A session counts when a workout of that sport happens in the same week, so
    moving a training by a day does not lose it. Each workout counts only once.
    """
    available: dict[tuple, list] = {}

    for workout in workouts:
        day = parse_day(workout.date)
        key = (day.isocalendar()[:2], _workout_sport(workout))
        available.setdefault(key, []).append(workout)

    matched = {}

    for session in sorted(sessions, key=lambda item: item.date):
        day = parse_day(session.date)
        candidates = available.get((day.isocalendar()[:2], session.sport), [])

        if candidates:
            matched[session.id] = candidates.pop(0).id

    return matched


def active_plan(db: Session, user_id: int) -> TrainingPlan | None:
    return db.scalar(
        select(TrainingPlan)
        .where(
            TrainingPlan.user_id == user_id,
            TrainingPlan.status == "ACTIVE",
        )
        .options(selectinload(TrainingPlan.sessions))
    )


def plan_view(db: Session, plan: TrainingPlan, today: date | None = None) -> dict:
    today = today or date.today()
    matched = match_sessions(plan.sessions, load_workouts(db, plan.user_id))

    sessions = [
        {
            "id": session.id,
            "date": session.date,
            "week": session.week,
            "sport": session.sport,
            "title": session.title,
            "description": session.description,
            "distance": session.distance,
            "duration": session.duration,
            "completed": session.id in matched,
            "missed": (
                session.id not in matched
                and parse_day(session.date) < today - timedelta(days=today.weekday())
            ),
        }
        for session in plan.sessions
    ]

    return {
        "id": plan.id,
        "goal": plan.goal,
        "goal_name": GOAL_NAMES[plan.goal],
        "start_date": plan.start_date,
        "end_date": plan.end_date,
        "race_date": plan.race_date,
        "warning": plan.warning,
        "weekdays": plan_weekdays(plan),
        "completed": sum(session["completed"] for session in sessions),
        "total": len(sessions),
        "sessions": sessions,
    }
