from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_user_id
from app.services import coach


router = APIRouter(
    prefix="/api/coach",
    tags=["coach"],
)


class CoachQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class CoachAnswer(BaseModel):
    answer: str


@router.post("/ask", response_model=CoachAnswer)
def ask_coach(
    body: CoachQuestion,
    user_id: int = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    try:
        return CoachAnswer(answer=coach.ask(db, user_id, body.question))
    except coach.CoachUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "De coach is niet bereikbaar. Staat de laptop aan en draait "
                f"Ollama? ({error})"
            ),
        ) from error
