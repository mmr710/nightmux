#!/usr/bin/env python3
"""
nightmux_logwatcher.py - Proactive Error Tailing

Tails a specified log file. If it detects a Traceback or Exception,
it automatically sends a Telegram alert and spawns an AI agent in a tmux 
session to investigate the root cause.
"""
import os
import sys
import time
import subprocess
import json
import urllib.request

CFG_PATH = os.path.expanduser("~/.nightmux.json")

def send_telegram(text):
    if not os.path.exists(CFG_PATH): return
    with open(CFG_PATH) as f: cfg = json.load(f)
    if not cfg.get("token") or not cfg.get("chat_id"): return
    url = f"https://api.telegram.org/bot{cfg['token']}/sendMessage"
    payload = json.dumps({"chat_id": cfg["chat_id"], "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try: urllib.request.urlopen(req, timeout=5)
    except: pass

def watch_log(logfile):
    if not os.path.exists(logfile):
        print(f"Log file {logfile} does not exist.")
        return
    
    print(f"Watching {logfile} for errors...")
    f = open(logfile, "r")
    f.seek(0, os.SEEK_END)
    
    while True:
        line = f.readline()
        if not line:
            time.sleep(1)
            continue
            
        lower_line = line.lower()
        if "traceback" in lower_line or "exception" in lower_line or "error" in lower_line:
            context = [line]
            # Grab the next few lines for context
            for _ in range(15):
                time.sleep(0.1) # Wait for lines to flush
                next_line = f.readline()
                if next_line: context.append(next_line)
                
            error_block = "".join(context)
            msg = f"⚠️ <b>Log Watcher Alert</b>\nDetected an error in <code>{logfile}</code>:\n<pre>{error_block[:500]}</pre>\n\nSpawning agent to investigate..."
            send_telegram(msg)
            
            subprocess.Popen([
                "tmux", "new-session", "-d", "-s", f"Investigator_{int(time.time())}", 
                f"echo 'Investigating error: {error_block[:100]}'; $SHELL"
            ])
            
            print(f"Error detected and agent spawned. Sleeping 60s...")
            time.sleep(60)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 nightmux_logwatcher.py <path_to_log_file>")
        sys.exit(1)
    watch_log(sys.argv[1])
