from sqlalchemy import select
from database.conversation_database import Conversation
from database.init_database import SessionLocal
from database.messages_database import Message


def repository_save_message(
    conversation_id: str,
    role: str,
    content: str,
) -> dict:
    """保存一条用户消息或助手消息。"""

    if role not in {"user", "assistant"}:
        raise ValueError("消息角色必须是 user 或 assistant")

    if not isinstance(content, str) or not content.strip():
        raise ValueError("消息内容不能为空")

    with SessionLocal.begin() as session:
        conversation = session.get(
            Conversation,
            conversation_id,
        )

        if conversation is None:
            raise LookupError("会话不存在")

        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )

        session.add(message)
        session.flush()

        result = {
            "id": message.id,
            "conversation_id": message.conversation_id,
            "role": message.role,
            "content": message.content,
        }

    return result


def repository_get_messages(conversation_id: str) -> list[dict]:
    """读取会话中的聊天记录，按保存顺序排列。"""

    with SessionLocal() as session:
        conversation = session.get(
            Conversation,
            conversation_id,
        )

        if conversation is None:
            raise LookupError("会话不存在")

        messages = session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id)
        ).all()

        return [
            {
                "id": message.id,
                "role": message.role,
                "content": message.content,
            }
            for message in messages
        ]
