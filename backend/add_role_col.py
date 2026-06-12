import sqlite3
import os

db_path = os.path.join(os.environ["APPDATA"], "AgentOrchestrator", "agent_orchestrator.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("PRAGMA table_info(users)")
cols = [row[1] for row in c.fetchall()]

if "role" not in cols:
    c.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'operator'")
    conn.commit()
    print("Added role column")
else:
    print("role already exists")

conn.close()
