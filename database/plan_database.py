from datetime import date, datetime
from uuid import uuid4
from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String, Text, DateTime, JSON, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from database.init_database import Base, utc_now

class Plan(Base):
    __tablename__='daily_plans'
    __table_args__=(CheckConstraint("status IN ('draft','active','superseded','discarded')"),CheckConstraint('end_date >= start_date'),Index('uq_daily_active_group','conversation_id','group_key',unique=True,sqlite_where=text("status = 'active'")))
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    conversation_id:Mapped[str]=mapped_column(ForeignKey('conversations.id',ondelete='CASCADE'),index=True)
    group_key:Mapped[str]=mapped_column(String(64),default=lambda:uuid4().hex,index=True)
    parent_plan_id:Mapped[int|None]=mapped_column(ForeignKey('daily_plans.id',ondelete='SET NULL'),nullable=True)
    goal:Mapped[str]=mapped_column(Text)
    start_date:Mapped[date]=mapped_column(Date)
    end_date:Mapped[date]=mapped_column(Date)
    daily_budgets:Mapped[list]=mapped_column(JSON,default=list)
    warnings:Mapped[list]=mapped_column(JSON,default=list)
    status:Mapped[str]=mapped_column(String(20),default='draft')
    change_reason:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=utc_now)
    confirmed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)