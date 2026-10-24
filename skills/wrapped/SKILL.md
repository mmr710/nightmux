---
name: wrapped
description: What the coding agents on this machine (Claude Code, Codex, OpenCode, Antigravity) did over the last days and what those tokens would cost at API list prices, with one card to keep and one to share. Use when the user asks about their agent usage, token spend or cost, or for a "wrapped".
argument-hint: "[days: 1-365, default 30]"
---

Run this with the Bash tool, from the home folder so the two cards are written there and not into a repository:

```
cd ~ && python3 "${CLAUDE_PLUGIN_ROOT}/nightmux.py" wrapped [days]
```

`days` is a whole number from 1 to 365, taken from the request; leave it out for 30. If the request has something else, ask for a number instead of passing it on. Request: $ARGUMENTS

Show the summary as printed, in a code block. Then give both card paths in full: `nightmux-wrapped-share` shows projects only as counts and is the one that is fine to post; `nightmux-wrapped` names them. Without Chromium the cards are web pages to open and screenshot.

The dollar figure is the same tokens at public list prices. A subscription bills differently, so it is a size, not an invoice. Everything is read from transcripts already on this machine, and nothing is uploaded.
