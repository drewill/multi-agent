from pydantic import BaseModel, Field

class ReviewResult(BaseModel):
    summary: str
    observations: list[str]
    adjustment_suggestions: list[str]
    needs_replan: bool
    missing_information: list[str] = Field(default_factory=list)

class ReviewRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=32)
    plan_id: int = Field(gt=0)
    feedback: str = Field(min_length=1, max_length=4000)