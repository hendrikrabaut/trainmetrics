from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


workout_equipment = Table(
    "workout_equipment",
    Base.metadata,
    Column(
        "workout_id",
        ForeignKey("workouts.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "equipment_id",
        ForeignKey("equipment.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str | None] = mapped_column(String)
    brand: Mapped[str | None] = mapped_column(String)
    model: Mapped[str | None] = mapped_column(String)
    purchase_date: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="ACTIVE",
    )
    notes: Mapped[str | None] = mapped_column(String)
