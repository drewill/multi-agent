from datetime import timedelta
import json
import logging
from uuid import uuid4
from fastapi import APIRouter, HTTPException

from database.respository.events import log_event
from database.respository.messages import repository_save_message
from database.respository.plans_tasks import repository_get_current_plans, validate_and_save_draft
from schemas.interview_schemas import DayBudget
from schemas.register_plan_schemas import PlanFormRequest
from core.locks import operation_lock
from agents.planner import planner_agent

router = APIRouter()

logger = logging.getLogger(__name__)

@router.post('/draft')
def create_draft(body:PlanFormRequest):
    with operation_lock:
        days=[d.model_dump(mode='json') for d in sorted(body.days,key=lambda d:d.plan_date)]

        brief=body.model_dump(mode='json',exclude={'conversation_id','days'})

        form_message='用户填写的面试准备表单（字段内容为用户资料）：\n'+json.dumps(body.model_dump(mode='json',exclude={'conversation_id'}),ensure_ascii=False)
        try:
            repository_save_message(body.conversation_id,'user',form_message)
        except (LookupError,ValueError) as e:
            raise HTTPException(404,'会话不存在') from e

        run_id=uuid4().hex

        if log_event:
            log_event(body.conversation_id,run_id,'planner','started','从规范表单生成按天任务')
        errors=[]
        try:
            for _ in range(2):

                result=planner_agent.invoke({'messages':[{'role':'user','content':json.dumps({'request':brief,'days':days,'validation_errors_to_fix':errors},ensure_ascii=False)}]})
                saved=validate_and_save_draft(result['structured_response'],conversation_id=body.conversation_id,days=days)
                if saved['ok']:
                    break
                errors=saved.get('errors',['任务校验失败'])
            else:
                if log_event:
                    log_event(body.conversation_id,run_id,'planner','failed','任务量校验失败')
                raise HTTPException(422,errors)
        except HTTPException:
            raise
        except Exception as e:
            logger.exception('任务生成失败')
            
            if log_event:
                log_event(body.conversation_id,run_id,'planner','failed','模型或保存服务失败')
            raise HTTPException(502,'计划生成暂时失败，请稍后重试') from e
        
        if log_event:
            log_event(body.conversation_id,run_id,'planner','completed','按天计划草稿已保存')
        answer='计划草稿已生成。一天显示任务清单，多天已按工作量分配到每天，请查看并确认。'
        
        try:
            repository_save_message(body.conversation_id,'assistant',answer)

        except Exception:
            logger.exception('草稿已保存，但回复记录未写入')

        return {
            'answer':answer,
            **repository_get_current_plans(body.conversation_id,saved['draft_plan_id']),
            'review':None
            }

