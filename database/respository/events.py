from sqlalchemy import select
from core.time_to_str import datetime_to_str
from database.agentevent_database import AgentEvent
from database.conversation_database import Conversation
from database.init_database import SessionLocal
from database.messages_database import Message


def log_event(
    conversation_id: str,
    run_id: str,
    agent_name: str,
    event_type: str,
    summary: str,
    duration_ms: int | None = None,
):
    with SessionLocal.begin() as session:
        session.add(
            AgentEvent(
                conversation_id=conversation_id,
                run_id=run_id,
                agent_name=agent_name,
                event_type=event_type,
                summary=summary,
                duration_ms=duration_ms,
            )
        )

def get_events(conversation_id: str) -> list[dict]:
    with SessionLocal() as session:
        rows = session.scalars(
            select(AgentEvent)
            .where(AgentEvent.conversation_id == conversation_id)
            .order_by(AgentEvent.id.desc())
            .limit(100)
        ).all()

        return [
            {
                "id": row.id,
                "run_id": row.run_id,
                "agent_name": row.agent_name,
                "event_type": row.event_type,
                "summary": row.summary,
                "duration_ms": row.duration_ms,
                "created_at": datetime_to_str(row.created_at),
            }
            for row in reversed(rows)
        ]