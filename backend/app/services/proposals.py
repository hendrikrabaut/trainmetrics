"""Proposals for a plan: a language model suggests, the user decides.

Nothing here touches the planning until approve() is called. Because a small
model can get things wrong, every proposal is checked and the warnings are shown
to the user. When the model is not available, the proposal comes from the rules
in plans.py and says so.
"""
import json
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.plan_proposal import PlanProposal
from app.models.training_plan import PlanSession, TrainingPlan
from app.services import coach, plans
from app.services.analytics import parse_day, weekly_summary
from app.services.estimates import estimates, load_workouts
from app.services.insights import best_efforts, zone_summary
from app.services.sleep import sleep_summary


SPORTS = ["RUNNING", "CYCLING", "SWIMMING", "STRENGTH", "OTHER"]

# A small model loses its way over a long plan, so it only plans the coming weeks.
MODEL_WEEKS = 6

LONGEST_RECENT_WEEKS = 8
JUMP_IN_LONG_RUN = 1.3
JUMP_IN_WEEK = 1.3
MAX_RUN_SHARE_BEFORE_RACE = 0.5

SYSTEM_PROMPT = (
    "Je bent een ervaren duursportcoach en stelt een trainingsschema voor. De "
    "sporter beslist zelf en past het nog aan. Baseer je op de JSON-gegevens en "
    "verzin geen data. Bouw voorzichtig op: een lange training groeit hoogstens "
    "10% per week ten opzichte van wat de sporter recent deed, de meeste "
    "trainingen zijn rustig, en voor een wedstrijd wordt het lichter. Plan alleen "
    "op de toegestane data, en volg de wensen van de sporter. Schrijf in het "
    "Nederlands. Geef per training een korte uitleg, en in rationale in maximaal "
    "drie zinnen waarom het schema zo is opgebouwd. Afstand in kilometer, duur in "
    "minuten; laat leeg wat niet van toepassing is."
)

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "rationale": {"type": "string"},
        "sessions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "sport": {"type": "string", "enum": SPORTS},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "distance_km": {"type": ["number", "null"]},
                    "duration_min": {"type": ["number", "null"]},
                },
                "required": ["date", "sport", "title", "description"],
            },
        },
    },
    "required": ["rationale", "sessions"],
}


def _rule_sessions(draft: list[PlanSession], today: date) -> list[dict]:
    return [
        {
            "date": session.date,
            "sport": session.sport,
            "title": session.title,
            "description": session.description,
            "distance": session.distance,
            "duration": session.duration,
            "phase": session.phase,
            "source": "RULES",
        }
        for session in sorted(draft, key=lambda item: item.date)
        if parse_day(session.date) >= today
    ]


def _context(db: Session, user_id: int, today: date) -> dict:
    workouts = load_workouts(db, user_id)
    estimate = estimates(db, user_id, today)
    sleep = sleep_summary(db, user_id, today)
    zones = zone_summary(db, user_id, 12, today)
    cutoff = today - timedelta(weeks=LONGEST_RECENT_WEEKS)

    longest: dict[str, float] = {}

    for workout in workouts:
        activity = workout.endurance_activity

        if activity and activity.distance and parse_day(workout.date) >= cutoff:
            sport = activity.activity_type
            longest[sport] = max(longest.get(sport, 0), activity.distance)

    return {
        "today": today.isoformat(),
        "weekly_summary_last_8_weeks": weekly_summary(db, user_id, 8, today),
        "longest_recent_meters": longest,
        "last_workouts": [
            {
                "date": workout.date[:10],
                "sport": (
                    workout.endurance_activity.activity_type
                    if workout.endurance_activity
                    else workout.type
                ),
                "meters": (
                    workout.endurance_activity.distance
                    if workout.endurance_activity
                    else None
                ),
                "seconds": (
                    workout.endurance_activity.duration
                    if workout.endurance_activity
                    else workout.duration
                ),
            }
            for workout in workouts[-8:]
        ],
        "fitness": estimate["fitness"],
        "race_time_estimates_in_seconds": (
            estimate["best_run"]["predictions"] if estimate["best_run"] else None
        ),
        "best_efforts": [
            {"sport": row["sport"], "meters": row["meters"], "seconds": row["best"][0]["seconds"]}
            for row in best_efforts(db, user_id)
        ],
        "share_of_time_in_easy_zones": zones["easy_share"],
        "sleep_averages": sleep["averages"],
        "recovery_last_night": sleep["recovery"] if sleep["is_recent"] else None,
    }


def _number(value, low: float, high: float) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None

    return float(value) if low < value <= high else None


