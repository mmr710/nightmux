#!/usr/bin/env python3
"""T1.1  `nightmux run "<task>" --until "<check>" --agents a,b`

The front door: one command, no bot, no daemon, no config. It starts the first
agent in tmux in the current folder, types the task, runs the check after every
turn, feeds failures back, moves to the next agent on a usage limit, and exits 0
when the check passes.
"""
import os
import shutil
import stat
import sys

from _h import cli, fake_home, need, nightmux, run

FAKE_AGENT = """#!/bin/sh
# A stand-in agent: an idle prompt the pane classifier reads, and one "turn" that
# does the work. Sonnet may change the prompt glyph if the classifier needs it,
# never the assertions below.
printf 'fake-agent ready\\n❯ '
while IFS= read -r line; do
  [ -n "$line" ] && touch done.flag && printf 'worked on it\\n'
  printf '❯ '
done
"""


def test_args_parse():
    run_args = need("run_args", "T1.1")
    a = run_args(["fix the failing tests", "--until", "pytest -q", "--agents", "claude,codex"])
    assert a["task"] == "fix the failing tests", a
    assert a["until"] == "pytest -q", a
    assert a["agents"] == ["claude", "codex"], a
    assert a["max_turns"] == 20, "default max_turns is 20"
    assert run_args(["x", "--max-turns", "3"])["max_turns"] == 3
    assert run_args(["x"])["until"] is None, "--until is optional: one turn, then exit 0"
    assert len(run_args(["x"])["agents"]) >= 1, "default: installed agents, claude first"


def test_bad_args_exit_2():
    run_args = need("run_args", "T1.1")
    for bad in ([], ["--until", "true"], ["x", "--agents", "nosuchagent"],
                ["x", "--max-turns", "0"], ["x", "--bogus"]):
        try:
            run_args(bad)
        except SystemExit as e:
            assert e.code == 2, f"{bad}: exit {e.code}, want 2"
        else:
            raise AssertionError(f"{bad} was accepted")


def test_usage_lists_run():
    assert "\n  run " in nightmux.USAGE, "USAGE has no `run` line"
    r = cli("run")
    assert r.returncode == 2 and "usage: nightmux run" in r.stderr, (r.returncode, r.stderr[-200:])


def _fake(home):
    path = os.path.join(home, "fake-agent")
    with open(path, "w") as f:
        f.write(FAKE_AGENT)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    # cfg["agents"] is {key: [launch, resume-flag]}, the shape agents(cfg) reads.
    with open(os.path.join(home, ".nightmux.json"), "w") as f:
        f.write('{"agents": {"fake": ["%s", ""]}}' % path)
    os.chmod(os.path.join(home, ".nightmux.json"), 0o600)
    return path


def test_end_to_end_passes():
    need("run_args", "T1.1")
    if not shutil.which("tmux"):
        print("       (skipped: no tmux)")
        return
    home = fake_home()
    work = os.path.join(home, "proj")
    os.makedirs(work)
    _fake(home)
    r = cli("run", "make the flag", "--until", "test -f done.flag", "--agents", "fake",
            "--max-turns", "3", home=home, cwd=work, timeout=120)
    assert r.returncode == 0, f"exit {r.returncode}\n{r.stdout[-600:]}\n{r.stderr[-600:]}"
    assert os.path.exists(os.path.join(work, "done.flag")), "the agent never got the task"
    assert "✅" in r.stdout and "test -f done.flag" in r.stdout, r.stdout[-300:]
    assert not os.path.exists(os.path.join(home, ".nightmux.offset")), "run must not poll Telegram"


def test_end_to_end_gives_up():
    need("run_args", "T1.1")
    if not shutil.which("tmux"):
        print("       (skipped: no tmux)")
        return
    home = fake_home()
    _fake(home)
    r = cli("run", "anything", "--until", "false", "--agents", "fake", "--max-turns", "1",
            home=home, timeout=120)
    assert r.returncode == 1, f"a check that never passes exits 1, got {r.returncode}"
    assert "max turns" in (r.stdout + r.stderr).lower()


if __name__ == "__main__":
    sys.exit(run([test_args_parse, test_bad_args_exit_2, test_usage_lists_run,
                  test_end_to_end_passes, test_end_to_end_gives_up]))
