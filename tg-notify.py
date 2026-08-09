#!/usr/bin/env python3
"""Claude Code Notification hook: push a permission prompt the instant it appears.

The watcher finds prompts by scraping, which costs a poll interval plus a
stability check — up to ten seconds when a session has been quiet. This fires
the moment Claude Code decides it needs you, so the phone buzzes first and the
buttons are already there.

Drops a stamp file so the watcher knows not to announce the same prompt again.
Never blocks the session: every failure path exits 0.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tgctl  # noqa: E402  (same dir; reuses the config + send helpers)

# "Claude is waiting for your input" fires on a 60s idle timer, not on a prompt.
# The watcher already reports an idle session; repeating it here is only noise.
IDLE = "waiting for your input"


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    msg = (payload.get("message") or "").strip()
    if IDLE in msg.lower():
        return
    sess = subprocess.run(("tmux", "display-message", "-p", "#S"),
                          capture_output=True, text=True).stdout.strip()
    if not sess:
        return
    try:
        cfg = tgctl.load_cfg()
    except OSError:
        return
    topic = next((t for t, s in cfg.get("topics", {}).items() if s == sess), None)
    if not topic:
        return
    lines = tgctl.visible(sess)
    os.makedirs(tgctl.STATE_DIR, exist_ok=True)
    stamp = os.path.join(tgctl.STATE_DIR, f".notify-{sess}")
    open(stamp, "w").close()   # claim this prompt before sending, never after
    body = "\n".join(tgctl.strip_noise(lines[-15:], verbose=True)).strip()
    tgctl.send(cfg, topic, f"🟠 needs input {sess}\n{msg}\n{body}".strip(),
               buttons=tgctl.menu_buttons(lines))


def selfcheck():
    assert IDLE in "Claude is waiting for your input"
    assert IDLE not in "Claude needs your permission to use Bash".lower()
    print("tg-notify selfcheck ok")


if __name__ == "__main__":
    selfcheck() if "--selfcheck" in sys.argv else main()
