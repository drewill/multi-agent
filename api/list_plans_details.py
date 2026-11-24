from fastapi import APIRouter, HTTPException, Query

from database.respository.plans_tasks import get_owned_plan
router = APIRouter()
@router.get('/{plan_id}')
def get_plan_detail(
    plan_id: int,
    conversation_id: str = Query(min_length=1, max_length=32),
):
    """读取指定会话中的计划及全部任务。会话 ID 不等同于登录验证。"""
    try:
        return {'plan': get_owned_plan(conversation_id, plan_id)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc