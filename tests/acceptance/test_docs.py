#!/usr/bin/env python3
"""T1.3  The README sells one thing, and nothing in it is stale.

Three guards that stay green forever after: the first command a visitor sees is
the zero-config one, every !command the README names exists, every repo link
resolves.
"""
import os
import re
import sys

from _h import ROOT, nightmux, run

README = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
MAX_LINES = 220          # 354 on 2026-11-11; the long tail moves to docs/GUIDE.md


def _known():
    md = nightmux.commands_md()
    known = set(re.findall(r"`(![a-z0-9_-]+)", md))
    known |= {"!" + k for k in nightmux.AGENTS} | {"!help"}
    return known


def test_first_command_is_zero_config():
    block = re.search(r"```(?:bash|sh|console)?\n(.*?)```", README, re.S)
    assert block, "no code block in the README"
    first = block.group(1).strip().splitlines()[0].lstrip("$ ").strip()
    assert first.startswith(("uvx nightmux run ", "uvx nightmux wrapped")), \
        f"first command a visitor sees is {first!r}; it must run with no bot, token or clone"
    assert README.find(block.group(0)) < README.find("## "), "the command belongs above the first heading"


def test_length():
    n = README.count("\n")
    assert n <= MAX_LINES, f"README is {n} lines, cap {MAX_LINES}"


def test_commands_exist():
    known = _known()
    named = set(re.findall(r"`(![a-z][a-z0-9_-]*)", README))
    gone = sorted(named - known)
    assert not gone, f"README names commands that do not exist: {gone}"


def test_repo_links_resolve():
    bad = []
    for path in re.findall(r"github\.com/mmr710/nightmux/blob/main/([^)#\s\"]+)", README) + \
            re.findall(r"raw\.githubusercontent\.com/mmr710/nightmux/main/([^)#\s\"]+)", README) + \
            re.findall(r"\]\((?!https?:|#|mailto:)([^)#\s]+)", README):
        if not os.path.exists(os.path.join(ROOT, path)):
            bad.append(path)
    assert not bad, f"links to files that are not in the repo: {sorted(set(bad))}"


def test_one_sentence_pitch():
    head = README.split("## ")[0]
    bullets = [l for l in head.splitlines() if l.lstrip().startswith(("- ", "* "))]
    assert len(bullets) <= 3, f"{len(bullets)} bullets above the first heading; the pitch is one sentence and at most 3"


if __name__ == "__main__":
    sys.exit(run([test_first_command_is_zero_config, test_length, test_commands_exist,
                  test_repo_links_resolve, test_one_sentence_pitch]))
