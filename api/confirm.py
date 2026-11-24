from sqlite3 import IntegrityError
from api.conversation import require_conversation
from database.respository.plans_tasks import confirm_plan, repository_get_current_plans
from schemas.confirm_schemas import ConfirmPlanRequest
from fastapi import APIRouter, HTTPException 
from core.locks import operation_lock
router = APIRouter()



@router.post("/{plan_id}")
def confirm_plan_api(
    plan_id: int,
    body: ConfirmPlanRequest,
):
    require_conversation(body.conversation_id)

    try:
        with operation_lock:
            confirm_plan(
                conversation_id=body.conversation_id,
                plan_id=plan_id,
            )

            # 【修改：按天规划】 草稿停用已在confirm_plan中按group_key事务处理。

            return {
                "answer": "计划已确认，可以开始记录完成情况。",
                **repository_get_current_plans(
                    body.conversation_id,
                    plan_id,
                ),
            }

    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc

    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

    except IntegrityError as exc:
        raise HTTPException(
            409,
            "计划状态发生冲突，请刷新后重试",
        ) from exc