def parse_model_sessions(raw, first: date, last: date) -> list[dict]:
    """Keeps what is usable. A model can return anything, so nothing is assumed."""
    sessions = []

    for row in raw if isinstance(raw, list) else []:
        if not isinstance(row, dict):
            continue

        try:
            day = date.fromisoformat(str(row.get("date"))[:10])
        except ValueError:
            continue

        title = str(row.get("title") or "").strip()[:100]

        if not first <= day <= last or row.get("sport") not in SPORTS or not title:
            continue

        kilometers = _number(row.get("distance_km"), 0, 400)
        minutes = _number(row.get("duration_min"), 0, 900)

        sessions.append(
            {
                "date": day.isoformat(),
                "sport": row["sport"],
                "title": title,
                "description": str(row.get("description") or "").strip()[:500],
                "distance": round(kilometers * 1000) if kilometers else None,
                "duration": round(minutes * 60) if minutes else None,
                "phase": None,
                "source": "MODEL",
            }
        )

    return sorted(sessions, key=lambda item: item["date"])


def _ask_model(
    db: Session,
    user_id: int,
    goal: str,
    weekdays: list[int],
    first: date,
    last: date,
    race_date: date | None,
    notes: str | None,
    today: date,
) -> tuple[list[dict], str | None]:
    request = {
        "goal": plans.GOAL_NAMES[goal],
        "race_date": race_date.isoformat() if race_date else None,
        "plan_from": first.isoformat(),
        "plan_until": last.isoformat(),
        "preferred_weekdays": [
            ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"][day]
            for day in weekdays
        ],
        "wishes_of_the_athlete": notes or None,
    }

    answer = coach.ask_json(
        SYSTEM_PROMPT,
        "Mijn gegevens:\n"
        f"{json.dumps(_context(db, user_id, today), ensure_ascii=False)}\n\n"
        f"Wat ik vraag:\n{json.dumps(request, ensure_ascii=False)}",
        RESPONSE_SCHEMA,
    )

    if not isinstance(answer, dict):
        raise coach.CoachUnavailable("Het model gaf geen bruikbaar antwoord")

    sessions = parse_model_sessions(answer.get("sessions"), first, last)

    if not sessions:
        raise coach.CoachUnavailable("Het model gaf geen bruikbare trainingen")

    rationale = answer.get("rationale")

    return sessions, str(rationale).strip()[:1000] if rationale else None


