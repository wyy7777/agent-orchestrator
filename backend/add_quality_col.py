import sqlite3
import os

db_path = os.path.join(os.environ["APPDATA"], "AgentOrchestrator", "agent_orchestrator.db")
print(f"DB: {db_path}")

conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("PRAGMA table_info(step_executions)")
cols = [row[1] for row in c.fetchall()]
print(f"Existing cols: {cols}")

if "quality_score" not in cols:
    c.execute("ALTER TABLE step_executions ADD COLUMN quality_score TEXT")
    conn.commit()
    print("Added quality_score column")
else:
    print("quality_score already exists")

conn.close()
print("Done")
