"""The relay hands a managed bot's token over exactly once. Run: python3 tests/test_relay.py"""
import os, sys, threading, time, urllib.request
sys.argv = ["n"]
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import nightmux as n

asked = []


def fake(cfg, m, **k):
    asked.append(m)
    if m == "getUpdates":
        if len(asked) > 1:
            time.sleep(30)
        return {"ok": True, "result": [{"update_id": 1, "managed_bot": {"bot": {"id": 9, "username": "nm1_bot"}}}]}
    return {"ok": True, "result": "9:TOK"}


n.api = fake
os.environ["NIGHTMUX_MANAGER_TOKEN"] = "x"
threading.Thread(target=n.relay_serve, args=(9877,), daemon=True).start()
time.sleep(1)
assert n.claim_managed_bot("http://127.0.0.1:9877", "nm1_bot", timeout=10) == "9:TOK"
try:
    urllib.request.urlopen("http://127.0.0.1:9877/claim?u=nm1_bot")
    raise SystemExit("claimed twice")
except urllib.error.HTTPError as e:
    assert e.code == 404
print("relay ok")
