from datetime import datetime
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Text
from database.init_database import Base, utc_now
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

class Review(Base):
    __tablename__='daily_reviews'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    plan_id:Mapped[int]=mapped_column(ForeignKey('daily_plans.id',ondelete='CASCADE'),index=True)
    feedback:Mapped[str]=mapped_column(Text)
    task_snapshot:Mapped[list]=mapped_column(JSON,default=list)
    result:Mapped[dict]=mapped_column(JSON,default=dict)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=utc_now)