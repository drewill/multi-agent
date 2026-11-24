from datetime import date
from typing import Literal
from pydantic import BaseModel, Field

class DayBudget(BaseModel):
    plan_date: date
    available_minutes: int | None = Field(default=None, gt=0, le=1440, strict=True)  # 【修改：时长选填】None表示用户未限制时长。

class Owner(BaseModel):
    conversation_id: str = Field(min_length=1,max_length=32)

class StartInterview(Owner):
    plan_id: int = Field(gt=0)
    scope: Literal['completed','plan','job'] = 'completed'
    interview_type: Literal['basic','project','mixed'] = 'mixed'
    question_count: Literal[3,5,8] = 5

class AnswerInterview(Owner):
    turn_id: int = Field(gt=0)
    answer: str = Field(min_length=1,max_length=12000)

class ReplanInterview(Owner):
    days: list[DayBudget] = Field(min_length=1,max_length=14)