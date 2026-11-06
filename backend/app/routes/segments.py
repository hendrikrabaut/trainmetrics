from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_user_id
from app.models.segment import Segment
from app.services import segments


router = APIRouter(
    prefix="/api/segments",
    tags=["segments"],
)


class SegmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    workout_id: int
    start: tuple[float, float]
    end: tuple[float, float]


def _segment_or_404(db: Session, segment_id: int) -> Segment:
    segment = db.get(Segment, segment_id)

    if segment is None:
        raise HTTPException(status_code=404, detail="Segment niet gevonden")

    return segment


@router.get("/")
def get_segments(
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(Segment).where(Segment.user_id == user_id).order_by(Segment.name)
    ).all()

    return [segments.segment_view(db, row, with_points=True) for row in rows]


@router.post("/")
def create_segment(
    body: SegmentCreate,
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    try:
        segment = segments.create_segment(
            db, user_id, body.workout_id, body.name, body.start, body.end
        )
    except segments.SegmentError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    return segments.segment_view(db, segment, with_points=True)


@router.delete("/{segment_id}")
def delete_segment(
    segment_id: int,
    db: Session = Depends(get_db),
):
    db.delete(_segment_or_404(db, segment_id))
    db.commit()

    return {"message": "Segment deleted successfully"}
