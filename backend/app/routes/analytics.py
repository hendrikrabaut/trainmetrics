from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_user_id
from app.services import analytics
from app.services.estimates import estimates
from app.services.insights import (
    best_efforts,
    performance_chart,
    year_review,
    zone_summary,
)
from app.services.sleep import sleep_summary
from app.services.sports import sport_breakdown


router = APIRouter(
    prefix="/api/analytics",
    tags=["analytics"],
)


@router.get("/weekly")
def get_weekly_summary(
    user_id: int = Depends(get_user_id),
    weeks: int = Query(12, ge=1, le=104),
    db: Session = Depends(get_db),
):
    return analytics.weekly_summary(db, user_id, weeks)


@router.get("/exercises/{exercise_id}/progress")
def get_exercise_progress(
    exercise_id: int,
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    return analytics.exercise_progress(db, user_id, exercise_id)


@router.get("/records")
def get_personal_records(
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    return analytics.personal_records(db, user_id)


@router.get("/body-weight")
def get_body_weight(
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    return analytics.body_weight_history(db, user_id)


@router.get("/estimates")
def get_estimates(
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    return estimates(db, user_id)


@router.get("/sports")
def get_sport_breakdown(
    user_id: int = Depends(get_user_id),
    days: int | None = Query(None, ge=1, le=3650),
    db: Session = Depends(get_db),
):
    """Totals per sport, for the last number of days or for all time."""
    return sport_breakdown(db, user_id, days)


@router.get("/sleep")
def get_sleep(
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    return sleep_summary(db, user_id)


@router.get("/zones")
def get_zones(
    weeks: int = Query(12, ge=1, le=104),
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    return zone_summary(db, user_id, weeks)


@router.get("/best-efforts")
def get_best_efforts(
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    return best_efforts(db, user_id)


@router.get("/performance")
def get_performance(
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    return performance_chart(db, user_id)


@router.get("/year/{year}")
def get_year(
    year: int,
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    return year_review(db, user_id, year)
