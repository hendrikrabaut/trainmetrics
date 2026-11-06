from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from app import models
from app.routes.analytics import router as analytics_router
from app.routes.coach import router as coach_router
from app.routes.equipment import router as equipment_router
from app.routes.game import router as game_router
from app.routes.imports import router as imports_router
from app.routes.plans import router as plans_router
from app.routes.polar import router as polar_router
from app.routes.users import router as users_router
from app.routes.workouts import router as workouts_router
from app.routes.exercises import router as exercises_router
from app.routes.exercise_sets import router as exercise_sets_router
from app.routes.endurance_activities import router as endurance_activities_router
from app.routes.body_measurements import router as body_measurements_router


FRONTEND_PATH = Path(__file__).resolve().parents[2] / "frontend"

app = FastAPI(
    title="TrainMetrics API",
    description="API for personal fitness and training data",
    version="0.1.0",
)


@app.exception_handler(IntegrityError)
def handle_integrity_error(_request: Request, _error: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={
            "detail": (
                "This conflicts with existing data: a referenced item does "
                "not exist, is still in use, or must be unique"
            )
        },
    )


app.include_router(users_router)
app.include_router(workouts_router)
app.include_router(exercises_router)
app.include_router(exercise_sets_router)
app.include_router(endurance_activities_router)
app.include_router(body_measurements_router)
app.include_router(equipment_router)
app.include_router(analytics_router)
app.include_router(imports_router)
app.include_router(coach_router)
app.include_router(game_router)
app.include_router(plans_router)
app.include_router(polar_router)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok"
    }


# Mounted last, because "/" would otherwise catch the API routes.
app.mount("/", StaticFiles(directory=FRONTEND_PATH, html=True), name="frontend")
