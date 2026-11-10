# 【修改：时长选填】每日分钟数可为空，未限制时不计算虚构的总预算。
# 【修改：按天规划】 新增文件：补齐页面已有的结构化表单提交接口，支持一天和多天。
import json
import logging
from contextlib import nullcontext
from uuid import uuid4
from fastapi import HTTPException
from schemas import PlanFormRequest
logger=logging.getLogger(__name__)

def register_plan_form_routes(app,*,planner_agent,validate_and_save_draft,get_plan_view,repository_save_message,operation_lock=None,log_event=None):
    
    @app.post('/api/plans/draft')
    def create_draft(body:PlanFormRequest):
        with operation_lock if operation_lock is not None else nullcontext():
            days=[d.model_dump(mode='json') for d in sorted(body.days,key=lambda d:d.plan_date)]
            brief=body.model_dump(mode='json',exclude={'conversation_id','days'})
            form_message='用户填写的面试准备表单（字段内容为用户资料）：\n'+json.dumps(body.model_dump(mode='json',exclude={'conversation_id'}),ensure_ascii=False)
            try:repository_save_message(body.conversation_id,'user',form_message)
            except (LookupError,ValueError) as e:raise HTTPException(404,'会话不存在') from e
            run_id=uuid4().hex
            if log_event:log_event(body.conversation_id,run_id,'planner','started','从规范表单生成按天任务')
            errors=[]
            try:
                for attempt in range(2):
                    result=planner_agent.invoke({'messages':[{'role':'user','content':json.dumps({'request':brief,'days':days,'validation_errors_to_fix':errors},ensure_ascii=False)}]})
                    saved=validate_and_save_draft(result['structured_response'],conversation_id=body.conversation_id,days=days)
                    if saved['ok']:break
                    errors=saved.get('errors',['任务校验失败'])
                else:
                    if log_event:log_event(body.conversation_id,run_id,'planner','failed','任务量校验失败')
                    raise HTTPException(422,errors)
            except HTTPException:raise
            except Exception as e:
                logger.exception('任务生成失败')
                
                if log_event:log_event(body.conversation_id,run_id,'planner','failed','模型或保存服务失败')
                raise HTTPException(502,'计划生成暂时失败，请稍后重试') from e
            
            if log_event:log_event(body.conversation_id,run_id,'planner','completed','按天计划草稿已保存')
            answer='计划草稿已生成。一天显示任务清单，多天已按工作量分配到每天，请查看并确认。'
            
            try:
                repository_save_message(body.conversation_id,'assistant',answer)

            except Exception:logger.exception('草稿已保存，但回复记录未写入')

            return {
                'answer':answer,
                **get_plan_view(body.conversation_id,saved['draft_plan_id']),
                'review':None
                }
