#!/usr/bin/env python3
"""
nightmux_milestones.py - GitHub Star Tracker & Celebrator

A lightweight, zero-dependency script to monitor GitHub repository stars.
When a new milestone (e.g. 50, 100, 150 stars) is reached, it automatically
broadcasts a celebratory message to the Nightmux Telegram chat.

Usage: Run manually or via cron daily to track milestones.
"""
import json
import os
import urllib.request

CFG_PATH = os.path.expanduser(os.environ.get("NIGHTMUX_CONFIG", "~/.nightmux.json"))
STATE_PATH = os.path.expanduser("~/.nightmux_stars_state.json")
MILESTONE_INTERVAL = 50

def get_stars():
    req = urllib.request.Request("https://api.github.com/repos/mmr710/nightmux")
    # GitHub requires a user-agent
    req.add_header('User-Agent', 'nightmux-milestone-tracker')
    try:
        resp = urllib.request.urlopen(req, timeout=10).read()
        data = json.loads(resp)
        return data.get("stargazers_count", 0)
    except Exception as e:
        print("Failed to get stars:", e)
        return None

def send_telegram(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print("Failed to send telegram:", e)

def main():
    if not os.path.exists(CFG_PATH):
        print(f"No nightmux config found at {CFG_PATH}.")
        return
        
    with open(CFG_PATH) as f:
        cfg = json.load(f)
        
    token = cfg.get("token")
    chat_id = cfg.get("chat_id")
    
    if not token or not chat_id:
        print("Incomplete config (missing token or chat_id).")
        return

    stars = get_stars()
    if stars is None:
        return
        
    print(f"Current stars: {stars}")
    
    last_milestone = 0
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            last_milestone = json.load(f).get("last_milestone", 0)
            
    current_milestone = (stars // MILESTONE_INTERVAL) * MILESTONE_INTERVAL
    
    if current_milestone > last_milestone and current_milestone > 0:
        msg = f"🎉 <b>Nightmux Milestone Reached!</b> 🎉\nWe just crossed <b>{current_milestone} stars</b> on GitHub (Currently at {stars})!\n\nThank you for your support! Let's get to 500! ⭐\nhttps://github.com/mmr710/nightmux"
        send_telegram(token, chat_id, msg)
        
        # Save new milestone
        with open(STATE_PATH, 'w') as f:
            json.dump({"last_milestone": current_milestone}, f)
        print(f"Announced milestone: {current_milestone}")
    else:
        print("No new milestone.")

if __name__ == "__main__":
    main()
