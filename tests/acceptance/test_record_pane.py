#!/usr/bin/env python3
"""T3.2  `nightmux record-pane <session> <state> [slug]`: a fixture in one command.

The pane corpus is the moat and the easiest first PR there is, if capturing one
does not mean hand-trimming and hand-redacting. This is the pure half; the CLI
wraps it around `tmux capture-pane`.
"""
import os
import sys
import tempfile

from _h import cli, need, nightmux, run

PANE = [f"line {i}" for i in range(40)] + [
    "cwd /home/alice/work/secret-client-app",
    "mail alice.smith@example.com",
    "key sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789",
    "gh ghp_abcdefghijklmnopqrstuvwxyz0123456789",
    "bot 123456789:" "AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw",   # split: keeps secret scanners quiet
    "╭──────────────╮",
    "│ Do you want to proceed?  1. Yes  2. No │",
    "╰──────────────╯",
]


def test_writes_redacted_fixture():
    pane_fixture = need("pane_fixture", "T3.2")
    dest = tempfile.mkdtemp(prefix="nm-acc-")
    path = pane_fixture(PANE, "claude", "Proceed Menu!", "waiting", dest, home="/home/alice")
    assert os.path.basename(path) == "claude_proceed_menu.waiting.txt", path
    text = open(path, encoding="utf-8").read()
    for leak in ("alice", "example.com", "sk-ant-", "ghp_", "AAHdqTcv", "secret-client-app"):
        assert leak not in text, f"{leak!r} survived redaction"
    assert "Do you want to proceed?" in text, "the TUI chrome is what is under test: keep it"
    assert len(text.splitlines()) <= 25, "trim to the last 25 lines the classifier reads"
    assert "line 0" not in text


def test_rejects_bad_input():
    pane_fixture = need("pane_fixture", "T3.2")
    dest = tempfile.mkdtemp(prefix="nm-acc-")
    for agent, slug, state in (("claude", "x", "sleeping"), ("../etc", "x", "idle"),
                               ("claude", "", "idle"), ("nosuchagent", "x", "idle")):
        try:
            pane_fixture(PANE, agent, slug, state, dest)
        except ValueError:
            continue
        raise AssertionError(f"accepted agent={agent!r} slug={slug!r} state={state!r}")
    assert os.listdir(dest) == []


def test_refuses_to_overwrite():
    pane_fixture = need("pane_fixture", "T3.2")
    dest = tempfile.mkdtemp(prefix="nm-acc-")
    pane_fixture(PANE, "codex", "menu", "waiting", dest)
    try:
        pane_fixture(PANE, "codex", "menu", "waiting", dest)
    except FileExistsError:
        return
    raise AssertionError("a second capture silently replaced a reviewed fixture")


def test_says_when_classifier_disagrees():
    pane_fixture = need("pane_fixture", "T3.2")
    dest = tempfile.mkdtemp(prefix="nm-acc-")
    path = pane_fixture(["working", "esc to interrupt"], "claude", "spin", "busy", dest)
    assert nightmux.pane_state(open(path).read().splitlines()) == "busy", "redaction changed what the classifier reads"


def test_cli_usage():
    need("pane_fixture", "T3.2")
    r = cli("record-pane")
    assert r.returncode == 2 and "usage: nightmux record-pane" in r.stderr


if __name__ == "__main__":
    sys.exit(run([test_writes_redacted_fixture, test_rejects_bad_input, test_refuses_to_overwrite,
                  test_says_when_classifier_disagrees, test_cli_usage]))
