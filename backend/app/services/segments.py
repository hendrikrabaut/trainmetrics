"""Own segments: a stretch of a route, and the time on it in every workout."""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.endurance_activity import EnduranceActivity
from app.models.segment import Segment, SegmentEffort
from app.models.workout import Workout
from app.models.workout_stream import WorkoutStream
from app.services.streams import flat_distance


NEAR_METERS = 60
ON_ROUTE_METERS = 100
LENGTH_TOLERANCE = 0.25
MINIMUM_LENGTH_METERS = 200
CHECKPOINTS = 12


class SegmentError(ValueError):
    """The chosen stretch cannot be a segment."""


def _track(data: dict) -> list:
    """(position in the stream, latitude, longitude, distance) of known positions."""
    distance = data.get("distance") or []

    return [
        (
            index,
            latitude,
            longitude,
            distance[index] if index < len(distance) else None,
        )
        for index, (latitude, longitude) in enumerate(
            zip(data.get("latitude") or [], data.get("longitude") or [])
        )
        if latitude is not None and longitude is not None
    ]


def _closest(track: list, point: tuple) -> int:
    return min(
        range(len(track)),
        key=lambda index: flat_distance(point, track[index][1:3]),
    )


def create_segment(
    db: Session,
    user_id: int,
    workout_id: int,
    name: str,
    start: tuple[float, float],
    end: tuple[float, float],
) -> Segment:
    stream = db.get(WorkoutStream, workout_id)
    activity = db.scalar(
        select(EnduranceActivity).where(EnduranceActivity.workout_id == workout_id)
    )

    if stream is None or activity is None:
        raise SegmentError("Deze training heeft geen metingen")

    track = _track(json.loads(stream.data))

    if len(track) < 3:
        raise SegmentError("Deze training heeft geen GPS-route")

    first = _closest(track, start)
    last = _closest(track, end)

    if first == last:
        raise SegmentError("Kies twee verschillende punten op de route")

    if first > last:
        first, last = last, first

    piece = track[first : last + 1]
    points = [[point[1], point[2]] for point in piece]
    length = sum(
        flat_distance(one, other) for one, other in zip(points, points[1:])
    )

    if length < MINIMUM_LENGTH_METERS:
        raise SegmentError(
            f"Een segment moet minstens {MINIMUM_LENGTH_METERS} m lang zijn"
        )

    segment = Segment(
        user_id=user_id,
        name=name,
        sport=activity.activity_type,
        points=json.dumps(points),
        length_meters=round(length, 1),
    )

    db.add(segment)
    db.flush()

    rows = db.execute(
        select(Workout.id, WorkoutStream)
        .join(WorkoutStream, WorkoutStream.workout_id == Workout.id)
        .join(EnduranceActivity, EnduranceActivity.workout_id == Workout.id)
        .where(
            Workout.user_id == user_id,
            EnduranceActivity.activity_type == segment.sport,
        )
    ).all()

    for other_id, other_stream in rows:
        _store_effort(db, segment, other_id, other_stream)

    db.commit()

    return segment


def _store_effort(db: Session, segment: Segment, workout_id: int, stream) -> None:
    seconds = time_on_segment(
        json.loads(segment.points),
        segment.length_meters,
        json.loads(stream.data),
        stream.interval_seconds,
    )

    if seconds is not None:
        db.add(
            SegmentEffort(
                segment_id=segment.id,
                workout_id=workout_id,
                seconds=seconds,
            )
        )


def time_on_segment(
    points: list,
    length_meters: float,
    data: dict,
    interval_seconds: int,
) -> int | None:
    """The fastest pass in the right direction, or None if it was not ridden."""
    track = _track(data)

    if len(track) < 3:
        return None

    start = points[0]
    end = points[-1]

    # A quick way out for the many workouts that never come near.
    if not any(flat_distance(start, point[1:3]) < NEAR_METERS for point in track):
        return None

    step = max(len(points) // CHECKPOINTS, 1)
    checkpoints = points[step:-1:step]
    best = None
    index = 0

    while index < len(track):
        if flat_distance(start, track[index][1:3]) >= NEAR_METERS:
            index += 1
            continue

        # The closest moment of this pass along the start.
        begin = index

        while (
            index + 1 < len(track)
            and flat_distance(start, track[index + 1][1:3]) < NEAR_METERS
        ):
            index += 1

            if (
                flat_distance(start, track[index][1:3])
                < flat_distance(start, track[begin][1:3])
            ):
                begin = index

        finish = _finish_of_pass(track, begin, end, length_meters)

        if finish is not None and _follows(track, begin, finish, checkpoints):
            seconds = (track[finish][0] - track[begin][0]) * interval_seconds

            if seconds > 0 and (best is None or seconds < best):
                best = seconds

        index += 1

    return best


def _finish_of_pass(track, begin, end, length_meters) -> int | None:
    travelled = 0.0
    finish = None
    closest = NEAR_METERS

    for index in range(begin + 1, len(track)):
        travelled += flat_distance(track[index - 1][1:3], track[index][1:3])

        if travelled > length_meters * (1 + LENGTH_TOLERANCE):
            break

        distance = flat_distance(end, track[index][1:3])

        if distance < closest:
            closest = distance
            finish = index

    if finish is None:
        return None

    covered = sum(
        flat_distance(track[index - 1][1:3], track[index][1:3])
        for index in range(begin + 1, finish + 1)
    )

    return finish if covered >= length_meters * (1 - LENGTH_TOLERANCE) else None


def _follows(track, begin, finish, checkpoints) -> bool:
    piece = [point[1:3] for point in track[begin : finish + 1]]

    return all(
        min(flat_distance(checkpoint, point) for point in piece) < ON_ROUTE_METERS
        for checkpoint in checkpoints
    )


def match_workout(db: Session, user_id: int, workout_id: int, sport: str) -> None:
    """Checks a new workout against the segments that already exist."""
    stream = db.get(WorkoutStream, workout_id)

    if stream is None:
        return

    segments = db.scalars(
        select(Segment).where(Segment.user_id == user_id, Segment.sport == sport)
    ).all()

    for segment in segments:
        if db.get(SegmentEffort, (segment.id, workout_id)) is None:
            _store_effort(db, segment, workout_id, stream)

    db.flush()


def segment_view(db: Session, segment: Segment, with_points: bool = False) -> dict:
    efforts = db.execute(
        select(SegmentEffort.seconds, Workout.id, Workout.date)
        .join(Workout, Workout.id == SegmentEffort.workout_id)
        .where(SegmentEffort.segment_id == segment.id)
        .order_by(SegmentEffort.seconds)
    ).all()

    view = {
        "id": segment.id,
        "name": segment.name,
        "sport": segment.sport,
        "length_meters": segment.length_meters,
        "count": len(efforts),
        "best_seconds": efforts[0][0] if efforts else None,
        "efforts": [
            {"seconds": seconds, "workout_id": workout_id, "date": date[:10]}
            for seconds, workout_id, date in efforts
        ],
    }

    if with_points:
        view["points"] = json.loads(segment.points)

    return view
