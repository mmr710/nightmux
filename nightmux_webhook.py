#!/usr/bin/env python3
"""
nightmux_webhook.py - CI/CD Auto-Fixer Webhook Listener

Listens for webhooks (e.g., from GitHub Actions when a build fails).
Automatically spawns a new Claude Code tmux session via Nightmux to investigate.
"""
import json
import os
import subprocess
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

CFG_PATH = os.path.expanduser(os.environ.get("NIGHTMUX_CONFIG", "~/.nightmux.json"))
PORT = 9090

def send_telegram(text):
    if not os.path.exists(CFG_PATH): return
    with open(CFG_PATH) as f:
        cfg = json.load(f)
    token = cfg.get("token")
    chat_id = cfg.get("chat_id")
    if not token or not chat_id: return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try: urllib.request.urlopen(req, timeout=10)
    except Exception as e: print("Telegram error:", e)

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            payload = json.loads(post_data.decode('utf-8'))
        except json.JSONDecodeError:
            payload = {}

        # Parse GitHub payload
        if "pull_request" in payload and payload.get("action") in ["opened", "reopened", "synchronize"]:
            pr_num = payload["pull_request"]["number"]
            repo_name = payload["repository"]["name"]
            clone_url = payload["repository"]["clone_url"]
            msg = f"👀 <b>PR Auto-Reviewer</b>\nNew or updated PR #{pr_num} in {repo_name}.\nSpawning agent to review the code!"
            send_telegram(msg)
            
            # Spawn tmux session that clones repo, checks out PR, and starts agent
            workspace = f"/tmp/{repo_name}_pr_{pr_num}"
            cmd = f"git clone {clone_url} {workspace} && cd {workspace} && gh pr checkout {pr_num} && echo 'Ready to review' && $SHELL"
            subprocess.Popen(["tmux", "new-session", "-d", "-s", f"PR_Review_{pr_num}", cmd])
            
        else:
            repo_name = payload.get("repository", {}).get("name", "UnknownRepo")
            msg = f"🔴 <b>CI/CD Alert: Build Failed in {repo_name}!</b>\n\nI have automatically spawned an AI agent to investigate."
            send_telegram(msg)
            
            subprocess.Popen([
                "tmux", "new-session", "-d", "-s", f"AutoFix_{repo_name}", "echo 'Investigating build failure...'; $SHELL"
            ])

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status": "ok"}')

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', PORT), WebhookHandler)
    print(f"Nightmux Webhook Auto-Fixer listening on port {PORT}...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
