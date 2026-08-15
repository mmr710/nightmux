#!/usr/bin/env python3
"""Claude Code Stop hook: push the final assistant message to its Telegram topic.

Cleaner than scraping the TUI — exact text, no chrome, no idle guessing. Only
fires for tmux sessions bound to a topic in ~/.nightmux.json; anything else exits
silently. Touching ~/.nightmux-hooked/<session> tells nightmux.py to stop scraping
replies for this session, so nothing is delivered twice.

Never blocks the session: every failure path exits 0.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nightmux  # noqa: E402  (same dir; reuses the config + send helpers)


def last_assistant_text(transcript_path):
    text = ""
    with open(transcript_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("type") != "assistant":
                continue
            blocks = (rec.get("message") or {}).get("content") or []
            if isinstance(blocks, str):
                chunk = blocks
            else:
                chunk = "\n".join(b.get("text", "") for b in blocks
                                  if isinstance(b, dict) and b.get("type") == "text")
            if chunk.strip():
                text = chunk  # keep the last one that actually said something
    return text.strip()


def tailed(sid):
    """True when the status-line sidecar is running, so nightmux reads this itself."""
    return bool(sid) and os.path.exists(
        os.path.join(nightmux.STATE_DIR, f"{sid}.json"))


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    sess = subprocess.run(("tmux", "display-message", "-p", "#S"),
                          capture_output=True, text=True).stdout.strip()
    if not sess:
        return
    try:
        cfg = nightmux.load_cfg()
    except OSError:
        return
    topic = next((t for t, s in cfg.get("topics", {}).items() if s == sess), None)
    if not topic:
        return
    os.makedirs(nightmux.HOOK_DIR, exist_ok=True)
    open(os.path.join(nightmux.HOOK_DIR, sess), "w").close()  # claim delivery
    text = last_assistant_text(payload.get("transcript_path", ""))
    if text:
        if tailed(payload.get("session_id")):
            return  # nightmux reads the same transcript, and reports the tool trace too
        nightmux.send(cfg, topic, f"✅ {sess}\n{text}", mode="md")
    else:
        # The turn ended and said nothing: /compact, /clear, an interrupt. Both
        # delivery paths key off assistant text, so both stayed silent and the topic
        # kept showing ⚙️ over a pane that was already idle and waiting. That is
        # indistinguishable from a hang, and it is the whole of "I send and get no
        # reply". Closing the turn costs one line and removes the ambiguity.
        nightmux.send(cfg, topic, f"✅ {sess} · turn ended with no message "
                      "(slash command or interrupt) — pane is free", mode="plain")


def selfcheck():
    import tempfile
    p = tempfile.mktemp(suffix=".jsonl")
    with open(p, "w") as f:
        for rec in [
            {"type": "user", "message": {"content": "hi"}},
            {"type": "assistant", "message": {"content": [{"type": "text",
                                                           "text": "first"}]}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash"}]}},   # no text: skipped
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "final answer"},
                {"type": "tool_use", "name": "Read"}]}},
            {"type": "user", "message": {"content": "tool result"}},
            "not json",
        ]:
            f.write((rec if isinstance(rec, str) else json.dumps(rec)) + "\n")
    assert last_assistant_text(p) == "final answer", last_assistant_text(p)
    os.remove(p)
    print("nightmux_stop selfcheck ok")


if __name__ == "__main__":
    selfcheck() if "--selfcheck" in sys.argv else main()
