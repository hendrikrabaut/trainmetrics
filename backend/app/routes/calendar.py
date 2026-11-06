from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_user_id
from app.services import plans


router = APIRouter(tags=["calendar"])


@router.get("/api/calendar.ics")
def calendar_subscription(
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    """The address a calendar app subscribes to. It always shows the current plan."""
    return Response(
        plans.plan_to_ical(plans.active_plan(db, user_id)),
        media_type="text/calendar; charset=utf-8",
        headers={"Cache-Control": "no-cache"},
    )
