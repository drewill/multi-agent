"""【新增：模拟面试】代码控制题数、追问次数与状态；模型仅负责提问和评价。"""
import json
from uuid import uuid4
from sqlalchemy import select
from datasets import SessionLocal, Plan, utc_now
from interview_models import InterviewSession, InterviewTurn, InterviewReport
from repository import repository_get_plan, repository_get_messages
from agents.interviewer import interviewer, evaluator
from agents.planner import planner_agent
from agents.plan_service import validate_and_save_draft, normalize_days


def owned_plan(s, cid, pid):
    plan = s.get(Plan, pid)
    if plan is None or plan.conversation_id != cid or plan.status == 'discarded':
        raise LookupError('计划不存在')
    return plan


def owned_interview(s, cid, sid):
    interview = s.get(InterviewSession, sid)
    if interview is None:
        raise LookupError('面试不存在')
    owned_plan(s, cid, interview.plan_id)
    return interview


def turns_for(s, sid):
    return list(s.scalars(select(InterviewTurn).where(InterviewTurn.session_id == sid).order_by(InterviewTurn.position)))


def view(cid, sid):
    with SessionLocal() as s:
        iv = owned_interview(s, cid, sid)
        report = s.scalar(select(InterviewReport).where(InterviewReport.session_id == sid))
        turns = turns_for(s, sid)
        return {'id':iv.id, 'plan_id':iv.plan_id,'status':iv.status,'question_count':iv.question_count,
                'scope':iv.scope,'interview_type':iv.interview_type,'ready':iv.ready_at is not None,
                'turns':[{'id':t.id,'question_number':t.question_number,'kind':t.kind,'question':t.question,'answer':t.answer} for t in turns],
                'report':report.result if report else None,'created_at':iv.created_at.isoformat()}


def start(cid, pid, scope, interview_type, count):
    with SessionLocal() as s:
        p = owned_plan(s, cid, pid)
        if p.status != 'active':
            raise ValueError('请先确认计划，再开始面试')
    data = repository_get_plan(pid)
    tasks = data['tasks']
    if scope == 'completed':
        tasks = [t for t in tasks if t['status'] == 'completed']
        if not tasks:
            raise ValueError('还没有已完成任务，请改选整个计划或岗位综合')
    # 保存真实表单快照；重开面试不依赖协调Agent内存。
    background = ''
    for msg in reversed(repository_get_messages(cid)):
        text = msg.get('content','')
        if text.startswith('用户填写的面试准备表单'):
            background = text
            break
    sid = uuid4().hex
    with SessionLocal.begin() as s:
        s.add(InterviewSession(id=sid,plan_id=pid,scope=scope,interview_type=interview_type,question_count=count,
            context={'goal':data['plan']['goal'],'tasks':tasks,'background':background,'scope':scope,'interview_type':interview_type}))
    # 模型失败时session仍保留，可以在历史记录中恢复重试。
    return advance(cid, sid)


def advance(cid, sid):
    with SessionLocal() as s:
        iv = owned_interview(s, cid, sid)
        turns = turns_for(s, sid)
        if iv.status == 'report_pending':
            return finish(cid, sid)
        if iv.status == 'completed' or (turns and turns[-1].answer is None):
            return view(cid, sid)
        last = turns[-1] if turns else None
        number = last.question_number if last else 0
        can_follow = bool(last and last.kind == 'main')
        if number >= iv.question_count and not can_follow:
            return finish(cid, sid)
        payload = {'context':iv.context,'history':[{'question':t.question,'answer':t.answer,'number':t.question_number,'kind':t.kind} for t in turns],
                   'allow_follow_up':can_follow,'force_follow_up_only':number >= iv.question_count,
                   'next_main_number':number+1}
        position = len(turns)
    decision = interviewer.invoke({'messages':[{'role':'user','content':json.dumps(payload,ensure_ascii=False)}]})['structured_response']
    # 最后一题不强迫追问：模型选择不追问即结束；其他场景最多追问一次。
    follow = can_follow and decision.follow_up
    if number >= iv.question_count and not follow:
        return finish(cid, sid)
    with SessionLocal.begin() as s:
        owned_interview(s, cid, sid)
        s.add(InterviewTurn(session_id=sid,position=position,question_number=number if follow else number+1,
                            kind='follow_up' if follow else 'main',question=decision.question))
    return view(cid, sid)


