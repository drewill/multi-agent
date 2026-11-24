import json
from time import perf_counter
from sqlalchemy import select
from database.init_database import SessionLocal
from database.respository.events import log_event
from database.respository.plans_tasks import get_owned_plan, task_to_dict
from database.task_database import Task
from schemas.review_schemas import ReviewResult
from database.review_database import Review
from agents.res import reviewer
import logging
logger = logging.getLogger(__name__)


def execute_review(
    conversation_id: str,
    run_id: str,
    plan_id: int,
    feedback: str,
) -> dict:
    plan = get_owned_plan(conversation_id, plan_id)

    if plan["status"] != "active":
        raise ValueError("请先确认计划，再进行复盘")

    # 记录复盘发生时的任务状态，避免后续修改覆盖复盘依据。
    with SessionLocal() as session:
        tasks = session.scalars(
            select(Task)
            .where(Task.plan_id == plan_id)
            .order_by(Task.position)
        ).all()

        snapshot = [task_to_dict(task) for task in tasks]

    log_event(
        conversation_id,
        run_id,
        "reviewer",
        "started",
        f"开始复盘计划 #{plan_id}",
    )

    started = perf_counter()

    try:
        result = reviewer.invoke({
            "messages": [{
                "role": "user",
                "content": json.dumps(
                    {
                        "plan_id": plan_id,
                        "plan": plan,
                        "execution_logs": snapshot,
                        "feedback": feedback,
                    },
                    ensure_ascii=False,
                ),
            }]
        })

        review_result = result["structured_response"]
        if review_result is None:
            logger.error(
            "复盘缺少结构化结果，返回字段：%s",
            list(result.keys()),
            )
            raise ValueError(
                "复盘模型未返回有效的结构化结果，本次复盘未保存"
            )
        review_result = ReviewResult.model_validate(review_result)
        review_data = review_result.model_dump(mode="json")

        with SessionLocal.begin() as session:
            review = Review(
                plan_id=plan_id,
                feedback=feedback,
                task_snapshot=snapshot,
                result=review_data,
            )
            session.add(review)
            session.flush()
            review_id = review.id

        log_event(
            conversation_id,
            run_id,
            "reviewer",
            "completed",
            f"复盘已保存，编号 #{review_id}",
            int((perf_counter() - started) * 1000),
        )

        return {
            "review_id": review_id,
            "plan_id": plan_id,
            **review_data,
        }

    except Exception:
        log_event(
            conversation_id,
            run_id,
            "reviewer",
            "failed",
            "复盘执行失败，请查看后端日志",
        )
        raise
