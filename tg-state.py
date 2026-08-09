#!/usr/bin/env python3
"""Status-line sidecar: park what Claude Code tells the status line where tgctl reads it.

The status line payload is the only place that carries the 5-hour usage window,
the context percentage and the transcript path together with the cwd. One line
added to the user's status line script therefore turns three of tgctl's guesses
into facts: what is being worked on, how much window is left, and where the
exact conversation text lives.

Keyed by session_id rather than tmux session so the hot path spawns nothing;
tgctl matches a snapshot to a pane by cwd. Prints nothing and swallows every
error: a status line that fails is a status line the user has to debug.
"""
import json
import os
import sys
import time

STATE_DIR = os.path.expanduser("~/.tgctl-state")


def snapshot(d):
    rl = d.get("rate_limits") or {}
    cw = d.get("context_window") or {}
    return {"ts": time.time(),
            # The pane this Claude runs in, straight out of the inherited env —
            # exact, and free. Matching on cwd instead binds the wrong session
            # when two run in one directory, or when an agy session inherits a
            # directory Claude once worked in.
            "pane": os.environ.get("TMUX_PANE"),
            "cwd": d.get("cwd") or (d.get("workspace") or {}).get("current_dir"),
            "transcript": d.get("transcript_path"),
            "model": (d.get("model") or {}).get("display_name"),
            "ctx_pct": cw.get("used_percentage"),
            "five_hour": rl.get("five_hour"),
            "seven_day": rl.get("seven_day")}


def write(sid, snap):
    os.makedirs(STATE_DIR, exist_ok=True)
    path = os.path.join(STATE_DIR, f"{sid}.json")
    with open(path + ".tmp", "w") as f:
        json.dump(snap, f)
    os.replace(path + ".tmp", path)   # a reader never sees a half-written file
    return path


def main():
    try:
        d = json.load(sys.stdin)
        if d.get("session_id"):
            write(d["session_id"], snapshot(d))
    except Exception:
        pass


def selfcheck():
    snap = snapshot({
        "session_id": "abc", "cwd": "/tmp/x", "transcript_path": "/t/abc.jsonl",
        "model": {"display_name": "Opus 5"},
        "context_window": {"used_percentage": 41.5},
        "rate_limits": {"five_hour": {"used_percentage": 88, "resets_at": 1}}})
    assert snap["cwd"] == "/tmp/x" and snap["transcript"] == "/t/abc.jsonl"
    os.environ["TMUX_PANE"] = "%7"
    assert snapshot({"cwd": "/x"})["pane"] == "%7"
    del os.environ["TMUX_PANE"]
    assert snapshot({"cwd": "/x"})["pane"] is None   # outside tmux: simply unbound
    assert snap["five_hour"]["used_percentage"] == 88 and snap["ctx_pct"] == 41.5
    assert snap["seven_day"] is None          # absent windows stay absent
    assert snapshot({"workspace": {"current_dir": "/w"}})["cwd"] == "/w"
    p = write("selfcheck", snap)
    with open(p) as f:
        assert json.load(f)["model"] == "Opus 5"
    os.remove(p)
    print("tg-state selfcheck ok")


if __name__ == "__main__":
    selfcheck() if "--selfcheck" in sys.argv else main()
