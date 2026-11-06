from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TrainingPlan(Base):
    __tablename__ = "training_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    goal: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[str] = mapped_column(String, nullable=False)
    end_date: Mapped[str] = mapped_column(String, nullable=False)
    race_date: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False, default="ACTIVE")
    warning: Mapped[str | None] = mapped_column(String)

    # Comma separated, 0 is Monday. Empty for plans made before this existed.
    weekdays: Mapped[str | None] = mapped_column(String)
    first_long_run: Mapped[float | None] = mapped_column(Float)

    sessions: Mapped[list["PlanSession"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="PlanSession.date",
    )


class PlanSession(Base):
    __tablename__ = "plan_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("training_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[str] = mapped_column(String, nullable=False)
    week: Mapped[int] = mapped_column(Integer, nullable=False)
    sport: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    distance: Mapped[float | None] = mapped_column(Float)
    duration: Mapped[int | None] = mapped_column(Integer)
    phase: Mapped[str | None] = mapped_column(String)

    plan: Mapped[TrainingPlan] = relationship(back_populates="sessions")
