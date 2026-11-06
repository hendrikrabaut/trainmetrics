"""Stores GPS routes small enough for a Raspberry Pi to serve quickly."""
import json
import math

from sqlalchemy.orm import Session

from app.models.workout_route import WorkoutRoute


# Less than this is a lost GPS signal or standing still, not a route.
MINIMUM_POINTS = 5
MINIMUM_LENGTH_METERS = 50
MAXIMUM_POINTS = 500
TOLERANCE_METERS = 4
METERS_PER_DEGREE = 111_320


def _clean(points) -> list[tuple[float, float]]:
    return [
        (latitude, longitude)
        for latitude, longitude in points
        if isinstance(latitude, (int, float))
        and isinstance(longitude, (int, float))
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
        and (latitude, longitude) != (0, 0)
    ]


def _distance_to_line(point, start, end, scale) -> float:
    """Meters from a point to a line, on a flat map, which is fine at this scale."""
    x = (point[1] - start[1]) * scale
    y = point[0] - start[0]
    dx = (end[1] - start[1]) * scale
    dy = end[0] - start[0]
    length = dx * dx + dy * dy

    if length:
        share = max(0, min(1, (x * dx + y * dy) / length))
        x -= share * dx
        y -= share * dy

    return math.hypot(x, y) * METERS_PER_DEGREE


def simplify(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Ramer-Douglas-Peucker: drops points that barely change the shape."""
    if len(points) <= 2:
        return list(points)

    scale = math.cos(math.radians(points[0][0]))
    tolerance = TOLERANCE_METERS

    while True:
        keep = {0, len(points) - 1}
        stack = [(0, len(points) - 1)]

        while stack:
            first, last = stack.pop()
            furthest = None
            largest = tolerance

            for index in range(first + 1, last):
                distance = _distance_to_line(
                    points[index], points[first], points[last], scale
                )

                if distance > largest:
                    largest = distance
                    furthest = index

            if furthest is not None:
                keep.add(furthest)
                stack += [(first, furthest), (furthest, last)]

        if len(keep) <= MAXIMUM_POINTS:
            return [points[index] for index in sorted(keep)]

        tolerance *= 1.5


def route_length(points) -> float:
    """Meters along the route, on a flat map, which is fine at this scale."""
    if not points:
        return 0.0

    scale = math.cos(math.radians(points[0][0]))

    return sum(
        math.hypot(
            (second[1] - first[1]) * scale,
            second[0] - first[0],
        )
        for first, second in zip(points, points[1:])
    ) * METERS_PER_DEGREE


def store_route(db: Session, workout_id: int, points) -> bool:
    """Keeps a route if there is one and the workout has none yet."""
    cleaned = _clean(points)

    if (
        len(cleaned) < MINIMUM_POINTS
        or route_length(cleaned) < MINIMUM_LENGTH_METERS
        or db.get(WorkoutRoute, workout_id)
    ):
        return False

    simplified = [
        [round(latitude, 5), round(longitude, 5)]
        for latitude, longitude in simplify(cleaned)
    ]

    db.add(WorkoutRoute(workout_id=workout_id, points=json.dumps(simplified)))
    db.flush()

    return True
