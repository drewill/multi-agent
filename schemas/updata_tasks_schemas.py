from pydantic import BaseModel, Field


class TaskUpdateRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=32)

    status: str | None = None
    actual_minutes: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=2000)