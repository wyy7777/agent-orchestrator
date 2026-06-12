import sqlite3
import os

db_path = os.path.join(os.environ["APPDATA"], "AgentOrchestrator", "agent_orchestrator.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("PRAGMA table_info(tasks)")
cols = [row[1] for row in c.fetchall()]

if "workflow_snapshot" not in cols:
    c.execute("ALTER TABLE tasks ADD COLUMN workflow_snapshot TEXT")
    conn.commit()
    print("Added workflow_snapshot column")
else:
    print("workflow_snapshot already exists")

conn.close()
