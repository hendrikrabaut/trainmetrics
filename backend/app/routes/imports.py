import hashlib

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.endurance_activity import EnduranceActivity
from app.models.workout import Workout
from app.services.importers import ActivityFileError, parse_activity_file
from app.services.routes import store_route


MAX_FILE_BYTES = 50 * 1024 * 1024

router = APIRouter(
    prefix="/api/import",
    tags=["import"],
)


@router.post("/")
def import_activity_file(
    file: UploadFile,
    user_id: int = 1,
    db: Session = Depends(get_db),
):
    content = file.file.read(MAX_FILE_BYTES + 1)

    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="File is larger than 50 MB",
        )

    try:
        activities = parse_activity_file(file.filename or "", content)
    except ActivityFileError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    file_hash = hashlib.sha256(content).hexdigest()
    imported = []
    skipped = 0

    for index, activity in enumerate(activities):
        source_hash = f"{file_hash}:{index}"

        already_imported = db.scalar(
            select(Workout.id).where(Workout.source_hash == source_hash)
        )

        if already_imported is not None:
            skipped += 1
            continue

        workout = Workout(
            user_id=user_id,
            date=activity.date,
            duration=activity.duration,
            type="ENDURANCE",
            source_hash=source_hash,
            endurance_activity=EnduranceActivity(
                activity_type=activity.activity_type,
                distance=activity.distance,
                duration=activity.duration,
                average_speed=activity.average_speed,
                average_heart_rate=activity.average_heart_rate,
                max_heart_rate=activity.max_heart_rate,
                elevation_gain=activity.elevation_gain,
                calories=activity.calories,
            ),
        )

        db.add(workout)
        db.flush()
        store_route(db, workout.id, activity.route)
        imported.append(workout)

    db.commit()

    return {
        "imported": [
            {
                "workout_id": workout.id,
                "date": workout.date,
                "activity_type": workout.endurance_activity.activity_type,
                "distance": workout.endurance_activity.distance,
                "duration": workout.endurance_activity.duration,
            }
            for workout in imported
        ],
        "skipped": skipped,
    }
