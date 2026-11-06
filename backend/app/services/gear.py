"""How far each piece of gear has been used.

A workout counts for gear linked to it. A workout with no gear of its sport
linked counts for the default gear of that sport, from its purchase date on.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.endurance_activity import EnduranceActivity
from app.models.equipment import Equipment, workout_equipment
from app.models.workout import Workout


def gear_usage(db: Session, user_id: int) -> list[dict]:
    gear = db.scalars(
        select(Equipment)
        .where(Equipment.user_id == user_id)
        .order_by(Equipment.status, Equipment.name)
    ).all()

    sports = {item.id: item.sport for item in gear}

    linked: dict[int, set[int]] = {}
    linked_sports: dict[int, set[str]] = {}

    for workout_id, equipment_id in db.execute(select(workout_equipment)).all():
        linked.setdefault(equipment_id, set()).add(workout_id)

        if sports.get(equipment_id):
            linked_sports.setdefault(workout_id, set()).add(sports[equipment_id])

    activities = db.execute(
        select(
            Workout.id,
            Workout.date,
            EnduranceActivity.activity_type,
            EnduranceActivity.distance,
            EnduranceActivity.duration,
        )
        .join(EnduranceActivity, EnduranceActivity.workout_id == Workout.id)
        .where(Workout.user_id == user_id)
    ).all()

    views = []

    for item in gear:
        meters = 0.0
        seconds = 0
        sessions = 0
        own = linked.get(item.id, set())

        for workout_id, date, sport, distance, duration in activities:
            by_default = (
                item.is_default
                and item.sport == sport
                and sport not in linked_sports.get(workout_id, set())
                and (not item.purchase_date or date[:10] >= item.purchase_date[:10])
            )

            if workout_id in own or by_default:
                meters += distance or 0
                seconds += duration or 0
                sessions += 1

        kilometers = round(meters / 1000, 1)
        limit = item.replace_after_km

        views.append(
            {
                "id": item.id,
                "name": item.name,
                "category": item.category,
                "brand": item.brand,
                "model": item.model,
                "purchase_date": item.purchase_date,
                "status": item.status,
                "notes": item.notes,
                "sport": item.sport,
                "is_default": item.is_default,
                "replace_after_km": limit,
                "kilometers": kilometers,
                "seconds": seconds,
                "sessions": sessions,
                "needs_replacing": bool(
                    limit and kilometers >= limit and item.status == "ACTIVE"
                ),
                "linked_workout_ids": sorted(own),
            }
        )

    return views
