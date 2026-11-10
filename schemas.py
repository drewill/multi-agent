from datetime import date, datetime, timedelta
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator





# 【修改：按天规划】 TaskDraft 必须先定义，PlanDraft 才能直接引用。
class TaskDraft(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    # 【修改：时长选填】模型指定第几天，不再预测任务耗时。
    day_number: int = Field(ge=1, le=14, strict=True)
    expected_output: str = Field(min_length=1)


class PlanDraft(BaseModel):
    goal: str
    tasks: list[TaskDraft] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)


class ReviewResult(BaseModel):
    summary: str
    observations: list[str]
    adjustment_suggestions: list[str]
    needs_replan: bool
    missing_information: list[str] = Field(default_factory=list)




class DayBudget(BaseModel):
    plan_date: date
    available_minutes: int | None = Field(default=None, gt=0, le=1440, strict=True)  # 【修改：时长选填】None表示用户未限制时长。

# 【修改：按天规划】 规范表单统一校验日期范围与每日预算，不再接收小时段。
class PlanFormRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    conversation_id:str=Field(min_length=1,max_length=32)
    goal:str=Field(min_length=1,max_length=1000)
    target_role:str=Field(min_length=1,max_length=255)
    background:str=Field(min_length=1,max_length=4000)
    job_description:str=Field(default='',max_length=12000)
    interview_date:date|None=None
    start_date:date
    end_date:date
    focus_areas:list[str]=Field(default_factory=list,max_length=10)
    days:list[DayBudget]=Field(min_length=1,max_length=14)
    
    @field_validator('goal','target_role','background','conversation_id')
    
    @classmethod
    def nonblank(cls,v):
        if not v.strip():raise ValueError('必填内容不能为空')
        return v.strip()
    
    @model_validator(mode='after')
    def dates(self):
        n=(self.end_date-self.start_date).days+1
        if not 1<=n<=14:raise ValueError('计划范围必须为1至14天')
        expected={self.start_date+timedelta(days=i) for i in range(n)}
        dates=[d.plan_date for d in self.days]
        if len(dates)!=len(set(dates)) or set(dates)!=expected:raise ValueError('每日预算须完整覆盖日期范围且不能重复')
        if self.interview_date and self.end_date>self.interview_date:raise ValueError('准备日期不能晚于面试日期')
        return self
