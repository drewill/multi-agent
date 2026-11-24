from uuid import uuid4
from database.init_database import Base,utc_now
from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy import String,DateTime
from datetime import datetime


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=lambda: uuid4().hex,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        default="新的学习会话",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )
