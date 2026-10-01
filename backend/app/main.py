from fastapi import FastAPI

from app import models
from app.routes.workouts import router as workouts_router
from app.routes.exercises import router as exercises_router
from app.routes.exercise_sets import router as exercise_sets_router
from app.routes.endurance_activities import router as endurance_activities_router
from app.routes.body_measurements import router as body_measurements_router


app = FastAPI(
    title="TrainMetrics API",
    description="API for personal fitness and training data",
    version="0.1.0",
)


app.include_router(workouts_router)
app.include_router(exercises_router)
app.include_router(exercise_sets_router)
app.include_router(endurance_activities_router)
app.include_router(body_measurements_router)

@app.get("/")
def root():
    return {
        "message": "Welcome to TrainMetrics API"
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "ok"
    }