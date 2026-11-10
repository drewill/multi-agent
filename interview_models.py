"""【新增：模拟面试】独立面试、问答与报告表，不复用协调Agent检查点。"""
from datetime import datetime
from sqlalchemy import ForeignKey, Integer, String, Text, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from datasets import Base, utc_now

class InterviewSession(Base):
    __tablename__ = 'interview_sessions'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey('daily_plans.id', ondelete='CASCADE'), index=True)
    scope: Mapped[str] = mapped_column(String(20))
    interview_type: Mapped[str] = mapped_column(String(20))
    question_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default='active')
    context: Mapped[dict] = mapped_column(JSON)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

class InterviewTurn(Base):
    __tablename__ = 'interview_turns'
    __table_args__ = (UniqueConstraint('session_id','position'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('interview_sessions.id', ondelete='CASCADE'), index=True)
    position: Mapped[int] = mapped_column(Integer)
    question_number: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)

class InterviewReport(Base):
    __tablename__ = 'interview_reports'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey('interview_sessions.id', ondelete='CASCADE'), unique=True)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
