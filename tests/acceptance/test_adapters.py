#!/usr/bin/env python3
"""T3.1  One honest contract per agent, and a README table generated from it.

"Ten agents" is a claim a visitor tests in the first five minutes. An adapter
says what it really does: a reader that is a stub is None, a tier is earned by
fixtures, and the README's table cannot drift from the code.
"""
import ast
import inspect
import os
import sys
import textwrap

from _h import ROOT, need, nightmux, run

KEYS = {"launch", "screen_state", "usage_reader", "limit_reader", "version_cmd", "tier"}
TIERS = ("full", "partial", "basic")
PANES = os.path.join(ROOT, "tests", "panes")


def _is_stub(fn):
    """True for `pass`, `return`, `return []`, `return {}`, `return None` bodies and lambdas."""
    if fn.__name__ == "<lambda>":
        return True
    body = ast.parse(textwrap.dedent(inspect.getsource(fn))).body[0].body
    body = [s for s in body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
    if len(body) != 1:
        return False
    s = body[0]
    if isinstance(s, ast.Pass):
        return True
    return isinstance(s, ast.Return) and (
        s.value is None or (isinstance(s.value, ast.Constant) and s.value.value is None)
        or (isinstance(s.value, (ast.List, ast.Dict, ast.Tuple)) and not getattr(s.value, "elts", getattr(s.value, "keys", []))))


def test_contract():
    for name, ad in nightmux.AGENT_ADAPTERS.items():
        missing = KEYS - set(ad)
        assert not missing, f"{name}: adapter lacks {sorted(missing)} (T3.1)"
        assert ad["tier"] in TIERS, f"{name}: tier {ad['tier']!r}"
        assert set(nightmux.AGENT_ADAPTERS) == set(nightmux.AGENTS), "an agent without an adapter"


def test_no_stub_readers():
    for name, ad in nightmux.AGENT_ADAPTERS.items():
        for key in ("usage_reader", "limit_reader"):
            fn = ad.get(key)
            assert fn is None or not _is_stub(fn), \
                f"{name}.{key} is a stub: set it to None so the table and !tokens can say 'not read'"


def test_tier_is_earned():
    panes = os.listdir(PANES)
    for name, ad in nightmux.AGENT_ADAPTERS.items():
        tier = ad.get("tier")
        states = {p.rsplit(".", 2)[1] for p in panes if p.startswith(name + "_")}
        if tier == "full":
            assert ad["usage_reader"] and ad["limit_reader"], f"{name}: 'full' needs both readers"
            assert {"busy", "idle", "waiting"} <= states, f"{name}: 'full' needs busy, idle and waiting panes, has {sorted(states)}"
        elif tier == "partial":
            assert ad["usage_reader"] or ad["limit_reader"], f"{name}: 'partial' needs one reader"
            assert states, f"{name}: 'partial' needs at least one pane fixture"
    assert nightmux.AGENT_ADAPTERS["claude"].get("tier") == "full", "claude is the reference adapter"


def test_none_readers_do_not_crash_callers():
    limits_for = need("limits_for", "T3.1")     # the one place callers ask; [] when the reader is None
    home = __import__("tempfile").mkdtemp(prefix="nm-acc-")
    for name in nightmux.AGENT_ADAPTERS:
        assert isinstance(limits_for(name, home), list), f"limits_for({name!r}) must return a list"
    stats = {}
    for name, ad in nightmux.AGENT_ADAPTERS.items():
        if ad["usage_reader"]:
            ad["usage_reader"](stats, home, 0)      # an empty home is not an error


def test_readme_table_is_generated():
    agents_md = need("agents_md", "T3.1")
    table = agents_md()
    for name in nightmux.AGENT_ADAPTERS:
        assert f"| {name} " in table or f"| `{name}` " in table, f"{name} missing from agents_md()"
    readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
    assert table.strip() in readme, "README agent table is stale: nightmux --agents-md"


if __name__ == "__main__":
    sys.exit(run([test_contract, test_no_stub_readers, test_tier_is_earned,
                  test_none_readers_do_not_crash_callers, test_readme_table_is_generated]))
