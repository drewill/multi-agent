# 【修改：按天规划】 新增文件：迁移前自动备份，复制旧计划/任务/复盘并保持旧ID。
"""复制旧单日数据到新表，保留 ID、历史记录及旧表；操作前自动备份。"""
from pathlib import Path
from datetime import datetime
import json
import sqlite3

def migrate_legacy(db_path):
    db_path=Path(db_path)
    with sqlite3.connect(db_path) as db:
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)')
        
        if db.execute("SELECT 1 FROM schema_migrations WHERE name='daily_tasks_v1'").fetchone(): return
        names={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        old=[dict(r) for r in db.execute('SELECT * FROM plans ORDER BY id')] if 'plans' in names else []
        
        if old:
            if db.execute('SELECT COUNT(*) FROM daily_plans').fetchone()[0]:
                raise RuntimeError('新表已有数据但未记录迁移，请先核对备份，不能自动合并')
            backup=db_path.with_name(db_path.name+'.before_daily_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.bak')
            with sqlite3.connect(backup) as target: db.backup(target)
            print(f'[OK] 旧数据库备份：{backup}')
        # 【修改：按天规划】备份完成后才进入写事务，迁移失败时自动回滚。
        db.execute('BEGIN IMMEDIATE')
        by_id={p['id']:p for p in old}
        
        def root(p):
            seen=set()
            while p.get('parent_plan_id') in by_id:
                if p['id'] in seen: raise RuntimeError('旧计划版本存在循环')
                seen.add(p['id']);p=by_id[p['parent_plan_id']]
            return p['id']
        
        for p in old:
            daily=json.dumps([{'plan_date':p['plan_date'],'available_minutes':p['available_minutes']}])
            db.execute('INSERT INTO daily_plans (id,conversation_id,group_key,parent_plan_id,goal,start_date,end_date,daily_budgets,warnings,status,change_reason,created_at,confirmed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (p['id'],p['conversation_id'],f"legacy-{root(p)}",None,p['goal'],p['plan_date'],p['plan_date'],daily,'[]',p['status'],p.get('change_reason'),p['created_at'],p.get('confirmed_at')))
        
        for p in old:
            if p.get('parent_plan_id') is not None: db.execute('UPDATE daily_plans SET parent_plan_id=? WHERE id=?',(p['parent_plan_id'],p['id']))
        
        tasks=[dict(r) for r in db.execute('SELECT * FROM tasks ORDER BY id')] if old and 'tasks' in names else []
        
        for t in tasks:
            db.execute('INSERT INTO daily_tasks (id,plan_id,source_task_id,plan_date,title,expected_output,estimated_minutes,actual_minutes,position,status,note,created_at,completed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (t['id'],t['plan_id'],None,by_id[t['plan_id']]['plan_date'],t['title'],t['expected_output'],t['estimated_minutes'],t.get('actual_minutes'),t['position'],t['status'],t.get('note'),t['created_at'],t.get('completed_at')))
        for t in tasks:
            if t.get('source_task_id') is not None: db.execute('UPDATE daily_tasks SET source_task_id=? WHERE id=?',(t['source_task_id'],t['id']))
        
        if old and 'reviews' in names:
            db.execute('INSERT INTO daily_reviews (id,plan_id,feedback,task_snapshot,result,created_at) SELECT id,plan_id,feedback,task_snapshot,result,created_at FROM reviews')
        db.execute("INSERT INTO schema_migrations VALUES ('daily_tasks_v1',?)",(datetime.now().isoformat(),))
        
        if db.execute('PRAGMA foreign_key_check').fetchone(): raise RuntimeError('迁移外键验证失败')
        db.commit()

# 【修改：时长选填】SQLite create_all不会修改旧列，备份后重建任务表以允许NULL。
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

if __name__=='__main__':
    from datasets import init_database
    init_database()
