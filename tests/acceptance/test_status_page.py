#!/usr/bin/env python3
"""T4.1  A public page that says which agents nightmux reads correctly today.

The nightly drift guard already knows. Publishing it makes a page other people
link to when an agent's TUI changes, and it is the proof behind "ten agents".
"""
import os
import sys

from _h import ROOT, run

sys.path.insert(0, os.path.join(ROOT, "tests"))

ROWS = [
    {"agent": "claude", "version": "2.9.1", "expected": "waiting", "got": "waiting"},
    {"agent": "codex", "version": "0.99.0", "expected": "waiting", "got": "idle"},
    {"agent": "qwen", "version": "<script>alert(1)</script>", "expected": "unknown", "got": "unknown"},
]


def _page():
    import live_agents
    if not hasattr(live_agents, "status_html"):
        raise AssertionError("T4.1 not built: tests/live_agents.py has no status_html(rows, when)")
    return live_agents.status_html(ROWS, when="2026-11-11 04:00 UTC")


def test_rows_and_states():
    page = _page()
    assert page.lstrip().lower().startswith("<!doctype html"), "a whole page, not a fragment"
    for r in ROWS[:2]:
        assert r["agent"] in page and r["version"] in page
    assert "2026-11-11 04:00 UTC" in page
    assert page.count('class="ok"') == 2 and page.count('class="drift"') == 1, "one row per agent, drift marked"


def test_escapes_and_is_self_contained():
    page = _page()
    assert "<script>alert(1)</script>" not in page, "version strings come from other people's binaries: escape them"
    assert "http://" not in page and "src=" not in page, "no external assets: it is served from docs/ as is"


def test_workflow_publishes_it():
    wf = open(os.path.join(ROOT, ".github", "workflows", "drift-guard.yml")).read()
    assert "docs/status.html" in wf, "drift-guard.yml never writes docs/status.html"
    assert "contents: write" in wf or "peter-evans/create-pull-request" in wf or "gh pr create" in wf, \
        "the workflow needs a way to land the page"


if __name__ == "__main__":
    sys.exit(run([test_rows_and_states, test_escapes_and_is_self_contained, test_workflow_publishes_it]))
