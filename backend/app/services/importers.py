"""Reads endurance activities from FIT, GPX and TCX files.

All values are normalized to the units the database uses: meters, seconds, m/s.
"""
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

import fitdecode
import gpxpy
from gpxpy.gpx import GPXException

from app.schemas.common import speed_in_meters_per_second


TCX_NAMESPACE = "{http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2}"


class ActivityFileError(ValueError):
    """The file could not be read as an activity."""


@dataclass
class ParsedActivity:
    date: str
    activity_type: str
    distance: float | None = None
    duration: int | None = None
    average_speed: float | None = None
    average_heart_rate: int | None = None
    max_heart_rate: int | None = None
    elevation_gain: float | None = None
    calories: int | None = None


def _activity_type(sport: str | None) -> str:
    sport = (sport or "").lower()

    if "run" in sport:
        return "RUNNING"

    if "cycl" in sport or "bik" in sport or "ride" in sport:
        return "CYCLING"

    if "swim" in sport:
        return "SWIMMING"

    return "OTHER"


def _local_time(value: datetime) -> str:
    """Stored dates are local, so a morning run stays on the right day."""
    if value.tzinfo is not None:
        value = value.astimezone().replace(tzinfo=None)

    return value.isoformat(timespec="seconds")


def _whole(value) -> int | None:
    return None if value is None else round(value)


def _parse_fit(content: bytes) -> list[ParsedActivity]:
    activities = []

    # A multisport file, like a triathlon, holds one session per discipline.
    with fitdecode.FitReader(BytesIO(content)) as reader:
        for frame in reader:
            if frame.frame_type != fitdecode.FIT_FRAME_DATA or frame.name != "session":
                continue

            def value(name):
                return frame.get_value(name, fallback=None)

            sport = value("sport")

            if str(sport).lower() == "transition":
                continue

            start = value("start_time")

            if not isinstance(start, datetime):
                raise ActivityFileError("FIT session has no start time")

            distance = value("total_distance")
            timer = value("total_timer_time")
            duration = _whole(timer if timer is not None else value("total_elapsed_time"))
            speed = value("enhanced_avg_speed")

            if speed is None:
                speed = value("avg_speed")

            activities.append(
                ParsedActivity(
                    date=_local_time(start),
                    activity_type=_activity_type(str(sport)),
                    distance=distance,
                    duration=duration,
                    average_speed=(
                        round(speed, 2)
                        if speed is not None
                        else speed_in_meters_per_second(distance, duration)
                    ),
                    average_heart_rate=_whole(value("avg_heart_rate")),
                    max_heart_rate=_whole(value("max_heart_rate")),
                    elevation_gain=value("total_ascent"),
                    calories=_whole(value("total_calories")),
                )
            )

    return activities


def _gpx_heart_rates(track) -> list[int]:
    # Heart rate is a device extension, such as <gpxtpx:hr>, in any namespace.
    rates = []

    for segment in track.segments:
        for point in segment.points:
            for extension in point.extensions:
                for element in extension.iter():
                    if element.tag.rsplit("}", 1)[-1] == "hr" and element.text:
                        rates.append(int(float(element.text)))

    return rates


def _parse_gpx(content: bytes) -> list[ParsedActivity]:
    gpx = gpxpy.parse(content.decode("utf-8-sig"))
    activities = []

    for track in gpx.tracks:
        start = track.get_time_bounds().start_time

        if start is None:
            raise ActivityFileError("GPX track has no timestamps")

        distance = round(track.length_2d(), 1)
        duration = _whole(track.get_duration())
        rates = _gpx_heart_rates(track)

        activities.append(
            ParsedActivity(
                date=_local_time(start),
                activity_type=_activity_type(track.type or track.name),
                distance=distance,
                duration=duration,
                average_speed=speed_in_meters_per_second(distance, duration),
                average_heart_rate=round(sum(rates) / len(rates)) if rates else None,
                max_heart_rate=max(rates) if rates else None,
                elevation_gain=round(track.get_uphill_downhill().uphill, 1),
            )
        )

    return activities


def _tcx_number(element, *path: str) -> float | None:
    found = element.find("/".join(f"{TCX_NAMESPACE}{name}" for name in path))

    if found is None or found.text is None:
        return None

    return float(found.text)


def _parse_tcx(content: bytes) -> list[ParsedActivity]:
    root = ElementTree.fromstring(content)
    activities = []

    for activity in root.iter(f"{TCX_NAMESPACE}Activity"):
        laps = activity.findall(f"{TCX_NAMESPACE}Lap")

        if not laps:
            continue

        start = activity.findtext(f"{TCX_NAMESPACE}Id") or laps[0].get("StartTime")

        if not start:
            raise ActivityFileError("TCX activity has no start time")

        duration = 0.0
        distance = 0.0
        calories = 0.0
        heart_rate_seconds = 0.0
        heart_rate_weighted = 0.0
        max_heart_rate = None

        for lap in laps:
            lap_duration = _tcx_number(lap, "TotalTimeSeconds") or 0
            duration += lap_duration
            distance += _tcx_number(lap, "DistanceMeters") or 0
            calories += _tcx_number(lap, "Calories") or 0

            average = _tcx_number(lap, "AverageHeartRateBpm", "Value")
            maximum = _tcx_number(lap, "MaximumHeartRateBpm", "Value")

            if average is not None and lap_duration:
                heart_rate_seconds += lap_duration
                heart_rate_weighted += average * lap_duration

            if maximum is not None:
                max_heart_rate = max(max_heart_rate or 0, maximum)

        ascent = 0.0
        previous = None

        for altitude in activity.iter(f"{TCX_NAMESPACE}AltitudeMeters"):
            current = float(altitude.text)

            if previous is not None and current > previous:
                ascent += current - previous

            previous = current

        whole_duration = round(duration)

        activities.append(
            ParsedActivity(
                date=_local_time(datetime.fromisoformat(start)),
                activity_type=_activity_type(activity.get("Sport")),
                distance=distance,
                duration=whole_duration,
                average_speed=speed_in_meters_per_second(distance, whole_duration),
                average_heart_rate=(
                    round(heart_rate_weighted / heart_rate_seconds)
                    if heart_rate_seconds
                    else None
                ),
                max_heart_rate=_whole(max_heart_rate),
                elevation_gain=round(ascent, 1) if previous is not None else None,
                calories=round(calories) if calories else None,
            )
        )

    return activities


PARSERS = {
    ".fit": _parse_fit,
    ".gpx": _parse_gpx,
    ".tcx": _parse_tcx,
}


def parse_activity_file(filename: str, content: bytes) -> list[ParsedActivity]:
    suffix = Path(filename).suffix.lower()
    parser = PARSERS.get(suffix)

    if parser is None:
        raise ActivityFileError("Only .fit, .gpx and .tcx files are supported")

    try:
        activities = parser(content)
    except ActivityFileError:
        raise
    except (
        fitdecode.FitError,
        GPXException,
        ElementTree.ParseError,
        UnicodeDecodeError,
        ValueError,
    ) as error:
        raise ActivityFileError(f"Could not read {suffix} file: {error}") from error

    if not activities:
        raise ActivityFileError("The file contains no activities")

    return activities
