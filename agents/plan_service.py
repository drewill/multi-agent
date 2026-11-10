# plan_service.py
from datetime import date, datetime, timezone

from schemas import PlanDraft, DayBudget
# 【修改：时长选填】按模型提供的day_number分组，分钟数不参与硬性分配。
from task_allocation import allocate_tasks
from uuid import uuid4
from datetime import timedelta
from datasets import (
    SessionLocal,
    Conversation,
    Plan,
    Task,
)


def to_utc(value: datetime) -> datetime:
    """将带时区的时间转换为不带时区标记的 UTC 时间。"""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            "时间必须包含时区，例如 2026-11-07T09:00:00+08:00"
        )

    return value.astimezone(timezone.utc).replace(tzinfo=None)


# 【修改：按天规划】 新增每日预算规范化函数。
def normalize_days(days):
    values=sorted([DayBudget.model_validate(d) if not isinstance(d,DayBudget) else d for d in days],key=lambda d:d.plan_date)
    if not 1<=len(values)<=14:raise ValueError('计划须为1至14天')
    if any(b.plan_date!=a.plan_date+timedelta(days=1) for a,b in zip(values,values[1:])):raise ValueError('每天预算须连续且不能重复')
    return values


# 【修改：按天规划】 使用用户已改好的days参数，完整替换遗留的小时段校验和写库逻辑。
def validate_and_save_draft(draft,*,conversation_id,days,parent_plan_id=None,change_reason=None):
    try:
        draft=PlanDraft.model_validate(draft);budgets=normalize_days(days)
        if not draft.goal.strip():raise ValueError('目标不能为空')
        # 【修改：按天规划】保留原服务对空白任务名称、空白产出的检查。
        for task in draft.tasks:
            task.title = task.title.strip()
            task.expected_output = task.expected_output.strip()
            if not task.title or not task.expected_output:
                raise ValueError('任务名称和预期产出不能为空白')
        allocation=allocate_tasks(draft.tasks,budgets)
    except ValueError as e:return {'ok':False,'status':'validation_failed','errors':[str(e)]}
    warnings=list(draft.warnings)
    if any(not ts for ts in allocation):warnings.append('任务少于可用日期，部分日期留作巩固或休息。')
    with SessionLocal.begin() as s:
        if s.get(Conversation,conversation_id) is None:raise LookupError('会话不存在')
        group_key=uuid4().hex
        if parent_plan_id is not None:
            parent=s.get(Plan,parent_plan_id)
            if parent is None or parent.conversation_id!=conversation_id:raise LookupError('原计划不存在')
            if parent.status!='active':raise ValueError('只能基于当前正式计划调整')
            group_key=parent.group_key
        p=Plan(conversation_id=conversation_id,group_key=group_key,parent_plan_id=parent_plan_id,goal=draft.goal.strip(),start_date=budgets[0].plan_date,end_date=budgets[-1].plan_date,daily_budgets=[d.model_dump(mode='json') for d in budgets],warnings=warnings,status='draft',change_reason=change_reason)
        s.add(p);s.flush();position=0
        for day,tasks in zip(budgets,allocation):
            for t in tasks:
                s.add(Task(plan_id=p.id,plan_date=day.plan_date,title=t.title,expected_output=t.expected_output,estimated_minutes=None,position=position,status='pending'));position+=1
        response={'ok':True,'draft_plan_id':p.id,'status':'draft','total_minutes':None,'warnings':warnings}  # 【修改：时长选填】不累计预测耗时
    return response

# add================================
# plan_service.py
# 保留原来的 validate_and_save_draft()，在下面追加。

from sqlalchemy import select

from datasets import SessionLocal, Plan, utc_now


# 【修改：按天规划】 按整份计划的group_key确认版本，不按某一天误伤其他计划。
def confirm_plan(*,conversation_id,plan_id):
    with SessionLocal.begin() as s:
        p=s.get(Plan,plan_id)
        if p is None or p.conversation_id!=conversation_id:raise LookupError('计划不存在')
        if p.status=='active':return {'ok':True,'plan_id':p.id,'status':'active'}
        if p.status!='draft':raise ValueError('只有草稿可以确认')
        active=s.scalar(select(Plan).where(Plan.conversation_id==conversation_id,Plan.group_key==p.group_key,Plan.status=='active'))
        if p.parent_plan_id is not None and (active is None or active.id!=p.parent_plan_id):raise ValueError('原正式计划已变化，请重新生成调整草稿')
        if active:active.status='superseded';s.flush()
        p.status='active';p.confirmed_at=utc_now()
        for other in s.scalars(select(Plan).where(Plan.group_key==p.group_key,Plan.conversation_id==conversation_id,Plan.status=='draft',Plan.id!=p.id)):other.status='discarded'
        s.flush();return {'ok':True,'plan_id':p.id,'status':'active'}


# 【新增：修改草稿】不经过正式计划的版本创建流程。
from schemas import DraftTaskReplacement


def update_draft_tasks(
    *,
    conversation_id: str,
    plan_id: int,
    replacements: list,
) -> dict:
    """修改当前会话内的草稿任务，保持计划ID和其他任务不变。"""

    if not replacements:
        raise ValueError("至少需要提供一项任务修改")

    # 先校验全部输入，再开始数据库写入。
    items = [
        DraftTaskReplacement.model_validate(item)
        for item in replacements
    ]

    task_ids = [item.task_id for item in items]

    if len(task_ids) != len(set(task_ids)):
        raise ValueError("同一次修改不能重复指定同一个任务")

    # 全部任务在一个事务中修改，任意一项失败则全部回滚。
    with SessionLocal.begin() as session:
        plan = session.get(Plan, plan_id)

        if (
            plan is None
            or plan.conversation_id != conversation_id
        ):
            raise LookupError("当前会话中不存在这份计划")

        if plan.status != "draft":
            raise ValueError(
                "此工具只能修改草稿；正式计划请生成调整版本"
            )

        tasks = session.scalars(
            select(Task).where(
                Task.plan_id == plan_id,
                Task.id.in_(task_ids),
            )
        ).all()

        # 防止模型传入其他计划中的任务ID。
        if len(tasks) != len(task_ids):
            raise ValueError(
                "部分任务不存在或不属于当前草稿，请重新读取计划"
            )

        tasks_by_id = {
            task.id: task
            for task in tasks
        }

        for item in items:
            task = tasks_by_id[item.task_id]

            # 只修改明确允许的两个字段。
            task.title = item.title
            task.expected_output = item.expected_output

        # 正常退出事务后才会提交。
        response = {
            "ok": True,
            "draft_plan_id": plan.id,
            "status": "draft",
            "updated_task_ids": task_ids,
            "updated_count": len(items),
            "message": (
                f"已更新草稿中的{len(items)}项任务，"
                "其余任务、日期和顺序保持不变，等待用户确认"
            ),
        }

    return response