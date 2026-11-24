from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from core.locks import operation_lock
from database.init_database import SessionLocal
from database.plan_database import Plan
router = APIRouter()

@router.delete('/{plan_id}')
def remove_plan(
    plan_id: int,
    conversation_id: str = Query(min_length=1, max_length=32),
):
    """逻辑删除：保留任务、复盘及版本关联，仅从列表移除。

    已删除的计划再次删除时仍返回成功。
    传入 main.py 的 operation_lock 可与聊天、确认、任务更新串行执行。
    """
    # 【修改：按天规划】 使用已有全局锁，不依赖未导入的nullcontext。
    with operation_lock:
        with SessionLocal.begin() as session:
            plan = session.get(Plan, plan_id)
            if plan is None or plan.conversation_id != conversation_id:
                raise HTTPException(status_code=404, detail='计划不存在')
            # 【新增：模拟面试】同一计划的全部版本一起从列表移除，避免旧版重新出现。
            for version in session.scalars(select(Plan).where(Plan.conversation_id == conversation_id, Plan.group_key == plan.group_key)):
                version.status = 'discarded'
        return {
            'ok': True,
            'plan_id': plan_id,
            'status': 'discarded',
            'message': '计划已移除，历史记录保留',
        }
