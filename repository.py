# 【修改：时长选填】每日分钟数可为空，未限制时不计算虚构的总预算。
# repository.py

from datetime import datetime, timezone

from sqlalchemy import select

from datasets import Conversation, Message, SessionLocal, Plan, Task


def datetime_to_str(value: datetime | None) -> str | None:
    """数据库中的时间按 UTC 保存，返回带时区的字符串。"""
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.isoformat()


# 【修改：按天规划】 任务序列化统一包含日期、状态、实际耗时和备注。
def task_to_dict(t):
    return {'id':t.id,'plan_id':t.plan_id,'source_task_id':t.source_task_id,'plan_date':t.plan_date.isoformat(),'title':t.title,'expected_output':t.expected_output,'estimated_minutes':t.estimated_minutes,'actual_minutes':t.actual_minutes,'position':t.position,'status':t.status,'note':t.note,'completed_at':datetime_to_str(t.completed_at)}


# 【修改：按天规划】 返回整份计划的days分组与全部tasks，方便详情展示及总进度统计。
def repository_get_plan(plan_id):
    with SessionLocal() as s:
        p=s.get(Plan,plan_id)
        if p is None:return {'ok':False,'error':'计划不存在'}
        tasks=[task_to_dict(t) for t in s.scalars(select(Task).where(Task.plan_id==plan_id).order_by(Task.position,Task.id))]
        days=[{**d,'tasks':[t for t in tasks if t['plan_date']==d['plan_date']]} for d in p.daily_budgets]
        return {'ok':True,'plan':{'id':p.id,'plan_id':p.id,'conversation_id':p.conversation_id,'group_key':p.group_key,'parent_plan_id':p.parent_plan_id,'goal':p.goal,'start_date':p.start_date.isoformat(),'end_date':p.end_date.isoformat(),'plan_date':p.start_date.isoformat(),'available_minutes':(sum(d['available_minutes'] for d in days) if all(d.get('available_minutes') is not None for d in days) else None),'days':days,'warnings':p.warnings,'status':p.status,'change_reason':p.change_reason,'created_at':datetime_to_str(p.created_at),'confirmed_at':datetime_to_str(p.confirmed_at)},'tasks':tasks}


def repository_get_execution_logs(plan_id: int) -> list[dict]:
    """读取任务当前的执行状态，不是逐次修改的历史日志。"""
    with SessionLocal() as session:
        plan = session.get(Plan, plan_id)

        if plan is None:
            raise ValueError(f"计划不存在：{plan_id}")

        tasks = session.scalars(
            select(Task)
            .where(Task.plan_id == plan_id)
            .order_by(Task.position, Task.id)
        ).all()

        return [
            {
                "task_id": task.id,
                # 【修改：按天规划】 复盘需要知道执行任务属于哪一天。
                "plan_date": task.plan_date.isoformat(),
                "title": task.title,
                "status": task.status,
                "estimated_minutes": task.estimated_minutes,
                "actual_minutes": task.actual_minutes,
                "note": task.note,
                "completed_at": datetime_to_str(task.completed_at),
            }
            for task in tasks
        ]
    
# add==================================================
def repository_save_message(
    conversation_id: str,
    role: str,
    content: str,
) -> dict:
    """保存一条用户消息或助手消息。"""

    if role not in {"user", "assistant"}:
        raise ValueError("消息角色必须是 user 或 assistant")

    if not isinstance(content, str) or not content.strip():
        raise ValueError("消息内容不能为空")

    with SessionLocal.begin() as session:
        conversation = session.get(
            Conversation,
            conversation_id,
        )

        if conversation is None:
            raise LookupError("会话不存在")

        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )

        session.add(message)
        session.flush()

        result = {
            "id": message.id,
            "conversation_id": message.conversation_id,
            "role": message.role,
            "content": message.content,
        }

    return result


def repository_get_messages(conversation_id: str) -> list[dict]:
    """读取会话中的聊天记录，按保存顺序排列。"""

    with SessionLocal() as session:
        conversation = session.get(
            Conversation,
            conversation_id,
        )

        if conversation is None:
            raise LookupError("会话不存在")

        messages = session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id)
        ).all()

        return [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
            }
            for message in messages
        ]

def repository_get_current_plans(conversation_id: str, preferred_plan_id: int | None = None) -> dict:
    """【修改：按天规划】按整份计划版本分组读取正式版与草稿。"""
    with SessionLocal() as session:
        selected = session.get(Plan, preferred_plan_id) if preferred_plan_id is not None else session.scalar(
            select(Plan).where(Plan.conversation_id == conversation_id, Plan.status.in_(["draft", "active"]))
            .order_by(Plan.id.desc()).limit(1)
        )
        if selected is None:
            return {"active_plan": None, "draft_plan": None}
        if selected.conversation_id != conversation_id or selected.status == "discarded":
            raise LookupError("计划不存在")
        ids = {
            status: session.scalar(select(Plan.id).where(
                Plan.conversation_id == conversation_id,
                Plan.group_key == selected.group_key,
                Plan.status == status,
            ).order_by(Plan.id.desc()).limit(1))
            for status in ["active", "draft"]
        }
    def load(plan_id):
        if plan_id is None:
            return None
        data = repository_get_plan(plan_id)
        if not data["ok"]:
            raise LookupError("计划不存在")
        return {**data["plan"], "tasks": data["tasks"]}
    return {status + "_plan": load(plan_id) for status, plan_id in ids.items()}
