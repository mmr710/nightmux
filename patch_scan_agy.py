import re

with open("nightmux.py", "r") as f:
    content = f.read()

new_scan_agy = r"""def _scan_agy(stats, home, since):
    import sqlite3
    db = os.path.join(home, ".gemini", "antigravity-cli", "conversation_summaries.db")
    if not os.path.exists(db):
        return
    b = _chat_bucket(stats, "agy")
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2)
    try:
        cut = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(since))
        for cid, steps, ws, last in con.execute("SELECT conversation_id, step_count, workspace_uris, last_user_input_time FROM "
                                     "conversation_summaries WHERE last_modified_time >= ?", (cut,)):
            b["sessions"] += 1
            m = re.search(r"file://(/[^\"',\s]+)", ws or "")
            if m:      # no prompts on disk: a conversation counts once for its project
                n = os.path.basename(urllib.parse.unquote(m.group(1)).rstrip("/"))
                b["projects"][n] = b["projects"].get(n, 0) + 1
            b["requests"] += steps or 0
            
            tf = os.path.join(home, ".gemini", "antigravity-cli", "brain", cid, ".system_generated", "logs", "transcript.jsonl")
            if os.path.exists(tf):
                import json
                try:
                    with open(tf, "r") as f_in:
                        for line in f_in:
                            if "PLANNER_RESPONSE" in line:
                                try:
                                    js = json.loads(line)
                                    if js.get("type") == "PLANNER_RESPONSE":
                                        i = js.get("input_tokens") or 0
                                        cr = js.get("cache_read_tokens") or 0
                                        o = js.get("output_tokens") or 0
                                        _chat_call(b, "agy", i, cr, 0, o, 0)
                                except: pass
                            elif "USER_INPUT" in line:
                                try:
                                    js = json.loads(line)
                                    if js.get("type") == "USER_INPUT":
                                        b["prompts"] += 1
                                        c = js.get("content")
                                        if c: b["prompt_chars"] += len(c)
                                except: pass
                except: pass
    finally:
        con.close()"""

content = re.sub(r'def _scan_agy\(stats, home, since\):.*?finally:\n        con\.close\(\)', lambda m: new_scan_agy, content, flags=re.DOTALL)
with open("nightmux.py", "w") as f:
    f.write(content)
