#!/usr/bin/env python3
"""Office page smoke test: the 3D renderer must draw a big fleet without throwing.

The 3D office is a software renderer inside a Python string, so nothing else
checks it: a typo, or one desk state it cannot draw, shows up as a blank page on
somebody's phone (the "keeps flickering" and "queued chip" crashes both did).
This loads the real page in headless Chromium with a 27-room fleet in every
state, draws many frames while orbiting the camera, and fails on any JS error.
Skips (exit 0) when there is no node/chromium, so it never blocks a laptop.

    python3 tests/test_office.py
"""
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.argv = ["nightmux"]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402

BUDGET_MS = 400   # generous: shared CI runners have no GPU. Real cost is ~20-40 ms.


def fleet():
    rnd = random.Random(3)
    states = ["busy", "idle", "waiting", "limit", "shell", "unknown", "gone"]
    rooms = []
    for i in range(27):
        desks = [{"agent": rnd.choice(["claude", "codex", "agy", "opencode"]),
                  "state": states[(i + j) % len(states)], "session": "s%d_%d" % (i, j),
                  "since": rnd.randint(0, 3000), "prog": rnd.random(),
                  "queued": rnd.choice([0, 0, 2, 4]), "live": j == 0}
                 for j in range(rnd.randint(1, 4))]
        rooms.append({"topic": str(100 + i), "name": "proj%d" % i, "desks": desks})
    return {"rooms": rooms, "installed": [], "usage": {}, "servers": []}


PROBE = """<script>window.addEventListener('load',function(){var out=document.body;try{
data=%s;var t=[];for(var i=0;i<30;i++){V3.cam.yaw+=.05;var a=performance.now();
V3.draw(frame+i*.5,Object.assign({clock:'03:10'},sky()));t.push(performance.now()-a)}
t.sort(function(a,b){return a-b});out.setAttribute('data-b','OK '+t[15].toFixed(1))}
catch(e){out.setAttribute('data-b','ERR '+e+' '+(e.stack||'').slice(0,300))}})</script>"""


def main():
    node, chrome = shutil.which("node"), None
    for c in ("chromium-browser", "chromium", "google-chrome", "google-chrome-stable"):
        chrome = chrome or shutil.which(c)
    if not (node and chrome):
        print("office render: skipped (needs node and chromium)")
        return 0
    html = nightmux.OFFICE_HTML
    with tempfile.TemporaryDirectory() as d:
        # 1. every embedded script must parse
        for n, s in enumerate(re.findall(r"<script>(.*?)</script>", html, re.S)):
            p = os.path.join(d, "s%d.js" % n)
            open(p, "w").write(s)
            r = subprocess.run([node, "--check", p], capture_output=True, text=True)
            assert r.returncode == 0, "script %d: %s" % (n, r.stderr[:400])
        # 2. real render in a browser
        page = html.replace("</body>", PROBE % json.dumps(fleet()) + "</body>")

        class H(BaseHTTPRequestHandler):
            def do_GET(s):
                api = s.path.split("?")[0] == "/api/office"
                b = (json.dumps(fleet()) if api else page).encode()
                s.send_response(200)
                s.send_header("Content-Type", "application/json" if api else "text/html")
                s.send_header("Content-Length", str(len(b)))
                s.end_headers()
                s.wfile.write(b)

            def log_message(*a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            r = subprocess.run(
                [chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
                 "--user-data-dir=" + os.path.join(d, "prof"), "--window-size=1280,800",
                 "--dump-dom", "http://127.0.0.1:%d/?view=3d" % srv.server_port],
                capture_output=True, text=True, timeout=90)
        finally:
            srv.shutdown()
        m = re.search(r'data-b="([^"]*)', r.stdout)
        assert m, "probe never ran (page did not load): " + r.stderr[-300:]
        res = m.group(1)
        assert res.startswith("OK"), "3D render threw: " + res
        ms = float(res.split()[1])
        assert ms < BUDGET_MS, "3D draw median %.0f ms > %d ms" % (ms, BUDGET_MS)
        print("office render ok (median %.0f ms, 27 rooms)" % ms)
    return 0


if __name__ == "__main__":
    sys.exit(main())
