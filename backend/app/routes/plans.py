from datetime import date as Date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_user_id
from app.models.training_plan import PlanSession
from app.schemas.common import RaceGoal
from app.models.plan_proposal import PlanProposal
from app.services import plans, proposals


router = APIRouter(
    prefix="/api/plans",
    tags=["plans"],
)


class PlanCreate(BaseModel):
    goal: RaceGoal | Literal["STRENGTH", "FITNESS"]
    sessions_per_week: int = Field(4, ge=2, le=7)
    weeks: int | None = Field(None, ge=2, le=30)
    start_date: Date | None = None
    race_date: Date | None = None
    weekdays: list[int] | None = None


class ScheduleUpdate(BaseModel):
    weekdays: list[int]


class SessionUpdate(BaseModel):
    date: Date | None = None
    title: str | None = Field(None, min_length=1)
    description: str | None = None
    distance: float | None = Field(None, ge=0, description="Meters")
    duration: int | None = Field(None, ge=0, description="Seconds")


class SessionCreate(BaseModel):
    date: Date
    sport: Literal["RUNNING", "CYCLING", "SWIMMING", "STRENGTH", "OTHER"]
    title: str = Field(min_length=1, max_length=100)
    description: str | None = None
    distance: float | None = Field(None, ge=0, description="Meters")
    duration: int | None = Field(None, ge=0, description="Seconds")


class ProposalCreate(BaseModel):
    goal: RaceGoal | Literal["STRENGTH", "FITNESS"]
    weekdays: list[int]
    weeks: int | None = Field(None, ge=2, le=30)
    start_date: Date | None = None
    race_date: Date | None = None
    notes: str | None = Field(None, max_length=1000)
    use_model: bool = True


class ProposalSession(BaseModel):
    date: Date
    sport: Literal["RUNNING", "CYCLING", "SWIMMING", "STRENGTH", "OTHER"]
    title: str = Field(min_length=1, max_length=100)
    description: str = ""
    distance: float | None = Field(None, ge=0)
    duration: int | None = Field(None, ge=0)
    phase: str | None = None
    source: str | None = None


class ProposalUpdate(BaseModel):
    sessions: list[ProposalSession]


def _proposal_or_404(db: Session, user_id: int) -> PlanProposal:
    proposal = db.get(PlanProposal, user_id)

    if proposal is None:
        raise HTTPException(status_code=404, detail="Er is geen voorstel")

    return proposal


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
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    plan = plans.active_plan(db, user_id)

    return plans.plan_view(db, plan) if plan else None


@router.post("/")
def create_plan(
    body: PlanCreate,
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    try:
        plan = plans.create_plan(
            db,
            user_id,
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
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    plan = _active_or_404(db, user_id)

    try:
        plans.reschedule_plan(db, plan, body.weekdays)
    except plans.PlanError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return plans.plan_view(db, plan)


@router.post("/sessions")
def create_session(
    body: SessionCreate,
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    plan = _active_or_404(db, user_id)

    try:
        plans.add_session(db, plan, body.model_dump())
    except plans.PlanError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return plans.plan_view(db, plan)


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


@router.post("/proposal")
def create_proposal(
    body: ProposalCreate,
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    """Asks for a proposal. Your planning stays as it is."""
    try:
        return proposals.create_proposal(
            db,
            user_id,
            body.goal,
            body.weekdays,
            weeks=body.weeks,
            start=body.start_date,
            race_date=body.race_date,
            notes=body.notes,
            use_model=body.use_model,
        )
    except plans.PlanError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/proposal")
def get_proposal(
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    proposal = db.get(PlanProposal, user_id)

    return proposals.proposal_view(db, proposal) if proposal else None


@router.put("/proposal")
def update_proposal(
    body: ProposalUpdate,
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    proposal = _proposal_or_404(db, user_id)
    proposals.update_sessions(db, proposal, [row.model_dump() for row in body.sessions])

    return proposals.proposal_view(db, proposal)


@router.delete("/proposal")
def discard_proposal(
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    db.delete(_proposal_or_404(db, user_id))
    db.commit()

    return {"message": "Proposal discarded"}


@router.post("/proposal/approve")
def approve_proposal(
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    """The only way a proposal gets into the planning."""
    proposal = _proposal_or_404(db, user_id)

    try:
        plan = proposals.approve(db, proposal)
    except plans.PlanError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return plans.plan_view(db, plan)
