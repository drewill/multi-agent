from fastapi import APIRouter, HTTPException

from api.conversation import require_conversation
from database.init_database import SessionLocal, utc_now
from database.plan_database import Plan
from database.respository.plans_tasks import task_to_dict
from database.task_database import Task
from schemas.updata_tasks_schemas import TaskUpdateRequest
from core.locks import operation_lock
router = APIRouter()
@router.patch("/{task_id}")
def update_task(
    task_id: int,
    body: TaskUpdateRequest,
):
    require_conversation(body.conversation_id)

    fields = body.model_fields_set

    if "status" in fields and body.status not in {
        "pending",
        "in_progress",
        "completed",
        "skipped",
    }:
        raise HTTPException(400, "不支持的任务状态")

    with operation_lock:
        with SessionLocal.begin() as session:
            task = session.get(Task, task_id)

            if task is None:
                raise HTTPException(404, "任务不存在")

            plan = session.get(Plan, task.plan_id)

            if (
                plan is None
                or plan.conversation_id != body.conversation_id
            ):
                raise HTTPException(404, "任务不存在")

            if plan.status != "active":
                raise HTTPException(
                    409,
                    "只能修改当前正式计划中的任务",
                )

            # 只修改请求实际传来的字段。
            if "status" in fields:
                if body.status == "completed":
                    if task.status != "completed":
                        task.completed_at = utc_now()
                else:
                    task.completed_at = None

                task.status = body.status

            if "actual_minutes" in fields:
                task.actual_minutes = body.actual_minutes

            if "note" in fields:
                task.note = body.note

            session.flush()
            data = task_to_dict(task)

    # 勾选只更新数据库，不调用复盘Agent。
    return {
        "task": data,
    }

