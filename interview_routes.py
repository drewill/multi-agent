"""【新增：模拟面试】在main.py注册；沿用本地单worker操作锁。"""
import logging
from fastapi import HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from schemas import DayBudget
import interview_service as service

class Owner(BaseModel):
    conversation_id: str = Field(min_length=1,max_length=32)
class StartInterview(Owner):
    plan_id: int = Field(gt=0)
    scope: Literal['completed','plan','job'] = 'completed'
    interview_type: Literal['basic','project','mixed'] = 'mixed'
    question_count: Literal[3,5,8] = 5
class AnswerInterview(Owner):
    turn_id: int = Field(gt=0)
    answer: str = Field(min_length=1,max_length=12000)
class ReplanInterview(Owner):
    days: list[DayBudget] = Field(min_length=1,max_length=14)

def register_interview_routes(app, operation_lock):
    def call(fn, *args):
        try:
            with operation_lock:
                return fn(*args)
        except LookupError as e:
            raise HTTPException(404,str(e)) from e
        except ValueError as e:
            raise HTTPException(409,str(e)) from e
        except Exception as e:
            logging.getLogger(__name__).exception('模拟面试操作失败')
            raise HTTPException(502,'模型请求暂时失败。回答已提交时会保留，请从面试记录中继续或重试生成报告。') from e

    @app.post('/api/interviews')
    def start(body:StartInterview):
        return call(service.start,body.conversation_id,body.plan_id,body.scope,body.interview_type,body.question_count)
    @app.get('/api/plans/{plan_id}/interviews')
    def history(plan_id:int,conversation_id:str):
        return call(service.history,conversation_id,plan_id)
    @app.get('/api/interviews/{sid}')
    def get(sid:str,conversation_id:str):
        return call(service.view,conversation_id,sid)
    @app.post('/api/interviews/{sid}/answer')
    def answer(sid:str,body:AnswerInterview):
        text=body.answer.strip()
        if not text:raise HTTPException(422,'回答不能为空')
        return call(service.answer,body.conversation_id,sid,body.turn_id,text)
    @app.post('/api/interviews/{sid}/continue')
    def advance(sid:str,body:Owner):
        return call(service.advance,body.conversation_id,sid)
    @app.post('/api/interviews/{sid}/finish')
    def finish(sid:str,body:Owner):
        return call(service.finish,body.conversation_id,sid)
    @app.post('/api/interviews/{sid}/ready')
    def ready(sid:str,body:Owner):
        return call(service.ready,body.conversation_id,sid)
    @app.post('/api/interviews/{sid}/replan')
    def replan(sid:str,body:ReplanInterview):
        return call(service.replan,body.conversation_id,sid,[d.model_dump(mode='json') for d in body.days])
