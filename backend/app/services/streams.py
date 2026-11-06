"""Turns measurements of one sample a second into splits, zones and best efforts.

Samples are a dict of equally long lists, one value a second, with None where
nothing was measured: heart_rate, speed (m/s), altitude and distance (meters,
counting up), latitude and longitude.
"""
import json
import math

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.workout_stream import WorkoutStream


KEPT_EVERY_SECONDS = 5

SPLIT_METERS = {"RUNNING": 1000, "CYCLING": 5000, "SWIMMING": 100, "OTHER": 1000}

BEST_EFFORT_METERS = {
    "RUNNING": [1000, 5000, 10000, 21098],
    "CYCLING": [10000, 20000, 40000],
    # No 100 m: in a pool the distance moves per length, which is too coarse.
    "SWIMMING": [400, 1000],
}

# Faster than this over a whole effort is a GPS error, not a record.
FASTEST_POSSIBLE = {"RUNNING": 7.5, "CYCLING": 22, "SWIMMING": 1.8}

# Where the distance moves on every second, a bigger jump is a GPS error.
GPS_SPORTS = {"RUNNING", "CYCLING"}

ZONE_SHARES = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

METERS_PER_DEGREE = 111_320


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None

    return None if math.isnan(value) or math.isinf(value) else value


def clean_series(values) -> list:
    return [_number(value) for value in values or []]


def _length(samples: dict) -> int:
    return max((len(values) for values in samples.values()), default=0)


def _series(samples: dict, name: str, length: int) -> list:
    values = list(samples.get(name) or [])
    return values + [None] * (length - len(values))


def _filled_distance(values: list) -> list[float] | None:
    """Distance that only counts up, without holes. None if there is no distance."""
    if not any(value for value in values):
        return None

    filled = []
    last = 0.0

    for value in values:
        if value is not None and value > last:
            last = value

        filled.append(last)

    return filled


def _crossing(distance: list[float], target: float, start: int) -> float | None:
    """The moment in seconds the distance reaches a target, between two samples."""
    for index in range(start, len(distance)):
        if distance[index] >= target:
            if index == 0:
                return 0.0

            before = distance[index - 1]
            step = distance[index] - before

            return index - 1 + ((target - before) / step if step else 1)

    return None


def _mean(values: list) -> float | None:
    known = [value for value in values if value is not None]
    return sum(known) / len(known) if known else None


def compute_splits(sport: str, samples: dict) -> list[dict]:
    length = _length(samples)
    distance = _filled_distance(_series(samples, "distance", length))
    unit = SPLIT_METERS.get(sport)

    if distance is None or unit is None or distance[-1] < unit / 2:
        return []

    heart_rate = _series(samples, "heart_rate", length)
    altitude = _series(samples, "altitude", length)
    splits = []
    previous_time = 0.0
    previous_index = 0
    number = 1

    while True:
        target = number * unit
        moment = _crossing(distance, target, previous_index)
        partial = moment is None

        if partial:
            remaining = distance[-1] - (number - 1) * unit

            # A last piece shorter than this says little about its pace.
            if remaining < unit * 0.1:
                break

            moment = float(length - 1)

        index = min(int(moment) + 1, length)
        window = range(previous_index, index)

        climbed = 0.0
        last_height = None

        for position in window:
            height = altitude[position]

            if height is not None:
                if last_height is not None and height > last_height:
                    climbed += height - last_height

                last_height = height

        rate = _mean([heart_rate[position] for position in window])
        meters = distance[-1] - (number - 1) * unit if partial else unit

        splits.append(
            {
                "number": number,
                "meters": round(meters, 1),
                "seconds": round(moment - previous_time, 1),
                "heart_rate": round(rate) if rate else None,
                "ascent": round(climbed, 1) if last_height is not None else None,
            }
        )

        if partial:
            break

        previous_time = moment
        previous_index = max(int(moment), 0)
        number += 1

    return splits


def _without_jumps(distance: list[float], limit: float) -> list[float]:
    """Replaces an impossible jump by the pace of the second before."""
    repaired = [distance[0]]
    step = 0.0

    for previous, current in zip(distance, distance[1:]):
        moved = current - previous

        if moved <= limit:
            step = moved

        repaired.append(repaired[-1] + step)

    return repaired


def compute_best_efforts(sport: str, samples: dict) -> list[dict]:
    """The fastest stretch of each distance, anywhere within the workout."""
    targets = BEST_EFFORT_METERS.get(sport)
    length = _length(samples)
    distance = _filled_distance(_series(samples, "distance", length))

    if not targets or distance is None:
        return []

    fastest_possible = FASTEST_POSSIBLE[sport]

    if sport in GPS_SPORTS:
        distance = _without_jumps(distance, fastest_possible * 2)

    efforts = []

    for meters in targets:
        if distance[-1] < meters:
            continue

        best = None
        end = 0

        for start in range(length):
            wanted = distance[start] + meters

            while end < length and distance[end] < wanted:
                end += 1

            if end >= length:
                break

            before = distance[end - 1]
            step = distance[end] - before
            moment = end - 1 + ((wanted - before) / step if step else 1)
            seconds = moment - start

            if seconds > 0 and meters / seconds <= fastest_possible:
                if best is None or seconds < best:
                    best = seconds

        if best is not None:
            efforts.append({"meters": meters, "seconds": round(best, 1)})

    return efforts


