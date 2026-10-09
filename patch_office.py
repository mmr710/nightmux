import re
import os

with open("nightmux.py", "r") as f:
    content = f.read()

def repl(m):
    return """
    fresh = max(snaps, key=lambda s: s.get("ts", 0), default={})   # account-wide
    
    # Extract models and mocked limits for agy and opencode
    usage = {k: (window(fresh, k) or {}).get("used_percentage") for k in ("five_hour", "seven_day")}
    try:
        import json, os
        # agy
        agy_set = os.path.expanduser("~/.gemini/antigravity-cli/settings.json")
        if os.path.exists(agy_set):
            with open(agy_set) as f:
                usage["agy_model"] = json.load(f).get("modelSelection", "Unknown")
        else: usage["agy_model"] = "Unknown"
        usage["agy_limit"] = 100 # Mock limit
        
        # opencode
        oc_set = os.path.expanduser("~/.config/opencode/opencode.json")
        if os.path.exists(oc_set):
            with open(oc_set) as f:
                usage["oc_model"] = json.load(f).get("model", "Unknown")
        else: usage["oc_model"] = "Unknown"
        usage["oc_limit"] = 100 # Mock limit
    except:
        pass

    return {"rooms": rooms, "installed": installed_agents(cfg), "now": now, "looks": cfg.get("looks") or {},
            "usage": usage}
"""

content = re.sub(r'fresh = max\(snaps, key=lambda s: s\.get\("ts", 0\), default=\{\}\).*?for k in \("five_hour", "seven_day"\)\}\}', repl, content, flags=re.DOTALL)
with open("nightmux.py", "w") as f:
    f.write(content)
