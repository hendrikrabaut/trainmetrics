from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PolarAccount(Base):
    __tablename__ = "polar_accounts"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    polar_user_id: Mapped[str | None] = mapped_column(String)

    # Never returned by the API. Database backups do contain it.
    access_token: Mapped[str] = mapped_column(String, nullable=False)
    last_sync_at: Mapped[str | None] = mapped_column(String)