def default_zone_limits(max_heart_rate: int) -> list[float]:
    """Polar's own zones are 50-60-70-80-90-100% of the maximum heart rate."""
    return [round(max_heart_rate * share) for share in ZONE_SHARES]


def compute_zones(samples: dict, limits: list[float]) -> list[dict]:
    seconds = [0] * (len(limits) - 1)

    for rate in samples.get("heart_rate") or []:
        if rate is None or rate < limits[0]:
            continue

        for index in range(len(seconds)):
            if rate < limits[index + 1] or index == len(seconds) - 1:
                seconds[index] += 1
                break

    return [
        {"lower": limits[index], "upper": limits[index + 1], "seconds": seconds[index]}
        for index in range(len(seconds))
    ]


def _thin(values: list, digits: int | None) -> list:
    """Every kept value is the mean of its stretch, so short spikes do not stand out."""
    kept = []

    for start in range(0, len(values), KEPT_EVERY_SECONDS):
        mean = _mean(values[start : start + KEPT_EVERY_SECONDS])

        if mean is None:
            kept.append(None)
        elif digits is None:
            kept.append(round(mean))
        else:
            kept.append(round(mean, digits))

    return kept


def _thin_position(values: list) -> list:
    return [
        round(value, 5) if value is not None else None
        for value in values[:: KEPT_EVERY_SECONDS]
    ]


def thin_samples(samples: dict) -> dict:
    length = _length(samples)
    distance = _filled_distance(_series(samples, "distance", length))
    data = {}

    if any(value is not None for value in _series(samples, "heart_rate", length)):
        data["heart_rate"] = _thin(_series(samples, "heart_rate", length), None)

    if any(value is not None for value in _series(samples, "speed", length)):
        data["speed"] = _thin(_series(samples, "speed", length), 2)

    if any(value is not None for value in _series(samples, "altitude", length)):
        data["altitude"] = _thin(_series(samples, "altitude", length), 1)

    if distance is not None:
        data["distance"] = [
            round(value, 1) for value in distance[:: KEPT_EVERY_SECONDS]
        ]

    if any(value is not None for value in _series(samples, "latitude", length)):
        data["latitude"] = _thin_position(_series(samples, "latitude", length))
        data["longitude"] = _thin_position(_series(samples, "longitude", length))

    return data


def store_stream(
    db: Session,
    workout_id: int,
    user_id: int,
    sport: str,
    samples: dict,
    zones: list[dict] | None = None,
) -> bool:
    """Keeps the measurements if there are any and the workout has none yet."""
    if _length(samples) < 10 or db.get(WorkoutStream, workout_id):
        return False

    if zones is None:
        user = db.get(User, user_id)
        known = [rate for rate in samples.get("heart_rate") or [] if rate]
        maximum = (user.max_heart_rate if user else None) or max(known, default=0)
        zones = compute_zones(samples, default_zone_limits(maximum)) if maximum else []

    db.add(
        WorkoutStream(
            workout_id=workout_id,
            interval_seconds=KEPT_EVERY_SECONDS,
            data=json.dumps(thin_samples(samples)),
            splits=json.dumps(compute_splits(sport, samples)),
            zones=json.dumps(zones),
            best_efforts=json.dumps(compute_best_efforts(sport, samples)),
        )
    )
    db.flush()

    return True


def samples_from_points(points: list[dict]) -> dict:
    """Spreads measurements at irregular moments over one sample a second."""
    if len(points) < 2:
        return {}

    first = points[0]["time"]
    length = int((points[-1]["time"] - first).total_seconds()) + 1

    # Long recordings of a broken file should not fill the memory.
    if length > 48 * 3600:
        return {}

    samples = {
        name: [None] * length
        for name in ("heart_rate", "speed", "altitude", "distance", "latitude", "longitude")
    }

    for point in points:
        second = int((point["time"] - first).total_seconds())

        if 0 <= second < length:
            for name in samples:
                value = _number(point.get(name))

                if value is not None:
                    samples[name][second] = value

    # Between two measurements, the last known value still holds.
    for name, values in samples.items():
        last = None
        gap = 0

        for second, value in enumerate(values):
            if value is None and last is not None and gap < 15:
                values[second] = last
                gap += 1
            elif value is not None:
                last = value
                gap = 0

    if not any(samples["distance"]):
        samples["distance"] = _distance_from_positions(samples)

    return {name: values for name, values in samples.items() if any(v is not None for v in values)}


def _distance_from_positions(samples: dict) -> list:
    total = 0.0
    previous = None
    distance = []

    for latitude, longitude in zip(samples["latitude"], samples["longitude"]):
        if latitude is not None and longitude is not None:
            if previous is not None:
                total += flat_distance(previous, (latitude, longitude))

            previous = (latitude, longitude)

        distance.append(total if previous is not None else None)

    return distance


def flat_distance(first, second) -> float:
    """Meters between two points, on a flat map, which is fine at this scale."""
    scale = math.cos(math.radians(first[0]))

    return math.hypot(
        (second[1] - first[1]) * scale,
        second[0] - first[0],
    ) * METERS_PER_DEGREE
