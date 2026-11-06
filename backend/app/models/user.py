from sqlalchemy import Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    max_heart_rate: Mapped[int | None] = mapped_column(Integer)
    resting_heart_rate: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
