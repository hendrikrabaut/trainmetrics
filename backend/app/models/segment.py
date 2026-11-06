from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    sport: Mapped[str] = mapped_column(String, nullable=False)
    points: Mapped[str] = mapped_column(Text, nullable=False)
    length_meters: Mapped[float] = mapped_column(Float, nullable=False)


class SegmentEffort(Base):
    __tablename__ = "segment_efforts"

    segment_id: Mapped[int] = mapped_column(
        ForeignKey("segments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    workout_id: Mapped[int] = mapped_column(
        ForeignKey("workouts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    seconds: Mapped[int] = mapped_column(Integer, nullable=False)
