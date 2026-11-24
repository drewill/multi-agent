from datetime import date
from typing import Literal
from pydantic import BaseModel, Field


class TaskDraft(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    # 【修改：时长选填】模型指定第几天，不再预测任务耗时。
    day_number: int = Field(ge=1, le=14, strict=True)
    expected_output: str = Field(min_length=1)

class PlanDraft(BaseModel):
    goal: str
    tasks: list[TaskDraft] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)


