from uuid import uuid4
from fastapi import APIRouter, HTTPException
from api.conversation import require_conversation
from core.locks import operation_lock
from database.respository.plans_tasks import get_owned_plan
from schemas.review_schemas import ReviewRequest
from services.review_service import execute_review
router = APIRouter()
import logging

logger = logging.getLogger(__name__)

@router.post("/")
def review_plan(body: ReviewRequest):
    result={}
    require_conversation(body.conversation_id)

    feedback = body.feedback.strip()

    if not feedback:
        raise HTTPException(400, "复盘反馈不能为空")

    try:
        with operation_lock:
            # 先检查归属，防止把无效ID交给模型。
            plan = get_owned_plan(
                body.conversation_id,
                body.plan_id,
            )

            if plan["status"] != "active":
                raise ValueError("请先确认计划，再进行复盘")

            # 让协调Agent处理复盘，并视条件决定是否重新规划。
            results = execute_review(
                body.conversation_id,
                uuid4().hex,
                body.plan_id,
                feedback,
            )
            # result = execute_chat(
            #     body.conversation_id,
            #     (
            #         f"请调用复盘工具，复盘已确认计划 #{body.plan_id}。\n"
            #         f"我的执行反馈：{feedback}\n"
            #         "如果需要调整且时间条件明确，请生成调整草稿；"
            #         "条件不明确时先追问，不自行假定剩余时间。"
            #     ),
            #     plan_id=body.plan_id,  # 【修改：按天规划】复盘绑定用户打开的这份计划。
            # )
            result["review"] = results
            if result["review"] is None:
                raise ValueError("未产生复盘结果，请重试")

            return result

    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc

    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

    except Exception as exc:
        logger.exception("复盘失败")

        raise HTTPException(
            500,
            "复盘处理失败，请查看后端日志",
        ) from exc