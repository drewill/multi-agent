
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import select
from core.time_to_str import datetime_to_str
from database.conversation_database import Conversation
from database.init_database import SessionLocal, utc_now
from database.plan_database import Plan
from database.task_database import Task
from schemas.interview_schemas import DayBudget
from schemas.planner_schemas import PlanDraft
from services.task_allocation import allocate_tasks


def repository_get_plan(plan_id):
    with SessionLocal() as s:
        p=s.get(Plan,plan_id)
        if p is None:return {'ok':False,'error':'计划不存在'}
        tasks=[task_to_dict(t) for t in s.scalars(select(Task).where(Task.plan_id==plan_id).order_by(Task.position,Task.id))]
        days=[{**d,'tasks':[t for t in tasks if t['plan_date']==d['plan_date']]} for d in p.daily_budgets]
        return {'ok':True,'plan':{'id':p.id,'plan_id':p.id,'conversation_id':p.conversation_id,'group_key':p.group_key,'parent_plan_id':p.parent_plan_id,'goal':p.goal,'start_date':p.start_date.isoformat(),'end_date':p.end_date.isoformat(),'plan_date':p.start_date.isoformat(),'available_minutes':(sum(d['available_minutes'] for d in days) if all(d.get('available_minutes') is not None for d in days) else None),'days':days,'warnings':p.warnings,'status':p.status,'change_reason':p.change_reason,'created_at':datetime_to_str(p.created_at),'confirmed_at':datetime_to_str(p.confirmed_at)},'tasks':tasks}

def task_to_dict(t):
    return {'id':t.id,'plan_id':t.plan_id,'source_task_id':t.source_task_id,'plan_date':t.plan_date.isoformat(),'title':t.title,'expected_output':t.expected_output,'estimated_minutes':t.estimated_minutes,'actual_minutes':t.actual_minutes,'position':t.position,'status':t.status,'note':t.note,'completed_at':datetime_to_str(t.completed_at)}

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
    


def validate_and_save_draft(draft,*,conversation_id,days,parent_plan_id=None,change_reason=None):
    try:
        draft=PlanDraft.model_validate(draft)

        budgets=normalize_days(days)

        if not draft.goal.strip():
            raise ValueError('目标不能为空')
        # 【修改：按天规划】保留原服务对空白任务名称、空白产出的检查。
        for task in draft.tasks:
            task.title = task.title.strip()
            task.expected_output = task.expected_output.strip()

            if not task.title or not task.expected_output:
                raise ValueError('任务名称和预期产出不能为空白')
        allocation=allocate_tasks(draft.tasks,budgets)
    except ValueError as e:
        return {'ok':False,'status':'validation_failed','errors':[str(e)]}

    warnings=list(draft.warnings)
    if any(not ts for ts in allocation):
        warnings.append('任务少于可用日期，部分日期留作巩固或休息。')

    with SessionLocal.begin() as s:
        if s.get(Conversation,conversation_id) is None:
            raise LookupError('会话不存在')
        
        group_key=uuid4().hex
        if parent_plan_id is not None:

            parent=s.get(Plan,parent_plan_id)
            if parent is None or parent.conversation_id!=conversation_id:
                raise LookupError('原计划不存在')
            if parent.status!='active':
                raise ValueError('只能基于当前正式计划调整')
            group_key=parent.group_key
        p=Plan(conversation_id=conversation_id,group_key=group_key,parent_plan_id=parent_plan_id,goal=draft.goal.strip(),start_date=budgets[0].plan_date,end_date=budgets[-1].plan_date,daily_budgets=[d.model_dump(mode='json') for d in budgets],warnings=warnings,status='draft',change_reason=change_reason)
        s.add(p);s.flush();position=0

        for day,tasks in zip(budgets,allocation):
            for t in tasks:
                s.add(Task(plan_id=p.id,plan_date=day.plan_date,title=t.title,expected_output=t.expected_output,estimated_minutes=None,position=position,status='pending'));position+=1
        response={'ok':True,'draft_plan_id':p.id,'status':'draft','total_minutes':None,'warnings':warnings}  # 【修改：时长选填】不累计预测耗时
    return response


def normalize_days(days):
    values=sorted([DayBudget.model_validate(d) if not isinstance(d,DayBudget) else d for d in days],key=lambda d:d.plan_date)
    if not 1<=len(values)<=14:
        raise ValueError('计划须为1至14天')
    if any(b.plan_date!=a.plan_date+timedelta(days=1) for a,b in zip(values,values[1:])):
        raise ValueError('每天预算须连续且不能重复')
    return values


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


def get_owned_plan(
    conversation_id: str,
    plan_id: int,
) -> dict:
    """读取完整计划，并检查所属会话。"""

    data = repository_get_plan(plan_id)

    if (
        not data.get("ok")
        or data["plan"]["conversation_id"] != conversation_id
        or data["plan"]["status"] == "discarded"
    ):
        raise LookupError("当前会话中不存在这份计划")

    return {
        **data["plan"],
        "tasks": data["tasks"],
    }

def confirm_plan(*,conversation_id,plan_id):
    with SessionLocal.begin() as s:
        p=s.get(Plan,plan_id)

        if p is None or p.conversation_id!=conversation_id:
            raise LookupError('计划不存在')

        if p.status=='active':
            return {'ok':True,'plan_id':p.id,'status':'active'}
        
        if p.status!='draft':
            raise ValueError('只有草稿可以确认')
        
        active=s.scalar(select(Plan).where(Plan.conversation_id==conversation_id,Plan.group_key==p.group_key,Plan.status=='active'))
        
        if p.parent_plan_id is not None and (active is None or active.id!=p.parent_plan_id):
            raise ValueError('原正式计划已变化，重请新生成调整草稿')
        
        if active:
            active.status='superseded'
            s.flush()
        p.status='active';p.confirmed_at=utc_now()

        for other in s.scalars(select(Plan).where(Plan.group_key==p.group_key,Plan.conversation_id==conversation_id,Plan.status=='draft',Plan.id!=p.id)):
            other.status='discarded'
        s.flush();return {'ok':True,'plan_id':p.id,'status':'active'}