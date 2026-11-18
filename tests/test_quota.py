"""test_quota: !quota readers, account discovery, no network, no real agy."""
import json
import os
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402

FIX = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "agy-usage.txt")).read()
KEYS = ("sk-SECRET-zai", "ghu_SECRET_copilot")


def _stub_agy(monkey):
    real = nightmux.subprocess.run
    monkey.append(lambda: setattr(nightmux.subprocess, "run", real))
    calls = []
    nightmux.subprocess.run = lambda argv, **kw: (
        calls.append((argv, (kw.get("env") or {}).get("HOME"))) or
        subprocess.CompletedProcess(argv, 0, FIX, ""))
    return calls


def test_agy_parse_all_rows():
    undo = []
    with isolated(nightmux):
        try:
            _stub_agy(undo)
            rows = nightmux._agy_read()
            assert len(rows) == 5
            assert rows[0]["window"] == "7d" and rows[0]["pct"] == 97
            assert rows[3]["disabled"] and rows[3]["pct"] is None and rows[3]["window"] == "5h"
            assert rows[4]["group"] == "Gemini 4 Argon" and rows[4]["resets_at"] == "2026-11-21T13:53:31Z"
            assert nightmux._agy_usage["pct"] == 1 and nightmux._agy_usage["claude_pct"] == 0
        finally:
            [u() for u in undo]


def test_accounts_and_report_with_fake_home():
    undo, h = [], None
    with isolated(nightmux) as iso:
        try:
            h = iso.home
            tok = os.path.join(h, ".ai-profiles", "agy1", ".gemini", "antigravity-cli")
            os.makedirs(tok)
            os.makedirs(os.path.join(h, ".ai-profiles", "agy2"))      # not signed in
            os.makedirs(os.path.join(h, ".ai-profiles", "opencode1"))
            os.makedirs(os.path.join(h, ".ai-profiles", "other"))
            open(os.path.join(tok, "antigravity-oauth-token"), "w").write("x")
            oc = os.path.join(h, ".local", "share", "opencode")
            os.makedirs(oc)
            json.dump({"zai": {"key": KEYS[0]}, "github-copilot": {"refresh": KEYS[1]},
                       "opencode-go": {"key": "k"}, "weird": {"key": "k"}},
                      open(os.path.join(oc, "auth.json"), "w"))
            now_ms = int(time.time() * 1000)
            c = sqlite3.connect(os.path.join(oc, "opencode.db"))
            c.execute("create table session_message (time_created int, type text, data text)")
            c.execute("insert into session_message values (?, 'assistant', ?)",
                      (now_ms, json.dumps({"cost": 1.5, "model": {"providerID": "opencode-go"}})))
            c.execute("insert into session_message values (?, 'assistant', ?)",
                      (now_ms, json.dumps({"cost": 9, "model": {"providerID": "other"}})))
            c.commit(); c.close()
            assert [a[0] for a in nightmux.quota_accounts()] == ["agy", "opencode", "agy1", "agy2", "opencode1"]

            urls = []

            def fake_get(url, hdr):
                urls.append((url, hdr))
                if "copilot" in url:
                    return {"quota_snapshots": {"premium": {"remaining": 30, "entitlement": 300, "percent_remaining": 10.0}},
                            "quota_reset_date": "2026-12-01"}
                return {"success": True, "data": {"limits": [{"type": "TOKENS_LIMIT", "percentage": 6, "nextResetTime": 1795000000000}]}}
            nightmux._quota_get = fake_get
            calls = _stub_agy(undo)
            nightmux._quota["rows"] = {}
            nightmux._quota["tried"] = time.time()          # no real thread in the test
            assert "refreshing" in nightmux.quota_report()
            nightmux._quota_refresh()
            out = nightmux.quota_report()
            print(out)
            assert [c[1] for c in calls] == [h, tok.split("/.gemini")[0]]   # default + signed-in agy1 only
            assert "agy1" in out and "agy1        Gemini 4 Argon" in out and "7d   94% left  resets 21 Nov 13:53" in out
            assert "agy2        agy" in out and "not signed in" in out
            assert "disabled" in out and "no quota API known" in out
            assert "zai" in out and "94% left" in out and "premium" in out and "30/300 left" in out
            assert "$1.50 used" in out and "$9" not in out
            for url, hdr in urls:       # each key goes only to its own provider
                assert (KEYS[0] in str(hdr)) == ("z.ai" in url) and (KEYS[1] in str(hdr)) == ("github.com" in url)
            assert not any(k in out for k in KEYS)
            nightmux._quota_get = lambda url, hdr: {"_err": "HTTPError 401"}
            errs = nightmux.opencode_limits()
            assert any("error HTTPError 401" in r["note"] for r in errs) and not any(k in str(errs) for k in KEYS)
        finally:
            [u() for u in undo]
            nightmux._quota["rows"] = {}
