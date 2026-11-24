from pydantic import BaseModel, Field


class ConfirmPlanRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=32)