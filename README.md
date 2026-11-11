<div align="center">

<img src="https://raw.githubusercontent.com/mmr710/nightmux/main/docs/nightmux-logo.jpg" alt="nightmux logo" width="160" height="160">

# nightmux

Run Claude, Codex and Gemini overnight. When one hits its limit, another takes over, until your tests pass.

[![PyPI](https://img.shields.io/pypi/v/nightmux.svg)](https://pypi.org/project/nightmux/)
[![tests](https://github.com/mmr710/nightmux/actions/workflows/test.yml/badge.svg)](https://github.com/mmr710/nightmux/actions/workflows/test.yml)
[![deps](https://img.shields.io/badge/dependencies-0-brightgreen)](https://github.com/mmr710/nightmux/blob/main/pyproject.toml)
[![license](https://img.shields.io/github/license/mmr710/nightmux)](https://github.com/mmr710/nightmux/blob/main/LICENSE)

</div>

- **Your check decides when it is done.** After each turn, `--until` runs your shell command; if it fails, the output goes back to the agent. It stops after 20 turns unless you set `--max-turns`.
- **Another agent takes over.** On a usage limit, an exit, or a turn that runs over an hour, the next agent gets a handoff brief of the work so far. Pick them with `--agents`; the default is whatever is installed, Claude first.
- **Nothing to set up.** It needs tmux and an agent CLI. No bot, no keys, no daemon.

<div align="center">
<img src="https://raw.githubusercontent.com/mmr710/nightmux/main/docs/office-demo.gif" width="100%" alt="The full nightmux daemon's office view: claude hits its limit at 02:14, codex takes over, and claude is back at 04:11">
<br><sub>The daemon's office view of a night, one step beyond <code>run</code>. <a href="https://mmr710.github.io/nightmux/#video">48-second video</a></sub>
</div>

```bash
uvx nightmux run "fix the failing tests" --until "npm test"
uvx nightmux run "add input validation" --until "pytest -q" --agents claude,codex --max-turns 10
```

Limits: usage-limit text is recognised for Claude Code only. Other agents fail over when they exit or a turn passes an hour. A permission menu in the agent is reported and waited on, never answered; attach with `tmux attach -t =<session>` to answer it. Exit codes: 0 check passed, 1 max turns, 2 usage, 3 no agent left.

## See what your agents cost first

```bash
uvx nightmux wrapped
```

Reads the logs Claude Code, Codex, OpenCode and Antigravity already keep in your home folder and prints what the last 30 days would have cost at API list prices (`wrapped 7` for a week). Nothing is uploaded. Dollars are list prices, not your invoice. [Details in the guide](docs/GUIDE.md#what-did-your-agents-cost).

## From your phone

`run` is one task in one terminal. For many projects, queues, schedules and a morning briefing, run the daemon and reach it from a phone:

```bash
curl -fsSL https://raw.githubusercontent.com/mmr710/nightmux/main/install.sh | sh
```

- **Telegram:** setup creates the bot (scan the QR it prints, or paste a token from [@BotFather](https://t.me/BotFather)). One topic per project, one tmux session behind it. In a topic: `!new myproj ~/code/myproj`, then type. Approval menus arrive as buttons.
- **Dashboard, no Telegram:** `nightmux up` starts it at http://127.0.0.1:9090. Nothing is opened to the network; for a phone, run `tailscale serve --bg 9090` on a machine with [Tailscale](https://tailscale.com) and tap **+ Pair phone**.

`!goal npm test` is `--until` in the daemon, `!failover codex` hands held work to another agent now, and `!help` lists the rest ([all commands](docs/COMMANDS.md)). Docker, a VPS and other installs: [guide](docs/GUIDE.md#install).

## Agents

Any agent that runs in a terminal works: nightmux types into its tmux pane and reads the screen back.

| Agent | Dialogs it turns into buttons | Usage windows | Tokens and cost | Started every night in CI |
|---|---|---|---|---|
| Claude Code | permissions, menus, folder trust | 5-hour and weekly | ✓ | ✓ |
| Codex | menus | 5-hour and weekly | ✓ | ✓ |
| agy | permissions | ✓ | ✓ | – |
| OpenCode | questions | – | ✓ | ✓ |
| Gemini CLI | folder trust | – | – | ✓ |
| Aider | (Y)es/(N)o questions | – | – | ✓ |
| Qwen Code | not yet | – | – | ✓ |
| Cursor, Amp, Goose | not tested | – | – | – |

The last column is the [drift guard](https://github.com/mmr710/nightmux/actions/workflows/drift-guard.yml): each night CI installs the newest release of each agent and checks how nightmux reads its first screen.

## Security

**The bot token is a shell on your machine, and `allow_users` is the only thing between a stranger and your sessions.**

- Nothing is exposed by default: the dashboard binds 127.0.0.1.
- Messages from anyone not in `allow_users` are ignored.
- `!autoyes` is off unless you turn it on per topic, and it never presses yes on `rm -rf`, `sudo`, `git push`, `curl | sh`, `--force` or publish dialogs.
- Standard library only, no dependencies. The QR setup shortcut trusts the maintainer's relay; paste a BotFather token if that matters. [SECURITY.md](SECURITY.md) is short and covers the rest.

## More

[Guide](docs/GUIDE.md) · [Commands](docs/COMMANDS.md) · [How it compares](docs/COMPARE.md) · [Architecture](ARCHITECTURE.md) · [Cookbook](cookbook/README.md) · [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Roadmap](ROADMAP.md) · [Website](https://mmr710.github.io/nightmux/) · [Telegram community](https://t.me/+SGmmExdMHTQ3OWVk) · [Donate](docs/GUIDE.md#-donate-crypto-usdt-on-trx-network)

MIT. Python 3.8+, tmux, and a terminal coding agent.
