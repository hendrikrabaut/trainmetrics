from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User


def get_user_id(db: Session = Depends(get_db)) -> int:
    """This app belongs to one person. The database could hold more later."""
    user_id = db.scalar(select(User.id).order_by(User.id))

    if user_id is None:
        raise HTTPException(status_code=409, detail="Maak eerst je profiel aan")

    return user_id
