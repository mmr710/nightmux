import os
import json
import sqlite3
import time

base = os.path.dirname(os.path.abspath(__file__))
now_ms = int(time.time() * 1000)

# 1. opencode_v1.db
v1_path = os.path.join(base, "opencode_v1.db")
if os.path.exists(v1_path):
    os.remove(v1_path)
con = sqlite3.connect(v1_path)
con.execute("CREATE TABLE session (id TEXT PRIMARY KEY, directory TEXT, time_created INTEGER)")
con.execute("CREATE TABLE message (id TEXT PRIMARY KEY, session_id TEXT, time_created INTEGER, data TEXT)")
con.execute("CREATE TABLE part (id TEXT PRIMARY KEY, message_id TEXT, data TEXT)")

con.execute("INSERT INTO session VALUES ('s1', '/projects/app-v1', ?)", (now_ms - 100000,))

msg_user = json.dumps({"role": "user", "id": "m1"})
con.execute("INSERT INTO message VALUES ('m1', 's1', ?, ?)", (now_ms - 80000, msg_user))
part_user = json.dumps({"type": "text", "text": "add endpoint", "synthetic": False})
con.execute("INSERT INTO part VALUES ('p1', 'm1', ?)", (part_user,))

msg_asst = json.dumps({
    "role": "assistant",
    "modelID": "claude-sonnet-4-5",
    "tokens": {"input": 1400, "output": 250, "cache": {"read": 3000, "write": 200}, "reasoning": 50}
})
con.execute("INSERT INTO message VALUES ('m2', 's1', ?, ?)", (now_ms - 60000, msg_asst))
con.commit()
con.close()

# 2. opencode_v2.db (session_v2 and session_message schema)
v2_path = os.path.join(base, "opencode_v2.db")
if os.path.exists(v2_path):
    os.remove(v2_path)
con = sqlite3.connect(v2_path)
con.execute("CREATE TABLE session_v2 (id TEXT PRIMARY KEY, directory TEXT, time_created INTEGER, time_updated INTEGER)")
con.execute("CREATE TABLE session_message (id TEXT PRIMARY KEY, session_id TEXT, time_created INTEGER, data TEXT)")

con.execute("INSERT INTO session_v2 VALUES ('s2', '/projects/app-v2', ?, ?)", (now_ms - 120000, now_ms - 50000))

msg2_user = json.dumps({"role": "user", "content": "refactor database client", "id": "m2_1"})
con.execute("INSERT INTO session_message VALUES ('m2_1', 's2', ?, ?)", (now_ms - 90000, msg2_user))

msg2_asst = json.dumps({
    "role": "assistant",
    "model": "gpt-5-turbo",
    "tokens": {"input": 2100, "output": 450, "cache": {"read": 5000, "write": 0}, "reasoning": 80}
})
con.execute("INSERT INTO session_message VALUES ('m2_2', 's2', ?, ?)", (now_ms - 70000, msg2_asst))
con.commit()
con.close()

# 3. agy_summaries.db
agy_path = os.path.join(base, "agy_summaries.db")
if os.path.exists(agy_path):
    os.remove(agy_path)
con = sqlite3.connect(agy_path)
con.execute("CREATE TABLE conversation_summaries (conversation_id TEXT PRIMARY KEY, step_count INTEGER, workspace_uris TEXT, last_user_input_time TEXT, last_modified_time TEXT)")
iso_now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
con.execute("INSERT INTO conversation_summaries VALUES ('c123', 5, 'file:///projects/agy-demo', ?, ?)", (iso_now, iso_now))
con.commit()
con.close()
print("Generated fixtures successfully.")
