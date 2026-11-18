"""test_share: cut from the old monolithic selfcheck() (the last part)."""
import html
import os
import queue
import re
import sys
import tempfile
import threading
import time
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_teleport_harvest_vibe_and_share():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        # !teleport, !harvest, !vibe, and OpenGraph Share Studio (/share, /share/card.svg)
        with tempfile.TemporaryDirectory() as tdir:
            os.makedirs(os.path.join(tdir, ".git"), exist_ok=True)
            tcfg = {"topics": {"11": "tp"}, "started": {"11": "claude"}, "dirs": {"11": tdir},
                    "agents": {"claude": ["/bin/sh", ""], "codex": ["/bin/sh", ""]}}
            tstate = {"tp": {"last": "refactor auth middleware", "mode": "idle",
                             "changed": time.time() - 300,
                             "snap": {"ts": time.time(),
                                      "five_hour": {"used_percentage": 52,
                                                    "resets_at": time.time() + 1800}}}}
            tlk = threading.Lock()
            tsent = []
            with nightmux.stubbed(switch_agent=lambda c, s, l, t, k: (c["topics"].__setitem__(t, "tp-" + k)
                                                             or c["started"].__setitem__(t, k)
                                                             or f"→ {k}"),
                         has_session=lambda s: True, pane=lambda s: ["✓ tests pass"],
                         save_queue=lambda s: None, save_cfg=lambda c: None,
                         sav_add=lambda k, n=1: None,
                         send=lambda c, t, x, mode="mono", buttons=None, quiet=False: tsent.append((x, buttons))):
                hpath, hbody = nightmux.teleport_packet(tcfg, tstate, "11", "tp")
                assert hpath and os.path.isfile(hpath) and "refactor auth middleware" in hbody, hbody
                out_tp = nightmux.teleport_cmd(tcfg, tstate, tlk, "11", "tp", "codex finish edge cases")
                assert "context teleported from claude → codex" in out_tp, out_tp
                assert "finish edge cases" in tstate["tp-codex"]["queue"][0], tstate["tp-codex"]
                # !harvest add, status, and harvest_tick
                h_add = nightmux.harvest_cmd(tcfg, tstate, tlk, "11", "tp-codex", "add write missing auth tests")
                assert "queued harvest task #1" in h_add, h_add
                h_cap = nightmux.harvest_cmd(tcfg, tstate, tlk, "11", "tp-codex", "ceiling 80")
                assert "80%" in h_cap, h_cap
                tstate["tp-codex"] = {"mode": "idle", "changed": time.time() - 300, "queue": []}
                nightmux.harvest_tick(tcfg, tstate, tlk)
                assert tstate["tp-codex"]["queue"] == ["write missing auth tests"], tstate["tp-codex"]
                assert any("quota harvest" in m for m, _ in tsent), tsent
                nightmux.vibe_cmd(tcfg, tstate, "11", "tp-codex")
                assert any("vibe cockpit" in m for m, _ in tsent), tsent
            svg_ = nightmux.share_card_svg(tcfg, {"tokens": ["14.2M"], "saved": ["41%"], "prompts": ["128"]})
            assert "<svg" in svg_ and "14.2M" in svg_ and "41%" in svg_, svg_[:200]
            with nightmux.stubbed(wrapped_data=lambda c, d: {"cells": [("14.2M", "TOKENS CRUNCHED")],
                                                    "agents": ["claude"], "projects": [("a", 1)],
                                                    "split": [], "hours": [0] * 24, "insights": []}):
                sp_ = nightmux.share_page_html(tcfg, {"days": ["30"]}, "https://demo.example.com")
                assert 'property="og:image"' in sp_ and 'name="twitter:card"' in sp_, sp_[:400]
                assert "navigator.canShare" in sp_ and "demo.example.com/share/card.svg" in sp_, sp_[:600]
            assert "AT API LIST PRICES" not in svg_ and "$677" in nightmux.share_card_svg(tcfg, {"tokens": ["1M"], "usd": ["$677"]})
            # the card's query follows the labels, not the order: the dollar cell sits second
            with nightmux.stubbed(wrapped_data=lambda c, d: {"cells": [("14.2M", "TOKENS CRUNCHED"), ("$677", "AT API LIST PRICES"),
                                                              ("41%", "SAVED FROM THE ABYSS (5.0M)"),
                                                              ("2.0M", "SAVED VIA SMART ROUTING"),
                                                              ("128", "VIBE DIRECTIVES ISSUED")],
                                                    "agents": ["claude"], "projects": [("a", 1)],
                                                    "split": [], "hours": [0] * 24, "insights": []}):
                cq_ = urllib.parse.parse_qs(html.unescape(re.search(
                    r'/share/card\.svg\?([^"]+)"', nightmux.share_page_html(tcfg, {"days": ["30"]}, "https://d.example.com")).group(1)))
                assert [cq_[k] for k in ("tokens", "usd", "saved", "lighter", "prompts")] == [
                    ["14.2M"], ["$677"], ["41%"], ["2.0M"], ["128"]], cq_
            assert "url=https%3A%2F%2Fd.uguu.se%2Fx.png" in nightmux.reddit_url("my recap", "https://d.uguu.se/x.png")