def answer(cid, sid, turn_id, text):
    # 先保存回答再请求模型。失败后以相同turn_id重试，不重复插入用户回答。
    with SessionLocal.begin() as s:
        iv = owned_interview(s, cid, sid)
        t = s.get(InterviewTurn, turn_id)
        if t is None or t.session_id != sid:
            raise LookupError('问题不存在')
        if iv.status != 'active':
            return view(cid, sid)
        if t.answer is not None:
            if t.answer != text:
                raise ValueError('该题已提交，请刷新后继续下一题')
        else:
            turns = turns_for(s, sid)
            if turns[-1].id != turn_id:
                raise ValueError('只能回答当前问题')
            t.answer = text
    return advance(cid, sid)


def finish(cid, sid):
    with SessionLocal.begin() as s:
        iv = owned_interview(s, cid, sid)
        if s.scalar(select(InterviewReport).where(InterviewReport.session_id == sid)):
            return view(cid, sid)
        turns = turns_for(s, sid)
        if not any(t.answer is not None for t in turns):
            raise ValueError('至少回答一道题后才能生成报告')
        iv.status = 'report_pending'
        payload = {'context':iv.context,'turns':[{'number':t.question_number,'kind':t.kind,'question':t.question,'answer':t.answer} for t in turns]}
    result = evaluator.invoke({'messages':[{'role':'user','content':json.dumps(payload,ensure_ascii=False)}]})['structured_response']
    result = result.model_dump(mode='json')
    with SessionLocal.begin() as s:
        iv = owned_interview(s, cid, sid)
        s.add(InterviewReport(session_id=sid,result=result))
        iv.status = 'completed'
    return view(cid, sid)


def ready(cid, sid):
    with SessionLocal.begin() as s:
        iv = owned_interview(s, cid, sid)
        if iv.status != 'completed':
            raise ValueError('面试报告生成后才能确认准备完成')
        iv.ready_at = utc_now()
    return {'ok':True,'message':'祝你面试成功！'}


def history(cid, pid):
    with SessionLocal() as s:
        p = owned_plan(s, cid, pid)
        versions = list(s.scalars(select(Plan).where(Plan.conversation_id==cid,Plan.group_key==p.group_key,Plan.status!='discarded').order_by(Plan.id.desc())))
        ids = list(s.scalars(select(InterviewSession.id).where(InterviewSession.plan_id.in_([v.id for v in versions])).order_by(InterviewSession.created_at.desc())))
        vs = [{'plan_id':v.id,'status':v.status,'change_reason':v.change_reason,'created_at':v.created_at.isoformat()} for v in versions]
    return {'interviews':[view(cid,i) for i in ids],'versions':vs}


def replan(cid, sid, days):
    budgets = normalize_days(days)
    with SessionLocal() as s:
        iv = owned_interview(s, cid, sid)
        old = owned_plan(s,cid,iv.plan_id)
        active = s.scalar(select(Plan).where(Plan.group_key==old.group_key,Plan.conversation_id==cid,Plan.status=='active'))
        if active is None:
            raise ValueError('这份计划没有正式版本，请先确认计划')
        report = s.scalar(select(InterviewReport).where(InterviewReport.session_id==sid))
        if report is None:
            raise ValueError('请先生成面试报告')
        if not report.result.get('weak_points'):
            raise ValueError('报告没有明确薄弱点，暂不自动调整计划')
        parent_id = active.id
        report_data = report.result
        context = iv.context
    payload = {'request':'依据面试报告生成后续学习草稿，优先补弱；已完成任务不重复安排，除非报告明确显示需要巩固。',
               'days':[d.model_dump(mode='json') for d in budgets], 'parent_plan_id':parent_id,
               'original_plan':repository_get_plan(parent_id),'interview_report':report_data,'background':context}
    for attempt in range(2):
        draft = planner_agent.invoke({'messages':[{'role':'user','content':json.dumps(payload,ensure_ascii=False)}]})['structured_response']
        saved = validate_and_save_draft(draft,conversation_id=cid,days=payload['days'],parent_plan_id=parent_id,
                                        change_reason=f'依据模拟面试 {sid} 的薄弱点调整')
        if saved['ok']:
            result = repository_get_plan(saved['draft_plan_id'])
            return {'draft_plan':{**result['plan'],'tasks':result['tasks']},'message':'调整草稿已保存，确认后才生效'}
        payload['validation_errors_to_fix'] = saved['errors']
    raise ValueError('调整草稿未通过校验：'+'；'.join(saved['errors']))
