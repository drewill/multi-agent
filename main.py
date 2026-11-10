# 【修改：时长选填】每日分钟数可为空，未限制时不计算虚构的总预算。
from __future__ import annotations

import json
import logging

from contextlib import asynccontextmanager
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from threading import Lock
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from langchain.agents import create_agent
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from queue import Queue, Empty
from threading import Thread
from fastapi.responses import StreamingResponse

from agents.coordinator import execute_chat, get_events, get_owned_plan, get_plan_view, task_to_dict
from datasets import (
    init_database,
    SessionLocal,
    Conversation,
    Plan,
    Task,
    Review,
    AgentEvent,
    utc_now,
)
from model_config import model
from repository import (
    repository_save_message,
    repository_get_messages,
    repository_get_plan,
)
from agents.planner import planner_agent
from agents.revs import reviewer
from agents.plan_service import (
    validate_and_save_draft,
    confirm_plan,
)


# ============================================================
# 1. 基础配置
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
BEIJING = timezone(timedelta(hours=8))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

memory = InMemorySaver()

# 本地原型串行处理修改与模型请求，避免同时修改计划。
# 请使用单个 Uvicorn worker。
operation_lock = Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield


app = FastAPI(
    title="学习计划与复盘助手",
    lifespan=lifespan,
)


# ============================================================
# 2. 请求数据结构
# ============================================================

class ConversationRequest(BaseModel):
    title: str = Field(
        default="学习计划与复盘",
        min_length=1,
        max_length=255,
    )


class ChatRequest(BaseModel):
    # 【修改：按天规划】 可选地指定当前打开的整份计划。
    plan_id: int | None = Field(default=None, gt=0)
    conversation_id: str = Field(min_length=1, max_length=32)
    question: str = Field(min_length=1, max_length=4000)


class ConfirmPlanRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=32)


class TaskUpdateRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=32)

    status: str | None = None
    actual_minutes: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=2000)


class ReviewRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=32)
    plan_id: int = Field(gt=0)
    feedback: str = Field(min_length=1, max_length=4000)





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







# ============================================================
# 6. 页面
# ============================================================

@app.get("/")
def homepage():
    return FileResponse(
        BASE_DIR / "static" / "index3.html",
        media_type="text/html",
        # 【修改：按天规划】开发时避免旧页面缓存掩盖新表单。
        headers={"Cache-Control": "no-store"},
    )


# ============================================================
# 7. 会话接口
# ============================================================

@app.post("/api/conversations")
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


@app.get("/api/conversations/{conversation_id}")
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
        **get_plan_view(conversation_id),
        "events": get_events(conversation_id),
        "latest_review": review_data,
    }


@app.get("/api/conversations/{conversation_id}/events")
def list_events(conversation_id: str):
    require_conversation(conversation_id)

    return {
        "events": get_events(conversation_id),
    }


# ============================================================
# 8. 聊天接口
# ============================================================

@app.post("/api/chat")
def chat(body: ChatRequest):
    question = body.question.strip()

    if not question:
        raise HTTPException(400, "问题不能为空")

    require_conversation(body.conversation_id)

    try:
        with operation_lock:
            return execute_chat(
                body.conversation_id,
                question,
                plan_id=body.plan_id,  # 【修改：按天规划】避免聊天误取其他计划。
            )

    except Exception as exc:
        logger.exception("聊天处理失败")

        raise HTTPException(
            status_code=500,
            detail="助手处理失败，请查看后端日志",
        ) from exc


