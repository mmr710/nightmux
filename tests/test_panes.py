#!/usr/bin/env python3
"""Classifier corpus: a captured pane, and the state nightmux must read from it.

Every fault this file guards against was found the same way — a human noticed
silence, hours later. The pane is the only input the classifier gets, the TUIs it
reads change without notice, and a wrong answer is invisible: a busy pane read as
idle gets a queued prompt typed into a running turn, and an idle one read as
waiting swallows everything the user types and nudges for an answer nobody owes.

Add a case whenever an agent's TUI surprises you: capture the pane, trim to the
last ~25 lines the classifier looks at, strip anything private, and name the file
<what>.<expected state>.txt. Reconstructed chrome is fine and often better —
what is under test is the shape of the TUI, never the content of your repo.

    python3 tests/test_panes.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402

PANES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panes")


def cases():
    """(name, expected, lines) from panes/<name>.<expected>.txt."""
    for fn in sorted(os.listdir(PANES)):
        if not fn.endswith(".txt"):
            continue
        name, expected, _ = fn.rsplit(".", 2)
        with open(os.path.join(PANES, fn)) as f:
            yield name, expected, f.read().splitlines()


def main():
    seen, bad = set(), []
    for name, expected, lines in cases():
        got = nightmux.pane_state(lines)
        seen.add(expected)
        if got != expected:
            bad.append(f"  {name}: expected {expected}, got {got}")
            for l in lines[-25:]:
                for label, rx in (("BUSY", nightmux.BUSY), ("WAITING", nightmux.WAITING)):
                    if rx.search(l):
                        bad.append(f"      {label} matched: {l.strip()[:90]!r}")

    # A corpus that has drifted to one state stops testing the classifier and
    # starts agreeing with it.
    missing = {"busy", "idle", "waiting"} - seen
    if missing:
        bad.append(f"  corpus covers no {', '.join(sorted(missing))} case")

    if bad:
        print("pane corpus FAILED", *bad, sep="\n")
        return 1
    print(f"pane corpus ok ({len(list(cases()))} panes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
