from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SleepNight(Base):
    __tablename__ = "sleep_nights"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    night: Mapped[str] = mapped_column(String, primary_key=True)

    sleep_start: Mapped[str | None] = mapped_column(String)
    sleep_end: Mapped[str | None] = mapped_column(String)
    asleep_seconds: Mapped[int | None] = mapped_column(Integer)
    light_seconds: Mapped[int | None] = mapped_column(Integer)
    deep_seconds: Mapped[int | None] = mapped_column(Integer)
    rem_seconds: Mapped[int | None] = mapped_column(Integer)
    interruption_seconds: Mapped[int | None] = mapped_column(Integer)
    continuity: Mapped[float | None] = mapped_column(Float)
    sleep_score: Mapped[float | None] = mapped_column(Float)

    # From Nightly Recharge: heart rate variability, heart rate, breaths a minute.
    hrv_ms: Mapped[float | None] = mapped_column(Float)
    heart_rate: Mapped[float | None] = mapped_column(Float)
    breathing_rate: Mapped[float | None] = mapped_column(Float)

    # Polar's own verdict, from 1 (very poor) to 6 (very good). Only the API has
    # it, for the last 28 days, so nights from the data export have none.
    recharge_status: Mapped[int | None] = mapped_column(Integer)
    ans_charge: Mapped[float | None] = mapped_column(Float)