# 【新增：流式聊天】使用POST请求接收问题，以SSE格式返回事件。
@app.post("/api/chat/stream")
def chat_stream(body: ChatRequest):

    question = body.question.strip()

    if not question:
        raise HTTPException(400, "问题不能为空")

    require_conversation(body.conversation_id)

    events = Queue()

    def emit(event: str, data: dict):
        events.put((event, data))

    def run_agent():
        try:
            emit("status", {
                "message": "请求已收到，正在等待处理…"
            })

            # 沿用当前项目的锁，不在这一步同时修改并发架构。
            with operation_lock:
                result = execute_chat(
                    body.conversation_id,
                    question,
                    plan_id=body.plan_id,
                    emit=emit,
                )

            # 最终完整结果包含回答和计划，前端据此同步页面。
            emit("result", result)
            emit("done", {})

        except Exception:
            logger.exception("流式聊天失败")

            emit("error", {
                "message": "本次回复未完成，请稍后重试。"
            })

        finally:
            events.put(None)

    def generate():
        Thread(
            target=run_agent,
            daemon=True,
        ).start()

        while True:
            try:
                item = events.get(timeout=15)
            except Empty:
                # 心跳，避免长时间执行工具时连接完全没有数据。
                yield ": ping\n\n"
                continue

            if item is None:
                break

            event, data = item

            yield (
                f"event: {event}\n"
                f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

# ============================================================
# 9. 确认计划接口
# ============================================================

@app.post("/api/plans/{plan_id}/confirm")
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
                **get_plan_view(
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


# ============================================================
# 10. 更新任务
# ============================================================

@app.patch("/api/tasks/{task_id}")
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


# ============================================================
# 11. 复盘接口
# ============================================================

@app.post("/api/reviews")
def review_plan(body: ReviewRequest):
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
            result = execute_chat(
                body.conversation_id,
                (
                    f"请调用复盘工具，复盘已确认计划 #{body.plan_id}。\n"
                    f"我的执行反馈：{feedback}\n"
                    "如果需要调整且时间条件明确，请生成调整草稿；"
                    "条件不明确时先追问，不自行假定剩余时间。"
                ),
                plan_id=body.plan_id,  # 【修改：按天规划】复盘绑定用户打开的这份计划。
            )

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

"""补充“所有计划列表”和“单份计划详情”接口。

将本文件放在 main.py 同级目录，在 main.py 的 app 创建之后添加：

    from plan_api_routes import register_plan_routes
    register_plan_routes(app, SessionLocal, Plan, get_owned_plan)

这些对象在此前的 main.py 中均已导入。
适用于当前本地单用户原型；多人使用前应按登录用户过滤计划。
"""
from fastapi import HTTPException, Query
from sqlalchemy import select


#def register_plan_routes(app, SessionLocal, Plan, get_owned_plan):
@app.get('/api/plans')
def list_plans():
    """读取本地数据库中全部会话的计划，最新的排在前面。"""
    with SessionLocal() as session:
        plans = session.scalars(
            # 【修改：按天规划】删除的计划不能继续出现在列表。
            select(Plan).where(Plan.status != "discarded").order_by(Plan.id.desc())
        ).all()
        # 【新增：模拟面试】列表每个计划分组只显示一个入口；版本在详情查看。
        grouped = {}
        for item in plans:
            key = (item.conversation_id, item.group_key)
            existing = grouped.get(key)
            if existing is None or (item.status == 'active' and existing.status != 'active'):
                grouped[key] = item
        plans = list(grouped.values())
        return {'list': [
            {
                'plan_id': plan.id,
                'conversation_id': plan.conversation_id,
                'goal': plan.goal,
                # 【修改：按天规划】显示日期范围与整份计划预算。
                'start_date': plan.start_date.isoformat(),
                'end_date': plan.end_date.isoformat(),
                'plan_date': plan.start_date.isoformat(),
                'available_minutes': (sum(day['available_minutes'] for day in plan.daily_budgets) if all(day.get('available_minutes') is not None for day in plan.daily_budgets) else None),  # 【修改：时长选填】未限制时不伪造总预算。
                'status': plan.status,
            }
            for plan in plans
        ]}

@app.get('/api/plans/{plan_id}')
def get_plan_detail(
    plan_id: int,
    conversation_id: str = Query(min_length=1, max_length=32),
):
    """读取指定会话中的计划及全部任务。会话 ID 不等同于登录验证。"""
    try:
        return {'plan': get_owned_plan(conversation_id, plan_id)}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc






@app.delete('/api/plans/{plan_id}')
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

# 【修改：按天规划】补齐规范表单的POST接口；保留你已内联的列表/详情/删除接口。
from plan_form_routes import register_plan_form_routes
register_plan_form_routes(
    app,
    planner_agent=planner_agent,
    validate_and_save_draft=validate_and_save_draft,
    get_plan_view=get_plan_view,
    repository_save_message=repository_save_message,
    operation_lock=operation_lock,
)

# 【新增：模拟面试】模块导入会注册三张新表；lifespan中的create_all自动建表。
from interview_routes import register_interview_routes
register_interview_routes(app, operation_lock)
