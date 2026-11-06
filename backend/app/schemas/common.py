from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, Field


def _check_iso_date(value: str) -> str:
    try:
        datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(
            "Must be an ISO date, such as 2026-10-01 or 2026-10-01T18:00:00"
        ) from error

    return value


IsoDate = Annotated[str, AfterValidator(_check_iso_date)]

NonNegativeFloat = Annotated[float, Field(ge=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]
HeartRate = Annotated[int, Field(gt=0, le=260)]

WorkoutType = Literal["STRENGTH", "ENDURANCE"]
ActivityType = Literal["RUNNING", "CYCLING", "SWIMMING", "OTHER"]


def speed_in_meters_per_second(
    distance: float | None,
    duration: int | None,
) -> float | None:
    """Average speed in m/s, the unit average_speed is always stored in."""
    if not distance or not duration:
        return None

    return round(distance / duration, 2)
