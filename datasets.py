# database.py
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    select,
    text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    sessionmaker,
)


# ============================================================
# 1. 数据库配置
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "study_assistant.db"


def utc_now() -> datetime:
    """统一保存不带时区标记的 UTC 时间。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


engine = create_engine(
    f"sqlite:///{DB_PATH.as_posix()}",
    echo=False,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
    },
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _):
    """SQLite 的每个连接都开启外键检查。"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


# ============================================================
# 2. 会话表
# ============================================================

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default=lambda: uuid4().hex,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        default="新的学习会话",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )


# ============================================================
# 3. 聊天消息表
# ============================================================

class Message(Base):
    __tablename__ = "messages"

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_messages_role",
        ),
        Index(
            "ix_messages_conversation_id_id",
            "conversation_id",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
    )

    role: Mapped[str] = mapped_column(String(20))

    content: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )


# ============================================================
# 4. 计划表
# ============================================================

# 【修改：按天规划】 一份计划保存日期范围、每日预算和版本分组。
class Plan(Base):
    __tablename__='daily_plans'
    __table_args__=(CheckConstraint("status IN ('draft','active','superseded','discarded')"),CheckConstraint('end_date >= start_date'),Index('uq_daily_active_group','conversation_id','group_key',unique=True,sqlite_where=text("status = 'active'")))
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    conversation_id:Mapped[str]=mapped_column(ForeignKey('conversations.id',ondelete='CASCADE'),index=True)
    group_key:Mapped[str]=mapped_column(String(64),default=lambda:uuid4().hex,index=True)
    parent_plan_id:Mapped[int|None]=mapped_column(ForeignKey('daily_plans.id',ondelete='SET NULL'),nullable=True)
    goal:Mapped[str]=mapped_column(Text)
    start_date:Mapped[date]=mapped_column(Date)
    end_date:Mapped[date]=mapped_column(Date)
    daily_budgets:Mapped[list]=mapped_column(JSON,default=list)
    warnings:Mapped[list]=mapped_column(JSON,default=list)
    status:Mapped[str]=mapped_column(String(20),default='draft')
    change_reason:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=utc_now)
    confirmed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)


# ============================================================
# 5. 任务表
# ============================================================

# 【修改：按天规划】 任务归属某一天，移除钟点及其非空约束。
class Task(Base):
    __tablename__='daily_tasks'
    __table_args__=(CheckConstraint("status IN ('pending','in_progress','completed','skipped')"),CheckConstraint('estimated_minutes > 0'),CheckConstraint('actual_minutes IS NULL OR actual_minutes >= 0'),UniqueConstraint('plan_id','position'))
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    plan_id:Mapped[int]=mapped_column(ForeignKey('daily_plans.id',ondelete='CASCADE'),index=True)
    source_task_id:Mapped[int|None]=mapped_column(ForeignKey('daily_tasks.id',ondelete='SET NULL'),nullable=True)
    plan_date:Mapped[date]=mapped_column(Date,index=True)
    title:Mapped[str]=mapped_column(String(255))
    expected_output:Mapped[str]=mapped_column(Text)
    # 【修改：时长选填】旧预计耗时仅供兼容历史，新任务存NULL。
    estimated_minutes:Mapped[int|None]=mapped_column(Integer,nullable=True)
    actual_minutes:Mapped[int|None]=mapped_column(Integer,nullable=True)
    position:Mapped[int]=mapped_column(Integer,default=0)
    status:Mapped[str]=mapped_column(String(20),default='pending')
    note:Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=utc_now)
    completed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)


# ============================================================
# 6. 复盘表
# ============================================================

# 【修改：按天规划】 复盘外键指向新版计划表，保留原有复盘字段。
class Review(Base):
    __tablename__='daily_reviews'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    plan_id:Mapped[int]=mapped_column(ForeignKey('daily_plans.id',ondelete='CASCADE'),index=True)
    feedback:Mapped[str]=mapped_column(Text)
    task_snapshot:Mapped[list]=mapped_column(JSON,default=list)
    result:Mapped[dict]=mapped_column(JSON,default=dict)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=utc_now)


# ============================================================
# 7. Agent 协作事件表
# ============================================================

class AgentEvent(Base):
    __tablename__ = "agent_events"

    __table_args__ = (
        CheckConstraint(
            "agent_name IN ('coordinator', 'planner', 'reviewer')",
            name="ck_agent_events_agent",
        ),
        CheckConstraint(
            "event_type IN "
            "('started', 'tool_called', 'completed', 'failed')",
            name="ck_agent_events_type",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_agent_events_duration",
        ),
        Index(
            "ix_agent_events_conversation_id_id",
            "conversation_id",
            "id",
        ),
        Index(
            "ix_agent_events_run_id_id",
            "run_id",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
    )

    # 一次用户请求对应一个 run_id，
    # 同一次请求中的多个事件共用这个 ID。
    run_id: Mapped[str] = mapped_column(String(32))

    agent_name: Mapped[str] = mapped_column(String(30))

    event_type: Mapped[str] = mapped_column(String(30))

    summary: Mapped[str] = mapped_column(Text)

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
    )



# ============================================================
# 8. 初始化
# ============================================================

def init_database() -> None:
    Base.metadata.create_all(engine)
    # 【修改：按天规划】 首次升级先备份并复制旧数据；原表和原数据库文件保留。
    from migrate_daily_plans import migrate_legacy, migrate_optional_minutes
    migrate_legacy(DB_PATH)
    # 【修改：时长选填】升级旧表的非空约束，历史数据保持不变。
    migrate_optional_minutes(DB_PATH)
    print(f"[OK] 数据库初始化完成：{DB_PATH}")


if __name__ == "__main__":
    init_database()