import re

with open("nightmux.py", "r") as f:
    content = f.read()

# Add reddit_url
if "def reddit_url" not in content:
    content = content.replace("def tweet_url(text):\n    return \"https://x.com/intent/post?text=\" + urllib.parse.quote(text)",
    "def tweet_url(text):\n    return \"https://x.com/intent/post?text=\" + urllib.parse.quote(text)\n\ndef reddit_url(text):\n    return \"https://www.reddit.com/submit?title=\" + urllib.parse.quote(\"My AI coding agents worked the night shift!\") + \"&text=\" + urllib.parse.quote(text)")

# Update !wrapped buttons
content = content.replace('buttons=kb([[("🐦 post it", tweet_url(', 'buttons=kb([[("🐦 X (attach photo!)", tweet_url(')
content = content.replace('f"{REPO_URL} #ClaudeCode #vibecoding"))]]))', 'f"{REPO_URL} #ClaudeCode #vibecoding")), ("👽 Reddit (attach photo!)", reddit_url(f"My AI coding agents, last {days} days: {top}. Run by nightmux {REPO_URL}"))]]))')

# Update !reel buttons
content = content.replace('buttons=kb([[("🐦 post it", tweet_url(', 'buttons=kb([[("🐦 X (attach GIF!)", tweet_url(')
content = content.replace('f" — run by nightmux {REPO_URL} #ClaudeCode"))]]))', 'f" — run by nightmux {REPO_URL} #ClaudeCode")), ("👽 Reddit (attach GIF!)", reddit_url("My AI agents worked the night shift: " + "; ".join(cap[1:3] or [name]) + f" — run by nightmux {REPO_URL}"))]]))')

with open("nightmux.py", "w") as f:
    f.write(content)
