#!/usr/bin/env python3
"""T1.4  `nightmux wrapped --json`: the numbers, for other tools and for the share loop.

The card is for people; --json is what a status bar, a blog post or somebody's
dashboard reads. Nothing but JSON on stdout, and no project names unless asked.
"""
import json
import os
import shutil
import sys

from _h import ROOT, cli, fake_home, run


def _home():
    home = fake_home()
    d = os.path.join(home, ".claude", "projects", "-projects-my-web")
    os.makedirs(d)
    shutil.copyfile(os.path.join(ROOT, "tests", "fixtures", "claude_sample.jsonl"),
                    os.path.join(d, "s1.jsonl"))
    return home


def test_json_shape():
    home = _home()
    r = cli("wrapped", "365", "--json", home=home)
    assert r.returncode == 0, f"exit {r.returncode}: {r.stderr[-300:]}"
    try:
        d = json.loads(r.stdout)
    except ValueError:
        raise AssertionError(f"stdout is not JSON alone: {r.stdout[:200]!r}")
    for k in ("days", "version", "tokens", "prompts", "usd", "agents"):
        assert k in d, f"missing key {k!r}: {sorted(d)}"
    assert d["days"] == 365 and d["prompts"] == 2, d
    assert d["agents"]["claude"]["tokens"] > 0, d["agents"]
    assert not [f for f in os.listdir(home) if f.startswith("nightmux-wrapped")], \
        "--json writes no card files"


def test_json_is_private_by_default():
    home = _home()
    out = cli("wrapped", "365", "--json", home=home).stdout
    assert "my-web" not in out, "project names leaked into --json"
    out = cli("wrapped", "365", "--json", "--projects", home=home).stdout
    assert "my-web" in out, "--projects should add them"


def test_flag_order_and_errors():
    home = _home()
    assert cli("wrapped", "--json", "365", home=home).returncode == 0, "flags before the day count"
    assert cli("wrapped", "--jsn", home=home).returncode == 2
    empty = cli("wrapped", "--json")
    assert empty.returncode == 1 and empty.stdout.strip() == "", "no transcripts: exit 1, empty stdout"


if __name__ == "__main__":
    sys.exit(run([test_json_shape, test_json_is_private_by_default, test_flag_order_and_errors]))
