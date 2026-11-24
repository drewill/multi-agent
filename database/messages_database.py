from datetime import datetime
from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from database.init_database import Base, utc_now


class Message(Base):
    __tablename__ = "messages"

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_messages_role",
        ),
        Index(
            "ix_messages_conversation_id_id",
            "conversation_id",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
    )

    role: Mapped[str] = mapped_column(String(20))

    content: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )
