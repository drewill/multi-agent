from uuid import uuid4
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from database.conversation_database import Conversation
from database.init_database import SessionLocal
from database.plan_database import Plan
from database.respository.events import get_events
from schemas.conversation_schemas import ConversationRequest
from database.review_database import Review
from database.respository.messages import repository_get_messages
from database.respository.plans_tasks import repository_get_current_plans


router = APIRouter()

def require_conversation(conversation_id: str):
    with SessionLocal() as session:
        conversation = session.get(
            Conversation,
            conversation_id,
        )

        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="会话不存在",
            )

@router.post("/")
def create_conversation(body: ConversationRequest):
    conversation_id = uuid4().hex

    with SessionLocal.begin() as session:
        session.add(
            Conversation(
                id=conversation_id,
                title=body.title,
            )
        )

    return {
        "id": conversation_id,
        "title": body.title,
    }


@router.get("/{conversation_id}")
def get_conversation(conversation_id: str):
    require_conversation(conversation_id)

    with SessionLocal() as session:
        latest_review = session.scalar(
            select(Review)
            .join(Plan, Review.plan_id == Plan.id)
            .where(Plan.conversation_id == conversation_id)
            .order_by(Review.id.desc())
            .limit(1)
        )

        review_data = (
            latest_review.result
            if latest_review is not None else None
        )

    return {
        "id": conversation_id,
        "messages": repository_get_messages(conversation_id),
        **repository_get_current_plans(conversation_id),
        "events": get_events(conversation_id),
        "latest_review": review_data,
    }
