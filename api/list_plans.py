from fastapi import APIRouter
from sqlalchemy import select

from database.init_database import SessionLocal
from database.plan_database import Plan

router = APIRouter()

@router.get('/')
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
