#!/usr/bin/env python3
"""T2.1  Commands live in a registry, not in an 800-line if-chain.

handle() was 804 lines and 116 branches on 2026-11-11. A contributor adding a
command should write one decorated function; help text, docs/COMMANDS.md and the
read-only gate come from the same entry.

MAX_HANDLE is a ratchet: each migration PR lowers it, the last one sets it to 120.
"""
import inspect
import re
import sys

from _h import need, nightmux, run

MAX_HANDLE = 804
# Ratchets for the migration PRs (T2.1 a-e). Final values: MAX_HANDLE 120,
# MIN_COMMANDS 80, MAX_UNMIGRATED 0.
MIN_COMMANDS = 11
MAX_UNMIGRATED = 75


def test_registry_shape():
    C = need("COMMANDS", "T2.1")
    assert isinstance(C, dict) and len(C) >= MIN_COMMANDS, f"{len(C)} commands registered, expected at least {MIN_COMMANDS}"
    for name, c in C.items():
        assert re.fullmatch(r"![a-z0-9_-]+", name), f"bad command name {name!r}"
        assert callable(c.fn), f"{name}: fn is not callable"
        assert c.help and "=" not in c.help[:1], f"{name}: no help line"
        assert c.section, f"{name}: no section"
        assert isinstance(c.writes, bool) or callable(c.writes), f"{name}: writes must be bool or (arg)->bool"


def test_docs_come_from_registry():
    C = need("COMMANDS", "T2.1")
    documented = set(re.findall(r"^- `(![a-z0-9_-]+)", nightmux.commands_md(), re.M))
    missing = sorted(d for d in documented if d not in C and d != "!<agent>")
    assert len(missing) <= MAX_UNMIGRATED, f"{len(missing)} documented but not registered, cap {MAX_UNMIGRATED}: {missing}"
    silent = sorted(n for n, c in C.items() if not getattr(c, "hidden", False)
                    and getattr(c, "alias_of", None) is None and n not in documented)
    assert not silent, f"registered but undocumented (mark hidden=True or give help): {silent}"


def test_aliases_resolve():
    C = need("COMMANDS", "T2.1")
    for name, c in C.items():
        target = getattr(c, "alias_of", None)
        if target:
            assert target in C and getattr(C[target], "alias_of", None) is None, f"{name} -> {target}"
    assert C["!doc"].fn is C["!doctor"].fn, "!doc is an alias of !doctor today; keep it"


def test_readonly_gate_uses_registry():
    C = need("COMMANDS", "T2.1")
    cfg = {"topics": {}, "modes": {}}
    for name, c in C.items():
        w = c.writes if isinstance(c.writes, bool) else None
        if w is not None:
            assert nightmux.writes(cfg, name, "") == w, f"writes() disagrees with the registry on {name}"
    assert nightmux.writes(cfg, "fix the bug", "") is True, "plain text is typed into the session: a write"
    assert nightmux.writes(cfg, "!status", "") is False


def test_handle_is_a_dispatcher():
    need("COMMANDS", "T2.1")
    n = len(inspect.getsource(nightmux.handle).splitlines())
    assert n <= MAX_HANDLE, f"handle() is {n} lines, cap {MAX_HANDLE}"


if __name__ == "__main__":
    sys.exit(run([test_registry_shape, test_docs_come_from_registry, test_aliases_resolve,
                  test_readonly_gate_uses_registry, test_handle_is_a_dispatcher]))
