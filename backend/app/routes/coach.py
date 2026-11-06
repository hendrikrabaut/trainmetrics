from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import coach


router = APIRouter(
    prefix="/api/coach",
    tags=["coach"],
)


class CoachQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    user_id: int = 1


class CoachAnswer(BaseModel):
    answer: str


@router.post("/ask", response_model=CoachAnswer)
def ask_coach(
    body: CoachQuestion,
    db: Session = Depends(get_db),
):
    try:
        return CoachAnswer(answer=coach.ask(db, body.user_id, body.question))
    except coach.CoachUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "De coach is niet bereikbaar. Staat de laptop aan en draait "
                f"Ollama? ({error})"
            ),
        ) from error
