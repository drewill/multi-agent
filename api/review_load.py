from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from database.init_database import SessionLocal
from database.plan_database import Plan
from database.review_database import Review
router = APIRouter()
@router.get("/{plan_id}")
def list_plan_reviews(
    plan_id: int,
    conversation_id: str ,
):
    with SessionLocal() as session:
        plan = session.get(Plan, plan_id)

        if (
            plan is None
            or plan.conversation_id != conversation_id
            or plan.status == "discarded"
        ):
            raise HTTPException(status_code=404, detail="计划不存在")

        reviews = session.scalars(
            select(Review)
            .join(Plan, Review.plan_id == Plan.id)
            .where(
                Plan.conversation_id == conversation_id,
                Plan.group_key == plan.group_key,
                Plan.status != "discarded",
            )
            .order_by(Review.created_at.desc(), Review.id.desc())
        ).all()

        return {
            "reviews": [
                {
                    "id": review.id,
                    "plan_id": review.plan_id,
                    "feedback": review.feedback,
                    "result": review.result or {},
                    # 数据库存的是不带时区标记的 UTC，补上 Z 供浏览器解析。
                    "created_at": review.created_at.isoformat() + "Z",
                }
                for review in reviews
            ]
        }
    