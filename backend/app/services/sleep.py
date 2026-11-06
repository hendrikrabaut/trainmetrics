"""Sleep and recovery per night, from the Polar export and the Polar API."""
import statistics
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sleep_night import SleepNight
from app.services.analytics import parse_day


BASELINE_NIGHTS = 28
MINIMUM_BASELINE_NIGHTS = 7
SUMMARY_NIGHTS = 30
RECENT_DAYS = 2
LOW_DEVIATION = -1
GOOD_DEVIATION = 0.2


def store_night(db: Session, user_id: int, night: str, values: dict) -> SleepNight:
    """Creates or fills in a night. An empty value never overwrites a known one."""
    row = db.get(SleepNight, (user_id, night))

    if row is None:
        row = SleepNight(user_id=user_id, night=night)
        db.add(row)

    for field, value in values.items():
        if value is not None:
            setattr(row, field, value)

    return row


def _status_from_polar(recharge_status: int) -> str:
    if recharge_status <= 2:
        return "LOW"

    return "OK" if recharge_status <= 4 else "GOOD"


def _recovery(night: SleepNight, earlier: list[SleepNight]) -> dict | None:
    """Polar's own verdict when there is one, otherwise this app's estimate.

    The estimate compares heart rate variability with the user's own normal. Its
    limits gave the same category as Polar on 20 of 23 real nights, against 17
    with a rule that also used the sleep score. That is a small sample, so it
    only stands in for nights without a verdict from Polar.
    """
    if night.recharge_status:
        return {
            "source": "POLAR",
            "status": _status_from_polar(night.recharge_status),
            "recharge_status": night.recharge_status,
            "ans_charge": night.ans_charge,
        }

    baseline = [row.hrv_ms for row in earlier if row.hrv_ms][-BASELINE_NIGHTS:]

    if not night.hrv_ms or len(baseline) < MINIMUM_BASELINE_NIGHTS:
        return None

    mean = statistics.fmean(baseline)
    deviation = (night.hrv_ms - mean) / (statistics.stdev(baseline) or 1)

    if deviation < LOW_DEVIATION:
        status = "LOW"
    elif deviation > GOOD_DEVIATION:
        status = "GOOD"
    else:
        status = "OK"

    return {
        "source": "ESTIMATE",
        "status": status,
        "hrv_ms": round(night.hrv_ms),
        "baseline_ms": round(mean),
        "baseline_nights": len(baseline),
    }


def _average(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _night_view(row: SleepNight) -> dict:
    return {
        "night": row.night,
        "sleep_start": row.sleep_start,
        "sleep_end": row.sleep_end,
        "asleep_seconds": row.asleep_seconds,
        "light_seconds": row.light_seconds,
        "deep_seconds": row.deep_seconds,
        "rem_seconds": row.rem_seconds,
        "interruption_seconds": row.interruption_seconds,
        "continuity": row.continuity,
        "sleep_score": round(row.sleep_score) if row.sleep_score is not None else None,
        "hrv_ms": round(row.hrv_ms) if row.hrv_ms else None,
        "heart_rate": round(row.heart_rate) if row.heart_rate else None,
        "breathing_rate": round(row.breathing_rate, 1) if row.breathing_rate else None,
        "recharge_status": row.recharge_status,
    }


def sleep_summary(db: Session, user_id: int, today: date | None = None) -> dict:
    today = today or date.today()

    rows = list(
        db.scalars(
            select(SleepNight)
            .where(SleepNight.user_id == user_id)
            .order_by(SleepNight.night)
        )
    )

    if not rows:
        return {"last_night": None, "recovery": None, "is_recent": False, "averages": None, "nights": []}

    last = rows[-1]
    recent = rows[-SUMMARY_NIGHTS:]

    def mean_of(field):
        return _average([getattr(row, field) for row in recent if getattr(row, field)])

    def rounded(value, digits=0):
        return round(value, digits) if value is not None else None

    return {
        "last_night": _night_view(last),
        "recovery": _recovery(last, rows[:-1]),
        "is_recent": parse_day(last.night) >= today - timedelta(days=RECENT_DAYS),
        "averages": {
            "nights": len(recent),
            "asleep_seconds": rounded(mean_of("asleep_seconds")),
            "light_seconds": rounded(mean_of("light_seconds")),
            "deep_seconds": rounded(mean_of("deep_seconds")),
            "rem_seconds": rounded(mean_of("rem_seconds")),
            "sleep_score": rounded(mean_of("sleep_score")),
            "hrv_ms": rounded(mean_of("hrv_ms")),
            "heart_rate": rounded(mean_of("heart_rate")),
            "breathing_rate": rounded(mean_of("breathing_rate"), 1),
        },
        "nights": [_night_view(row) for row in recent],
    }
