# database.py
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import sqlite3
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
def init_database() -> None:
    Base.metadata.create_all(engine)
    # 【修改：按天规划】 首次升级先备份并复制旧数据；原表和原数据库文件保留。
    

    # 【修改：时长选填】升级旧表的非空约束，历史数据保持不变。
    migrate_optional_minutes(DB_PATH)
    print(f"[OK] 数据库初始化完成：{DB_PATH}")


class Base(DeclarativeBase):
    pass



def migrate_optional_minutes(db_path):
    import re
    db_path = Path(db_path)
    
    with sqlite3.connect(db_path) as db:
        columns = list(db.execute('PRAGMA table_info(daily_tasks)'))
        
        if not any(c[1] == 'estimated_minutes' and c[3] for c in columns):
            return
        backup = db_path.with_name(db_path.name + '.before_optional_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.bak')
        
        with sqlite3.connect(backup) as target:
            db.backup(target)
        sql = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='daily_tasks'").fetchone()[0]
        indexes = [r[0] for r in db.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='daily_tasks' AND sql IS NOT NULL")]
        sql = sql.replace('CREATE TABLE daily_tasks', 'CREATE TABLE daily_tasks_optional', 1)
        sql = re.sub(r'(estimated_minutes\s+INTEGER)\s+NOT NULL', r'\1', sql, flags=re.I)
        db.execute('PRAGMA foreign_keys=OFF')
        
        try:
            db.execute('BEGIN IMMEDIATE')
            db.execute(sql)
            db.execute('INSERT INTO daily_tasks_optional SELECT * FROM daily_tasks')
            db.execute('DROP TABLE daily_tasks')
            db.execute('ALTER TABLE daily_tasks_optional RENAME TO daily_tasks')
            
            for statement in indexes:
                db.execute(statement)
            
            if db.execute('PRAGMA foreign_key_check').fetchone():
                raise RuntimeError('时长选填迁移外键检查失败')
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.execute('PRAGMA foreign_keys=ON')