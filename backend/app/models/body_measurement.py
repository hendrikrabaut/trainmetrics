from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BodyMeasurement(Base):
    __tablename__ = "body_measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    date: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    weight: Mapped[float | None] = mapped_column(Float)
    body_fat: Mapped[float | None] = mapped_column(Float)
    waist: Mapped[float | None] = mapped_column(Float)
    chest: Mapped[float | None] = mapped_column(Float)

    notes: Mapped[str | None] = mapped_column(String)