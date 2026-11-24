
import json
import logging
from queue import Empty, Queue
from threading import Thread
from fastapi import HTTPException,APIRouter
from fastapi.responses import StreamingResponse
from api.conversation import require_conversation
from schemas.chat_schemas import ChatRequest

from core.locks import operation_lock
from services.chat_service import execute_chat
logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/")
def chat_stream(body: ChatRequest):

    question = body.question.strip()

    if not question:
        raise HTTPException(400, "问题不能为空")

    require_conversation(body.conversation_id)

    events = Queue()

    def emit(event: str, data: dict):
        events.put((event, data))

    def run_agent():
        try:
            emit("status", {
                "message": "请求已收到，正在等待处理…"
            })

            # 沿用当前项目的锁，不在这一步同时修改并发架构。
            with operation_lock:
                result = execute_chat(
                    body.conversation_id,
                    question,
                    plan_id=body.plan_id,
                    emit=emit,
                )

            # 最终完整结果包含回答和计划，前端据此同步页面。
            emit("result", result)
            emit("done", {})

        except Exception:
            logger.exception("流式聊天失败")

            emit("error", {
                "message": "本次回复未完成，请稍后重试。"
            })

        finally:
            events.put(None)

    def generate():
        Thread(
            target=run_agent,
            daemon=True,
        ).start()

        while True:
            try:
                item = events.get(timeout=15)
            except Empty:
                # 心跳，避免长时间执行工具时连接完全没有数据。
                yield ": ping\n\n"
                continue

            if item is None:
                break

            event, data = item

            yield (
                f"event: {event}\n"
                f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
