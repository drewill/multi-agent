import logging
from fastapi import APIRouter, HTTPException

from schemas.interview_schemas import AnswerInterview, Owner, ReplanInterview, StartInterview
from services import interview_service
from core.locks import operation_lock
router = APIRouter()



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

@router.post('/api/interviews')
def start(body:StartInterview):
    return call(interview_service.start,body.conversation_id,body.plan_id,body.scope,body.interview_type,body.question_count)

@router.get('/api/plans/{plan_id}/interviews')
def history(plan_id:int,conversation_id:str):
    return call(interview_service.history,conversation_id,plan_id)

@router.get('/api/interviews/{sid}')
def get(sid:str,conversation_id:str):
    return call(interview_service.view,conversation_id,sid)

@router.post('/api/interviews/{sid}/answer')
def answer(sid:str,body:AnswerInterview):
    text=body.answer.strip()
    if not text:raise HTTPException(422,'回答不能为空')
    return call(interview_service.answer,body.conversation_id,sid,body.turn_id,text)

@router.post('/api/interviews/{sid}/continue')
def advance(sid:str,body:Owner):
    return call(interview_service.advance,body.conversation_id,sid)

@router.post('/api/interviews/{sid}/finish')
def finish(sid:str,body:Owner):
    return call(interview_service.finish,body.conversation_id,sid)

@router.post('/api/interviews/{sid}/ready')
def ready(sid:str,body:Owner):
    return call(interview_service.ready,body.conversation_id,sid)

@router.post('/api/interviews/{sid}/replan')
def replan(sid:str,body:ReplanInterview):
    return call(interview_service.replan,body.conversation_id,sid,[d.model_dump(mode='json') for d in body.days])
