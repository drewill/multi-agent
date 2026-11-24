from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    # 【修改：按天规划】 可选地指定当前打开的整份计划。
    plan_id: int | None = Field(default=None, gt=0)
    conversation_id: str = Field(min_length=1, max_length=32)
    question: str = Field(min_length=1, max_length=4000)