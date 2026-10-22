<div align="center">

<img src="docs/nightmux-logo.jpg" alt="nightmux logo" width="200" height="200">

# 🌙 nightmux

**Your AI coding agents keep working while you sleep.**

Drive Claude Code, Codex, Gemini, agy, opencode, Cursor, Amp, Goose and Qwen Code
from your phone. Usage limit at 2am? Your queue waits and resumes the moment the
window resets — or hands the work to another agent.

[![GitHub stars](https://img.shields.io/github/stars/mmr710/nightmux?style=social)](https://github.com/mmr710/nightmux/stargazers)
[![tests](https://github.com/mmr710/nightmux/actions/workflows/test.yml/badge.svg)](https://github.com/mmr710/nightmux/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/nightmux.svg)](https://pypi.org/project/nightmux/)
[![license](https://img.shields.io/github/license/mmr710/nightmux)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-2496ED?logo=docker&logoColor=white)](https://github.com/mmr710/nightmux/pkgs/container/nightmux)
[![Android](https://img.shields.io/badge/android-APK-3DDC84?logo=android&logoColor=white)](https://github.com/mmr710/nightmux/releases/latest/download/nightmux.apk)
[![Python](https://img.shields.io/badge/python-3.8%E2%80%933.13-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![deps](https://img.shields.io/badge/dependencies-0-brightgreen)](pyproject.toml)
[![Telegram](https://img.shields.io/badge/Telegram-Community-blue.svg?logo=telegram)](https://t.me/+SGmmExdMHTQ3OWVk)

[Website](https://mmr710.github.io/nightmux/) · [Live demo](https://mmr710.github.io/nightmux/office.html?demo) · [Leaderboard](https://mmr710.github.io/nightmux/leaderboard.html) · [Install](#install)

![The night shift in the office: claude hits its limit at 02:14 and hands the work to codex, agy asks and gets a yes from your phone, and at 04:11 the window resets and claude is back](docs/office-demo.gif)

</div>

## Quickstart

1. `curl -fsSL https://raw.githubusercontent.com/mmr710/nightmux/main/install.sh | sh`
2. Create the bot: scan the QR it prints (quickest; the new token passes through the maintainer's [onboarding relay](SECURITY.md#the-qr-onboarding-relay)), or press Enter and paste a token from [@BotFather](https://t.me/BotFather) (nothing leaves your machine). No token at all runs dashboard-only.
3. In a topic (or **+ project** on the dashboard): `!new myproj ~/code/myproj`, then just type.

No install? `uvx --from git+https://github.com/mmr710/nightmux nightmux --setup` (or `pipx run --spec git+https://github.com/mmr710/nightmux nightmux --setup`).

Just looking? `python3 nightmux.py --demo` and open http://127.0.0.1:8099/office — no bot, no keys.
Docker, a fresh VPS and the rest: [Install →](#install)

## How it compares

nightmux is one of several ways to reach a coding agent from your phone, and not the biggest. The others, and where to look first:

- **[Happy](https://github.com/slopus/happy)** (MIT, 24k★) and **[HAPI](https://github.com/tiann/hapi)** (AGPL-3.0, 5k★) are apps for Claude Code, Codex and more, with communities far larger than this one. If you want an app rather than a chat bot, start there.
- **[ccbot](https://github.com/six-ddc/ccbot)** and **[ccgram](https://github.com/alexei-led/ccgram)** bridge Telegram topics to tmux sessions, the same shape as nightmux's core. If a bridge is all you want, try them first.
- **[claude-auto-resume](https://github.com/terryso/claude-auto-resume)** is a shell script that resumes Claude Code when a usage limit lifts. nightmux does the same inside a bigger tool.
- **[claude-squad](https://github.com/smtg-ai/claude-squad)** manages several terminal agents at once, from the terminal.
- **Anthropic's own** Remote Control and Telegram channel plugin reach a Claude Code session with no third-party code. If Claude Code is the only agent you use, start there.

What nightmux is for is the overnight layer across agents: a queue that waits out usage limits or hands the work to another agent, schedules, `!goal` loops that run your tests until they pass, a morning briefing, and a dashboard with an office view. The cost is size: the daemon is a single file of about 20,000 lines, from one maintainer.

## The night shift

```
02:14  ⏸ api hit the usage limit
       5-hour window spent — resumes 04:11, resuming itself with 'continue'
04:11  ▶️ api resumed · sending queued prompt
04:11  ⚙️ api
```

A usage limit at 2am used to end the night. The turn dies mid-refactor, the
prompt that started it is already spent, and the session sits there until
someone awake types `continue`. nightmux reads the reset time, holds everything
you send, and puts the work back the moment the window reopens — including the
turn the limit cut off. You read the result at breakfast.

The rest is what makes it usable:

Run **Claude Code from your phone** — or Codex, Gemini, aider, anything with a
prompt. One Telegram forum topic per project, one tmux session behind it. Text
you send is typed into that session's prompt; what the session says comes back
to the topic. Approvals arrive as tap buttons.

No container, no DNS, no certificates, no ports open. It attaches to tmux
sessions you already have, on the machine you already use. Messages travel
through Telegram's servers; nightmux runs none of its own in that path.
Python standard library only, nothing to `pip install`.

![What a night looks like: the limit hits at 02:14, nightmux resumes the turn at 04:11, and the one approval waits for breakfast](docs/demo.svg)

```
   Telegram group (Topics on)          your machine
   ┌───────────────────────┐          ┌──────────────────────────┐
   │ #api      ────────────┼──────────┼─► tmux: api    → claude  │
   │ #frontend ────────────┼──────────┼─► tmux: web    → claude  │
   │ #scratch  ────────────┼──────────┼─► tmux: scratch→ claude  │
   └───────────────────────┘          └──────────────────────────┘
              ▲                                    │
              └──── output, approvals, usage ──────┘
```

## What's in the box

| | |
|---|---|
| 🌙 **Overnight** | resumes after usage limits · `!at` / `!every` schedules · `!shift` and `!plan` step queues · `!goal` loops until tests pass · morning briefing |
| 🤝 **Several agents** | Claude Code, Codex, agy, opencode, Gemini, Cursor, Amp, Goose, Qwen, aider · one topic, a bench of agents · `!failover` · `!consult` · `!pair` reviews · `!race` |
| 💸 **Tokens** | live context % and limit windows · `!cost` · `!ctx` · auto-compact · `!stats` with what to change · `!saved` · `!wrapped` card |
| 🔧 **Code** | `!git` / `!diff` / `!undo` snapshots · issues in, PRs out · CI and preview watchers · dependency health |
| 👀 **See it** | dashboard · chat PWA · pixel-art office · Android app with alerts and a widget · GIF of the night |
| 🖥 **Two servers** | one bot, several machines; move a topic between them |
| 🧩 **Yours** | stdlib only, no dependencies · plugins · webhook API · runs without Telegram |

The [guide](docs/GUIDE.md) walks through each one; [COMMANDS.md](docs/COMMANDS.md) lists every command.

## Install

The fastest way to install is using the one-line installer:
```bash
curl -fsSL https://raw.githubusercontent.com/mmr710/nightmux/main/install.sh | sh
```
*(Clones — or updates — `~/nightmux` from GitHub and runs setup. Adding a
second server? Use the command its dashboard gives you instead: servers →
**+ add server**.)*

**Just looking?** `python3 nightmux.py --demo` serves the office with a made-up night — no bot, no keys.

**Docker** (tmux, Claude Code and Codex inside; your code mounted at `/code`):
```bash
docker run -it --name nightmux -v nightmux-home:/root -v ~/code:/code \
  -p 127.0.0.1:9090:9090 ghcr.io/mmr710/nightmux
docker exec -it nightmux claude      # log the agent in once
```
The dashboard trusts this machine and your tailnet — keep the port on `127.0.0.1` (or behind `tailscale serve`), never on the open internet. See [SECURITY.md](SECURITY.md).

**A fresh VPS** (Hetzner, DigitalOcean, Vultr…): paste
[`deploy/cloud-init.yaml`](deploy/cloud-init.yaml) into the provider's user-data
box, then SSH in, log the agents in and run the one-liner above.

Or from PyPI (may lag behind GitHub — the peer and dashboard features need
the current version):
```bash
pipx install nightmux
nightmux --setup
```

Or install the latest development version directly from GitHub:
```bash
pipx install git+https://github.com/mmr710/nightmux
nightmux --setup
```

or clone it, which is the version to pick if you want the source where you can
read and edit it — there are only four files and no dependencies:

```bash
git clone https://github.com/mmr710/nightmux ~/nightmux
python3 ~/nightmux/nightmux.py --setup
```

Setup walks the whole thing: BotFather token, finding your group, writing the
allowlist, wiring the Claude Code hooks, installing the service (a systemd user
unit on Linux, a launchd agent on macOS). It is idempotent — re-run it after an
upgrade.

You will be asked to create a Telegram group with **Topics** turned on and add
the bot as an **admin**. Admin is not optional: without it the bot only receives
messages addressed to it, so most of what you type never arrives.

Then, in a new topic:

```
!new api ~/code/api      # start a session and bind this topic to it
```

and type. `!help` lists the rest.

## What it feels like

```
you   fix the failing auth test
bot   ⚙️ api  · Opus 5 · 34% ctx
bot   🔧 Bash  pytest tests/test_auth.py -x
bot   🔧 Read  src/auth.py
bot   🟠 needs input api
      Bash(git commit -m "fix token expiry check")
      [ 1. Yes ] [ 2. Yes, don't ask again ] [ 3. No ]
you   (taps 1)
bot   ✅ api
      Token expiry used `<` instead of `<=`, so a token expiring exactly on the
      boundary was rejected. Fixed and committed; the test passes.
```

Approvals arrive the moment Claude Code asks, via its `Notification` hook —
before the terminal has finished redrawing.

## Commands

Everything is `!cmd` (the common ones also `/cmd`); anything else is typed into the
agent. `!help` in Telegram is a menu of eight sections. The ones you'll use first:

| | |
|---|---|
| `!new <name> <dir>` | start a session here with your default agent |
| `!codex` / `!agy` / `!opencode` … | add that agent to this topic, or switch to it |
| `@agy <text>` | one prompt to one agent, without switching |
| `!goal <check>` | after every turn run the check; failures go back until it passes |
| `!shift` | one prompt per line: a plan that runs overnight |
| `!at 03:00 <prompt>` | start work while you sleep |
| `!usage` / `!cost` / `!stats` | limit windows, spend, and what to change |
| `!undo` | roll back the agent's last turn |
| `!wrapped` | a card of your month: tokens, projects, when you code |

All of them: [docs/COMMANDS.md](docs/COMMANDS.md).

## Docs

- [Guide](docs/GUIDE.md): every feature, the config, how it works
- [Commands](docs/COMMANDS.md): generated from `!help`, so it is never out of date
- [Architecture](ARCHITECTURE.md) · [Security](SECURITY.md) · [Cookbook](cookbook/README.md) · [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md) · [Roadmap](ROADMAP.md)

## Community & Support

**Join the Community:** Connect with other users, share your overnight agent successes, and get help in our [Telegram Group](https://t.me/+SGmmExdMHTQ3OWVk).

**Support the Project:** If `nightmux` saves you time or money, consider supporting its development! ☕

### 💳 Donate Crypto (USDT on TRX Network)
**Address:** `TG2GZhZHg5N892M3nEzRdqpbDSVT2BffwN`
<br><img src="docs/usdt-qr.png" alt="USDT TRX QR Code" width="150">

## Requirements

Python 3.8+ (CI runs 3.8 through 3.13), tmux, a terminal coding agent, and Linux
with systemd (the service is optional — `python3 nightmux.py` in a terminal works
fine). Claude Code gets the hooks and the usage numbers; everything else runs on
the terminal scrape.

## Security

**The bot token is a shell on your machine, and `allow_users` is the only thing
between a stranger and your sessions.** Read [SECURITY.md](SECURITY.md) before
you add a second person or a second machine. It is short.

What that means in practice:

- **Nothing is exposed by default.** The dashboard binds `127.0.0.1`; phones reach it through your tailnet or a pairing QR.
- **Only you can drive it.** Telegram messages from anyone not in `allow_users` are ignored.
- **Risky approvals stay human.** `!autoyes` is opt-in per topic and never presses yes on `rm -rf`, `sudo`, `git push`, `curl | sh`, `--force` or publish dialogs (`!policy` tunes this).
- **Spend is capped.** `!budget` and `!spendcap` stop runaway loops; `!cost top` shows where it went.
- **The QR shortcut in setup trusts the maintainer.** The relay passes your new bot's token to your terminal once, from memory, with no logs and no disk copy — but it runs on a machine you can't audit, so paste a BotFather token instead if that matters ([details](SECURITY.md#the-qr-onboarding-relay)).
- **Zero dependencies.** Standard library only, so nothing third-party to audit. The daemon itself is a single file of about 20,000 lines.

## License

MIT. Changes are in [CHANGELOG.md](CHANGELOG.md).
