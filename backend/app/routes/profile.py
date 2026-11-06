from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate


router = APIRouter(
    prefix="/api/profile",
    tags=["profile"],
)


def _profile(db: Session) -> User | None:
    return db.scalar(select(User).order_by(User.id))


@router.get("/", response_model=UserResponse | None)
def get_profile(db: Session = Depends(get_db)):
    """Empty until the app has been set up."""
    return _profile(db)


@router.post("/", response_model=UserResponse)
def create_profile(
    user: UserCreate,
    db: Session = Depends(get_db),
):
    if _profile(db) is not None:
        raise HTTPException(status_code=409, detail="Er is al een profiel")

    new_user = User(name=user.name, email=user.email)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.patch("/", response_model=UserResponse)
def update_profile(
    user_update: UserUpdate,
    db: Session = Depends(get_db),
):
    user = _profile(db)

    if user is None:
        raise HTTPException(status_code=404, detail="Er is nog geen profiel")

    for field, value in user_update.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)

    return user
