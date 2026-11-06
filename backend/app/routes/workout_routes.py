import json
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_user_id
from app.models.endurance_activity import EnduranceActivity
from app.models.workout import Workout
from app.models.segment import Segment, SegmentEffort
from app.models.workout_route import WorkoutRoute
from app.models.workout_stream import WorkoutStream
from app.services.analytics import parse_day


router = APIRouter(
    prefix="/api",
    tags=["routes"],
)


@router.get("/workouts/{workout_id}/route")
def get_route(
    workout_id: int,
    db: Session = Depends(get_db),
):
    route = db.get(WorkoutRoute, workout_id)

    if route is None:
        raise HTTPException(status_code=404, detail="Deze training heeft geen route")

    return {"workout_id": workout_id, "points": json.loads(route.points)}


@router.get("/workouts/{workout_id}/detail")
def get_workout_detail(
    workout_id: int,
    db: Session = Depends(get_db),
):
    """Measurements during a workout. Empty lists if it has none."""
    stream = db.get(WorkoutStream, workout_id)

    efforts = db.execute(
        select(Segment.id, Segment.name, SegmentEffort.seconds)
        .join(SegmentEffort, SegmentEffort.segment_id == Segment.id)
        .where(SegmentEffort.workout_id == workout_id)
        .order_by(Segment.name)
    ).all()

    return {
        "workout_id": workout_id,
        "interval_seconds": stream.interval_seconds if stream else None,
        "series": json.loads(stream.data) if stream else {},
        "splits": json.loads(stream.splits) if stream else [],
        "zones": json.loads(stream.zones) if stream else [],
        "best_efforts": json.loads(stream.best_efforts) if stream else [],
        "segments": [
            {"id": segment_id, "name": name, "seconds": seconds}
            for segment_id, name, seconds in efforts
        ],
    }


@router.get("/routes")
def get_routes(
    user_id: int = Depends(get_user_id),
    sport: Literal["RUNNING", "CYCLING", "SWIMMING", "OTHER"] | None = None,
    days: int | None = Query(None, ge=1, le=3650),
    db: Session = Depends(get_db),
):
    statement = (
        select(
            Workout.id,
            Workout.date,
            EnduranceActivity.activity_type,
            WorkoutRoute.points,
        )
        .join(WorkoutRoute, WorkoutRoute.workout_id == Workout.id)
        .join(EnduranceActivity, EnduranceActivity.workout_id == Workout.id)
        .where(Workout.user_id == user_id)
        .order_by(Workout.date)
    )

    if sport:
        statement = statement.where(EnduranceActivity.activity_type == sport)

    cutoff = date.today() - timedelta(days=days) if days else None

    return [
        {
            "workout_id": workout_id,
            "date": workout_date,
            "sport": activity_type,
            "points": json.loads(points),
        }
        for workout_id, workout_date, activity_type, points in db.execute(statement)
        if cutoff is None or parse_day(workout_date) > cutoff
    ]
