from datetime import date, datetime
from uuid import uuid4
from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String, Text, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from database.init_database import Base, utc_now

class Task(Base):
    __tablename__='daily_tasks'
    __table_args__=(CheckConstraint("status IN ('pending','in_progress','completed','skipped')"),CheckConstraint('estimated_minutes > 0'),CheckConstraint('actual_minutes IS NULL OR actual_minutes >= 0'),UniqueConstraint('plan_id','position'))
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    plan_id:Mapped[int]=mapped_column(ForeignKey('daily_plans.id',ondelete='CASCADE'),index=True)
    source_task_id:Mapped[int|None]=mapped_column(ForeignKey('daily_tasks.id',ondelete='SET NULL'),nullable=True)
    plan_date:Mapped[date]=mapped_column(Date,index=True)
    title:Mapped[str]=mapped_column(String(255))
    expected_output:Mapped[str]=mapped_column(Text)
    # 【修改：时长选填】旧预计耗时仅供兼容历史，新任务存NULL。
    estimated_minutes:Mapped[int|None]=mapped_column(Integer,nullable=True)
    actual_minutes:Mapped[int|None]=mapped_column(Integer,nullable=True)
    position:Mapped[int]=mapped_column(Integer,default=0)
    status:Mapped[str]=mapped_column(String(20),default='pending')
    note:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=utc_now)
    completed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)