"""Answers questions through a local Ollama model, usually on another machine.

The backend does all calculations. The model only gets the resulting summary
and explains it, so it has no reason to work out numbers itself.
"""
import json
import os
import re
import urllib.error
import urllib.request

from sqlalchemy.orm import Session

from app.services.analytics import (
    body_weight_history,
    personal_records,
    weekly_summary,
)
from app.services.estimates import estimates
from app.services.game import profile
from app.services.plans import active_plan, plan_view


SYSTEM_PROMPT = (
    "Je bent de Coach, een oude, norse bokstrainer met een klein hart voor je "
    "pupil. Je spreekt in korte, droge zinnen, in het Nederlands. Je bent streng "
    "maar eerlijk, en je scheldt nooit. Antwoord in maximaal vijf zinnen. Baseer "
    "cijfers uitsluitend op de JSON-gegevens die je krijgt en verzin geen data. "
    "Staat het antwoord er niet in, zeg dat dan. Afstanden staan in meter, duur "
    "in seconden en gewichten in kilogram. Het trainingsplan wordt door de app "
    "gemaakt: leg het uit en moedig aan, maar verander het niet. Stuur bij pijn "
    "of blessures door naar een arts of kinesist en stel geen diagnoses."
)


class CoachUnavailable(Exception):
    """The model could not be reached or gave no usable answer."""


def _settings() -> tuple[str, str, float]:
    return (
        os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/"),
        os.environ.get("OLLAMA_MODEL", "qwen3:4b"),
        float(os.environ.get("OLLAMA_TIMEOUT", "180")),
    )


def _plan_context(db: Session, user_id: int) -> dict | None:
    plan = active_plan(db, user_id)

    if plan is None:
        return None

    view = plan_view(db, plan)
    upcoming = [
        session for session in view["sessions"] if not session["completed"]
    ][:7]

    return {
        "goal": view["goal_name"],
        "race_date": view["race_date"],
        "sessions_completed": view["completed"],
        "sessions_total": view["total"],
        "next_sessions": upcoming,
    }


def build_context(db: Session, user_id: int) -> dict:
    estimate = estimates(db, user_id)
    game = profile(db, user_id)

    return {
        "weekly_summary_last_12_weeks": weekly_summary(db, user_id),
        "personal_records": personal_records(db, user_id),
        "body_weight_history": body_weight_history(db, user_id)[-20:],
        "fitness": estimate["fitness"],
        "running_index_average": (
            estimate["running_index"]["average"]
            if estimate["running_index"]
            else None
        ),
        "race_time_estimates_in_seconds": (
            estimate["running_index"]["predictions"]
            if estimate["running_index"]
            else None
        ),
        "level": game["level"],
        "streak_weeks": game["streak_weeks"],
        "training_plan": _plan_context(db, user_id),
    }


def ask(db: Session, user_id: int, question: str) -> str:
    url, model, timeout = _settings()

    context = json.dumps(build_context(db, user_id), ensure_ascii=False)

    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Mijn gegevens:\n{context}\n\nVraag: {question}",
            },
        ],
    }

    request = urllib.request.Request(
        f"{url}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            answer = json.load(response)["message"]["content"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise CoachUnavailable(str(error)) from error

    # Some models write their reasoning into the answer between think tags.
    answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()

    if not answer:
        raise CoachUnavailable("The model returned an empty answer")

    return answer
