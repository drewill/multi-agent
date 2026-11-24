from pydantic import BaseModel, Field


class ConversationRequest(BaseModel):
    title: str = Field(
        default="学习计划与复盘",
        min_length=1,
        max_length=255,
    )
