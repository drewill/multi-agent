from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text

from database.init_database import Base,utc_now
from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy import String,DateTime
from datetime import datetime


class AgentEvent(Base):
    __tablename__ = "agent_events"

    __table_args__ = (
        CheckConstraint(
            "agent_name IN ('coordinator', 'planner', 'reviewer')",
            name="ck_agent_events_agent",
        ),
        CheckConstraint(
            "event_type IN "
            "('started', 'tool_called', 'completed', 'failed')",
            name="ck_agent_events_type",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_agent_events_duration",
        ),
        Index(
            "ix_agent_events_conversation_id_id",
            "conversation_id",
            "id",
        ),
        Index(
            "ix_agent_events_run_id_id",
            "run_id",
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

    # 一次用户请求对应一个 run_id，
    # 同一次请求中的多个事件共用这个 ID。
    run_id: Mapped[str] = mapped_column(String(32))

    agent_name: Mapped[str] = mapped_column(String(30))

    event_type: Mapped[str] = mapped_column(String(30))

    summary: Mapped[str] = mapped_column(Text)

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )

