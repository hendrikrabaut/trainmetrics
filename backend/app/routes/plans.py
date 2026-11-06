from datetime import date as Date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.training_plan import PlanSession
from app.services import plans


router = APIRouter(
    prefix="/api/plans",
    tags=["plans"],
)


class PlanCreate(BaseModel):
    user_id: int = 1
    goal: Literal["5K", "10K", "HALF", "TRIATHLON", "STRENGTH", "FITNESS"]
    sessions_per_week: int = Field(4, ge=2, le=7)
    weeks: int | None = Field(None, ge=2, le=30)
    start_date: Date | None = None
    race_date: Date | None = None
    weekdays: list[int] | None = None


class ScheduleUpdate(BaseModel):
    user_id: int = 1
    weekdays: list[int]


class SessionUpdate(BaseModel):
    date: Date | None = None
    title: str | None = Field(None, min_length=1)
    description: str | None = None
    distance: float | None = Field(None, ge=0, description="Meters")
    duration: int | None = Field(None, ge=0, description="Seconds")


def _active_or_404(db: Session, user_id: int):
    plan = plans.active_plan(db, user_id)

    if plan is None:
        raise HTTPException(status_code=404, detail="Er is nog geen plan")

    return plan


def _session_or_404(db: Session, session_id: int) -> PlanSession:
    session = db.get(PlanSession, session_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Training niet gevonden")

    return session


@router.get("/active")
def get_active_plan(
    user_id: int = 1,
    db: Session = Depends(get_db),
):
    plan = plans.active_plan(db, user_id)

    return plans.plan_view(db, plan) if plan else None


@router.post("/")
def create_plan(
    body: PlanCreate,
    db: Session = Depends(get_db),
):
    try:
        plan = plans.create_plan(
            db,
            body.user_id,
            body.goal,
            body.sessions_per_week,
            weeks=body.weeks,
            start=body.start_date,
            race_date=body.race_date,
            weekdays=body.weekdays,
        )
    except plans.PlanError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return plans.plan_view(db, plan)


@router.put("/active/schedule")
def change_schedule(
    body: ScheduleUpdate,
    db: Session = Depends(get_db),
):
    plan = _active_or_404(db, body.user_id)

    try:
        plans.reschedule_plan(db, plan, body.weekdays)
    except plans.PlanError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return plans.plan_view(db, plan)


@router.get("/active/calendar.ics")
def export_calendar(
    user_id: int = 1,
    db: Session = Depends(get_db),
):
    plan = _active_or_404(db, user_id)

    return Response(
        plans.plan_to_ical(plan),
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="trainmetrics-plan.ics"',
        },
    )


@router.patch("/sessions/{session_id}")
def change_session(
    session_id: int,
    body: SessionUpdate,
    db: Session = Depends(get_db),
):
    session = _session_or_404(db, session_id)
    changes = body.model_dump(exclude_unset=True)

    if changes.get("date", session.date) is None:
        raise HTTPException(status_code=422, detail="Een training heeft een dag nodig")

    if changes.get("title", session.title) is None:
        raise HTTPException(status_code=422, detail="Een training heeft een naam nodig")

    if changes.get("description", session.description) is None:
        changes["description"] = ""

    try:
        plans.update_session(db, session, changes)
    except plans.PlanError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return plans.plan_view(db, session.plan)


@router.delete("/sessions/{session_id}")
def remove_session(
    session_id: int,
    db: Session = Depends(get_db),
):
    session = _session_or_404(db, session_id)
    plan = session.plan

    try:
        plans.delete_session(db, session)
    except plans.PlanError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return plans.plan_view(db, plan)
