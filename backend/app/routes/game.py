from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_user_id
from app.services.game import profile


router = APIRouter(
    prefix="/api/game",
    tags=["game"],
)


@router.get("/profile")
def get_profile(
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    return profile(db, user_id)
