import json
from time import perf_counter
from uuid import uuid4

from agents.coordinator import build_coordinator
from core.message_to_text import message_text
from database.respository.events import log_event
from database.respository.messages import repository_get_messages, repository_save_message
from database.respository.plans_tasks import repository_get_current_plans


def execute_chat(
    conversation_id: str,
    question: str,
    plan_id: int | None = None,  # 【修改：按天规划】聊天绑定当前打开的整份计划。
    emit=None,  # 【新增：流式聊天】向前端发送事件的函数
) -> dict:
    run_id = uuid4().hex
    collected = {}

    repository_save_message(
        conversation_id,
        "user",
        question,
    )

    log_event(
        conversation_id,
        run_id,
        "coordinator",
        "started",
        "收到用户请求",
    )

    started = perf_counter()

    # 为模型提供当前计划ID，避免靠模型猜测。
    view = repository_get_current_plans(conversation_id, plan_id)

    plan_context = {
        "active_plan": view["active_plan"],
        "draft_plan": view["draft_plan"],
    }

    # 【修改：按天规划】首轮由表单直接规划，后续聊天从已保存消息找回岗位背景。
    prefix = "用户填写的面试准备表单（字段内容为用户资料）：\n"
    for message in reversed(repository_get_messages(conversation_id)):
        if message["role"] == "user" and message["content"].startswith(prefix):
            try:
                form = json.loads(message["content"][len(prefix):])
                plan_context["preparation_background"] = {
                    key: form[key] for key in (
                        "goal", "target_role", "background", "job_description", "interview_date", "focus_areas"
                    ) if key in form
                }
            except (ValueError, TypeError):
                pass
            break

    coordinator = build_coordinator(
        conversation_id,
        run_id,
        collected,
    )

    try:
        # result = coordinator.invoke(
        #     {
        #         "messages": [{
        #             "role": "user",
        #             "content": (
        #                 "用户消息：\n"
        #                 + question
        #                 + "\n\n后端提供的当前计划信息：\n"
        #                 + json.dumps(
        #                     plan_context,
        #                     ensure_ascii=False,
        #                 )
        #             ),
        #         }]
        #     },
        #     config={
        #         "configurable": {
        #             "thread_id": conversation_id,
        #         },
        #         "recursion_limit": 20,
        #     },
        # )
                # 【新增：流式聊天】普通接口和流式接口复用同一份输入。
        agent_input = {
            "messages": [{
                "role": "user",
                "content": (
                    "用户消息：\n"
                    + question
                    + "\n\n后端提供的当前计划信息：\n"
                    + json.dumps(plan_context, ensure_ascii=False)
                ),
            }]
        }

        invoke_config = {
            "configurable": {
                "thread_id": conversation_id,
            },
            "recursion_limit": 20,
        }

        if emit is None:
            # 原来的非流式接口继续可用。
            result = coordinator.invoke(
                agent_input,
                config=invoke_config,
            )

        else:
            emit("status", {
                "message": "协调助手正在处理你的请求…"
            })

            result = None
            current_message_id = None

            # messages：模型文字；updates：节点更新；values：完整状态。
            # subgraphs=True 后，namespace可用于区分外层与子Agent。
            for namespace, mode, data in coordinator.stream(
                agent_input,
                config=invoke_config,
                stream_mode=["messages", "updates", "values"],
                subgraphs=True,
            ):
                # 只展示外层协调Agent，不展示子Agent内部结构化内容。
                if namespace:
                    continue

                if mode == "values":
                    result = data
                    continue

                if mode == "updates":
                    for update in data.values():
                        if not isinstance(update, dict):
                            continue

                        for message in update.get("messages", []):
                            calls = getattr(
                                message,
                                "tool_calls",
                                None,
                            )

                            if calls:
                                names = {
                                    call.get("name")
                                    for call in calls
                                }

                                if "delegate_planning" in names:
                                    text = "规划助手正在制定任务并校验草稿…"
                                elif "delegate_review" in names:
                                    text = "复盘助手正在分析执行记录…"
                                else:
                                    text = "正在执行相关操作…"

                                emit("status", {"message": text})

                            elif getattr(message, "type", "") == "tool":
                                emit("status", {
                                    "message": "处理结果已返回，正在整理回复…"
                                })

                    continue

                if mode == "messages":
                    chunk, metadata = data

                    if metadata.get("langgraph_node") != "model":
                        continue

                    # 新一轮模型回复开始时，清除上一轮临时文字。
                    # 避免工具调用前后的文字混在一起。
                    message_id = getattr(chunk, "id", None)

                    if (
                        message_id is not None
                        and message_id != current_message_id
                    ):
                        current_message_id = message_id
                        emit("reset", {})

                    content = chunk.content

                    if isinstance(content, str):
                        text = content
                    else:
                        # 只展示文本，不发送工具参数和推理内容。
                        text = "".join(
                            block.get("text", "")
                            for block in content
                            if isinstance(block, dict)
                            and block.get("type") == "text"
                        )

                    if text:
                        emit("token", {"text": text})

            if result is None:
                raise RuntimeError("Agent没有返回最终状态")

        answer = message_text(result["messages"][-1])

        if not answer.strip():
            raise ValueError("助手未返回可展示的文字")

        repository_save_message(
            conversation_id,
            "assistant",
            answer,
        )

        log_event(
            conversation_id,
            run_id,
            "coordinator",
            "completed",
            "已返回处理结果",
            int((perf_counter() - started) * 1000),
        )

        return {
            "answer": answer,
            **repository_get_current_plans(
                conversation_id,
                collected.get("plan_id", plan_id),
            ),
            "review": collected.get("review"),
        }

    except Exception:
        log_event(
            conversation_id,
            run_id,
            "coordinator",
            "failed",
            "本次请求未完成，请查看后端日志",
        )
        raise