def create_proposal(
    db: Session,
    user_id: int,
    goal: str,
    weekdays: list[int],
    weeks: int | None = None,
    start: date | None = None,
    race_date: date | None = None,
    notes: str | None = None,
    use_model: bool = True,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    first_day = start or today

    draft = plans.build_draft(
        db, user_id, goal, weekdays, weeks, first_day, race_date, today
    )
    sessions = _rule_sessions(draft["sessions"], max(first_day, today))

    if not sessions:
        raise plans.PlanError("Er blijven geen trainingen over in deze periode")

    source = "RULES"
    rationale = draft["warning"]
    model_error = None

    if use_model:
        last_day = parse_day(sessions[-1]["date"])
        model_until = min(last_day, first_day + timedelta(weeks=MODEL_WEEKS) - timedelta(days=1))

        try:
            from_model, rationale_of_model = _ask_model(
                db, user_id, goal, draft["weekdays"], first_day, model_until,
                race_date, notes, today,
            )
        except coach.CoachUnavailable as error:
            model_error = str(error)
        else:
            later = [row for row in sessions if parse_day(row["date"]) > model_until]
            race = [
                row for row in sessions
                if row["phase"] == "RACE" and parse_day(row["date"]) <= model_until
            ]

            # The race day itself is not the model's to move or forget.
            kept = [row for row in from_model if not race or row["date"] != race[0]["date"]]
            sessions = sorted(kept + race + later, key=lambda row: row["date"])
            source = "MIXED" if later else "MODEL"
            rationale = rationale_of_model

    db.query(PlanProposal).filter_by(user_id=user_id).delete()

    proposal = PlanProposal(
        user_id=user_id,
        goal=goal,
        race_date=race_date.isoformat() if race_date else None,
        source=source,
        rationale=rationale,
        notes=notes,
        sessions=json.dumps(sessions),
    )

    db.add(proposal)
    db.commit()

    return {**proposal_view(db, proposal, today), "model_error": model_error}


def _km(meters: float) -> str:
    return f"{meters / 1000:.1f}".replace(".", ",")


def _busiest_recent_week(workouts, cutoff: date) -> float:
    weeks: dict[date, float] = {}

    for workout in workouts:
        day = parse_day(workout.date)
        activity = workout.endurance_activity

        if activity and activity.activity_type == "RUNNING" and day >= cutoff:
            monday = day - timedelta(days=day.weekday())
            weeks[monday] = weeks.get(monday, 0) + (activity.distance or 0)

    return max(weeks.values(), default=0)


def check_sessions(
    db: Session,
    user_id: int,
    sessions: list[dict],
    race_date: str | None,
    today: date,
) -> list[str]:
    """Advice for the user. It warns and never blocks: the choice is theirs."""
    warnings = []
    workouts = load_workouts(db, user_id)
    cutoff = today - timedelta(weeks=LONGEST_RECENT_WEEKS)

    recent_long = max(
        (
            workout.endurance_activity.distance or 0
            for workout in workouts
            if workout.endurance_activity
            and workout.endurance_activity.activity_type == "RUNNING"
            and parse_day(workout.date) >= cutoff
        ),
        default=0,
    )

    weeks: dict[date, list[dict]] = {}

    for row in sessions:
        day = parse_day(row["date"])
        weeks.setdefault(day - timedelta(days=day.weekday()), []).append(row)

        if day < today:
            warnings.append(f"{row['title']} staat op {row['date']}, en die dag is voorbij.")

        if race_date and row["date"] > race_date:
            warnings.append(f"{row['title']} staat na je wedstrijd.")

    previous_long = recent_long
    busiest_week = _busiest_recent_week(workouts, cutoff)

    for monday in sorted(weeks):
        rows = weeks[monday]
        runs = [
            row["distance"]
            for row in rows
            if row["sport"] == "RUNNING"
            and row["distance"]
            and row["date"] != race_date
            and not row["title"].startswith("Wedstrijd")
        ]
        longest = max(runs, default=0)
        total = sum(runs)

        if longest and previous_long and longest > previous_long * JUMP_IN_LONG_RUN:
            warnings.append(
                f"Week van {monday:%d/%m}: een loop van {_km(longest)} km is een "
                f"grote sprong tegenover {_km(previous_long)} km."
            )

        # Against the busiest week so far, so that a normal week after a light
        # one, or after a short first week, is no reason for alarm.
        if busiest_week and total > busiest_week * JUMP_IN_WEEK:
            warnings.append(
                f"Week van {monday:%d/%m}: {total / 1000:.0f} km lopen is meer dan 30% "
                f"boven je drukste week tot nu toe ({busiest_week / 1000:.0f} km)."
            )

        if len({row["date"] for row in rows}) == 7:
            warnings.append(f"Week van {monday:%d/%m}: er is geen rustdag.")

        if longest:
            previous_long = max(previous_long, longest)

        busiest_week = max(busiest_week, total)

    if race_date:
        race = parse_day(race_date)
        race_distance = next(
            (row["distance"] for row in sessions if row["date"] == race_date and row["distance"]),
            None,
        )

        for row in sessions:
            before = (race - parse_day(row["date"])).days

            if (
                0 < before <= 3
                and row["sport"] == "RUNNING"
                and race_distance
                and (row["distance"] or 0) > race_distance * MAX_RUN_SHARE_BEFORE_RACE
            ):
                warnings.append(
                    f"{row['title']} is lang, zo kort voor je wedstrijd."
                )

    return warnings


def proposal_view(db: Session, proposal: PlanProposal, today: date | None = None) -> dict:
    sessions = json.loads(proposal.sessions)

    return {
        "goal": proposal.goal,
        "goal_name": plans.GOAL_NAMES[proposal.goal],
        "race_date": proposal.race_date,
        "source": proposal.source,
        "rationale": proposal.rationale,
        "notes": proposal.notes,
        "sessions": sessions,
        "warnings": check_sessions(
            db, proposal.user_id, sessions, proposal.race_date, today or date.today()
        ),
    }


def update_sessions(db: Session, proposal: PlanProposal, sessions: list[dict]) -> None:
    ordered = sorted(sessions, key=lambda row: row["date"])

    for row in ordered:
        row["date"] = str(row["date"])
        row.setdefault("phase", None)
        row["source"] = row.get("source") or "USER"

    proposal.sessions = json.dumps(ordered)
    db.commit()


def approve(db: Session, proposal: PlanProposal, today: date | None = None) -> TrainingPlan:
    """The one moment a proposal becomes part of the planning."""
    today = today or date.today()
    rows = json.loads(proposal.sessions)

    if not rows:
        raise plans.PlanError("Er staan geen trainingen in dit voorstel")

    first = min(parse_day(row["date"]) for row in rows)
    start = first - timedelta(days=first.weekday())
    weekdays = sorted({parse_day(row["date"]).weekday() for row in rows})

    plan = TrainingPlan(
        user_id=proposal.user_id,
        goal=proposal.goal,
        start_date=start.isoformat(),
        end_date=max(row["date"] for row in rows),
        race_date=proposal.race_date,
        weekdays=",".join(str(day) for day in weekdays),
        counts_from=today.isoformat(),
    )

    plan.sessions = [
        PlanSession(
            date=row["date"],
            week=(parse_day(row["date"]) - start).days // 7 + 1,
            sport=row["sport"],
            title=row["title"],
            description=row.get("description") or "",
            distance=row.get("distance"),
            duration=row.get("duration"),
            phase=row.get("phase"),
        )
        for row in rows
    ]

    plans.archive_active(db, proposal.user_id, today)
    db.add(plan)
    db.delete(proposal)
    db.commit()
    db.refresh(plan)

    return plan
