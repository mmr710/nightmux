<div align="center">

<img src="https://raw.githubusercontent.com/mmr710/nightmux/main/docs/nightmux-logo.jpg" alt="nightmux logo" width="160" height="160">

# nightmux

### Your AI coding agents keep working while you sleep.

Drive **Claude Code, Codex, Gemini, agy, opencode, Cursor, Amp, Goose, Qwen Code** and **aider**
from your phone. Usage limit at 2 AM? Your queue waits and resumes the moment the window
resets, or hands the work to another agent. You wake up to a briefing.

[![GitHub stars](https://img.shields.io/github/stars/mmr710/nightmux?style=social)](https://github.com/mmr710/nightmux/stargazers)
[![tests](https://github.com/mmr710/nightmux/actions/workflows/test.yml/badge.svg)](https://github.com/mmr710/nightmux/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/nightmux.svg)](https://pypi.org/project/nightmux/)
[![Python](https://img.shields.io/badge/python-3.8%E2%80%933.13-3776AB?logo=python&logoColor=white)](https://github.com/mmr710/nightmux/blob/main/pyproject.toml)
[![deps](https://img.shields.io/badge/dependencies-0-brightgreen)](https://github.com/mmr710/nightmux/blob/main/pyproject.toml)
[![license](https://img.shields.io/github/license/mmr710/nightmux)](https://github.com/mmr710/nightmux/blob/main/LICENSE)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-2496ED?logo=docker&logoColor=white)](https://github.com/mmr710/nightmux/pkgs/container/nightmux)
[![Android](https://img.shields.io/badge/android-APK-3DDC84?logo=android&logoColor=white)](https://github.com/mmr710/nightmux/releases/latest/download/nightmux.apk)
[![Telegram](https://img.shields.io/badge/Telegram-Community-blue.svg?logo=telegram)](https://t.me/+SGmmExdMHTQ3OWVk)

**[▶ Watch the video](https://mmr710.github.io/nightmux/#video)** · [Website](https://mmr710.github.io/nightmux/) · [Live demo](https://mmr710.github.io/nightmux/office.html?demo) · [Leaderboard](https://mmr710.github.io/nightmux/leaderboard.html) · [Install](#install) · [Guide](https://github.com/mmr710/nightmux/blob/main/docs/GUIDE.md)

<a href="https://mmr710.github.io/nightmux/#video"><img src="https://raw.githubusercontent.com/mmr710/nightmux/main/docs/promo.gif" width="100%" alt="nightmux in 12 seconds: claude hits its usage limit at 02:14, codex takes over, agy asks and gets a yes with one tap on the phone, claude is back at 04:11, and the morning briefing says 3 tasks done and 2 PRs ready"></a>

<sub>12 seconds of a night. <a href="https://mmr710.github.io/nightmux/#video">The full 48-second video, with sound →</a></sub>

</div>

## Why vibe coders run it

- 🌙 **A usage limit no longer ends the night.** Claude Code runs out of its 5-hour window at 2:14 AM. nightmux keeps your queue and the turn that got cut off, and sends them back the moment the window resets. Can't wait? `!failover codex` hands the work to another agent now.
- 📱 **Your phone is the terminal.** One Telegram topic per project, one tmux session behind it. Approval menus arrive as buttons, so a "yes" is one tap from bed. Photos, files and voice notes go straight to the agent.
- ✅ **It keeps going until the tests pass.** `!goal npm test` runs your check after every turn and sends the failures back. It stops and asks when it goes in circles.
- 🗓 **Plan the whole night.** `!shift` takes one prompt per line and runs them in order. `!at 03:00 <prompt>` and `!every 4h <prompt>` start work while you sleep.
- 🤝 **Every agent you already use.** Ten terminal agents, a bench of them per topic. `!race claude,codex <task>` runs both in their own worktrees and you keep the better one.
- ☀️ **You wake up to a briefing.** What got done, which PRs are ready, which errors came in, and a GIF of the night.
- 💸 **Fewer tokens spent.** Live context %, the limit windows, auto-compact, a fresh session per task, and `!stats` says what to change.
- 🔒 **Yours, entirely.** Python standard library only, zero dependencies, on your machine with your keys. Nothing is exposed by default. MIT.

## Quickstart

1. Install:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/mmr710/nightmux/main/install.sh | sh
   ```
2. Create the bot: scan the QR it prints (quickest; the new token passes through the maintainer's [onboarding relay](https://github.com/mmr710/nightmux/blob/main/SECURITY.md#the-qr-onboarding-relay)), or press Enter and paste a token from [@BotFather](https://t.me/BotFather) (nothing leaves your machine). No token at all runs dashboard-only.
3. In a topic (or **+ project** on the dashboard): `!new myproj ~/code/myproj`, then just type.

No install? `uvx --from git+https://github.com/mmr710/nightmux nightmux --setup` (or `pipx run --spec git+https://github.com/mmr710/nightmux nightmux --setup`).

No Telegram, or want to look first? `nightmux up` (or `uvx --from git+https://github.com/mmr710/nightmux nightmux up`) checks for tmux, starts the dashboard at http://127.0.0.1:9090 and opens it; **+ project** there starts an agent. It opens nothing to your Wi-Fi or the internet, so a phone needs a route: with [Tailscale](https://tailscale.com) on both devices, run `tailscale serve --bg 9090`, then **+ Pair phone** on the dashboard shows the QR. A bot can be added later with `nightmux --setup`.

Just looking? `python3 nightmux.py --demo` and open http://127.0.0.1:8099/office — no bot, no keys.
Docker, a fresh VPS and the rest: [Install →](#install)

## A night with nightmux

![The night shift in the office: claude hits its limit at 02:14 and hands the work to codex, agy asks and gets a yes from your phone, and at 04:11 the window resets and claude is back](https://raw.githubusercontent.com/mmr710/nightmux/main/docs/office-demo.gif)

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

What it feels like from your phone:

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

![What a night looks like: the limit hits at 02:14, nightmux resumes the turn at 04:11, and the one approval waits for breakfast](https://raw.githubusercontent.com/mmr710/nightmux/main/docs/demo.svg)

## How it works

```
   Telegram group (Topics on)          your machine
   ┌───────────────────────┐          ┌──────────────────────────┐
   │ #api      ────────────┼──────────┼─► tmux: api    → claude  │
   │ #frontend ────────────┼──────────┼─► tmux: web    → codex   │
   │ #scratch  ────────────┼──────────┼─► tmux: scratch→ gemini  │
   └───────────────────────┘          └──────────────────────────┘
              ▲                                    │
              └──── output, approvals, usage ──────┘
```

Run **Claude Code from your phone** — or Codex, Gemini, aider, anything with a
prompt. One Telegram forum topic per project, one tmux session behind it. Text
you send is typed into that session's prompt; what the session says comes back
to the topic. Approvals arrive as tap buttons. Rather not use Telegram? The
dashboard and its chat PWA do the same.

No container, no DNS, no certificates, no ports open. It attaches to tmux
sessions you already have, on the machine you already use. Messages travel
through Telegram's servers; nightmux runs none of its own in that path.
Python standard library only, nothing to `pip install`.

## What's in the box

| | |
|---|---|
| 🌙 **Overnight** | resumes after usage limits · `!at` / `!every` schedules · `!shift` and `!plan` step queues · `!goal` loops until tests pass · morning briefing |
| 🤝 **Several agents** | Claude Code, Codex, agy, opencode, Gemini, Cursor, Amp, Goose, Qwen, aider · one topic, a bench of agents · `!failover` · `!consult` · `!pair` reviews · `!race` |
| 💸 **Tokens** | live context % and limit windows · `!cost` · `!ctx` · auto-compact · `!stats` with what to change · `!saved` · `!wrapped` card |
| 🔧 **Code** | `!git` / `!diff` / `!undo` snapshots · issues in, PRs out · CI and preview watchers · dependency health |
| 👀 **See it** | dashboard · chat PWA · 3D office (pixel rooms on tap) · Android app with alerts and a widget · GIF of the night |
| 🖥 **Two servers** | one bot, several machines; move a topic between them |
| 🧩 **Yours** | stdlib only, no dependencies · plugins · webhook API · runs without Telegram |

The [guide](https://github.com/mmr710/nightmux/blob/main/docs/GUIDE.md) walks through each one; [COMMANDS.md](https://github.com/mmr710/nightmux/blob/main/docs/COMMANDS.md) lists every command.

## Agents

Any agent that runs in a terminal works: nightmux types into its tmux pane and reads the screen back. What it reads beyond the prompt and the reply depends on the agent:

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

Claude Code also gets hooks, so its replies and permission prompts arrive the moment they happen; the others' are read off the screen. Every agent's queue waits out a usage-limit message nightmux recognises and resumes at the reset it states. The tests cover Claude Code's limit messages and the capacity errors of Gemini models; another agent's wording may need adding.

The last column is the [drift guard](https://github.com/mmr710/nightmux/actions/workflows/drift-guard.yml). Every night it installs the newest release of each agent, starts it in tmux from an empty home folder and checks how nightmux reads its first screen; each run's summary lists the versions. If a new release reads differently on your machine, an issue with a screenshot is the fastest fix.

## Two tools that need nothing running

### What did your agents cost?

`uvx --from git+https://github.com/mmr710/nightmux nightmux wrapped` (or `python3 nightmux.py wrapped` in a clone) reads the logs Claude Code, Codex, OpenCode and Antigravity already keep in your home folder, and prints what the last 30 days would have cost at API list prices (`wrapped 7` for a week). No bot, no keys, no daemon. It also draws two cards: one with your project names, to keep, and one with counts only, safe to post. Nothing is uploaded.

The dollar figure is the same tokens at the providers' public list prices, dated in the output. A subscription bills differently, so read it as a size, not an invoice. A model with no price in the table is named and left out, never counted as free; `"prices": {"my-model": [input, output, cache read, cache write]}` in `~/.nightmux.json` (dollars per million tokens; the last two are optional) adds a model or overrides a built-in one. The PNG needs Chromium, otherwise you get a web page to screenshot. Drawing a card fetches the Inter and JetBrains Mono fonts from Google Fonts; none of your numbers are in that request.

### Hit a limit mid-task?

`nightmux handoff codex`, run in the repo from any terminal, writes what the last Claude Code or Codex conversation there left behind to `.nightmux/HANDOFF.md` and starts Codex on it: the instruction that was cut off, its last actions and notes, `git status`, the diffstat and the recent commits. The file stays out of `git status` (it goes in `.git/info/exclude`). Say what comes next after the agent's name: `nightmux handoff gemini "finish the tests"`. With no agent it only writes the file and shows it. No install: `uvx --from git+https://github.com/mmr710/nightmux nightmux handoff codex`.

It starts Claude Code, Codex, OpenCode, agy, Gemini and Qwen Code, the ones whose first-prompt flag was checked against their own `--help`; for any other agent it prints the prompt to paste. Only Claude Code and Codex conversations are read, and only Claude Code's give the last actions and notes. After anything else you get the git state and whatever you type after the agent's name. No bot, no keys, no daemon, and nothing leaves your machine except to the agent you named.

### From inside Claude Code

Both also come as a Claude Code plugin:

```
/plugin marketplace add mmr710/nightmux
/plugin install nightmux@nightmux
```

`/nightmux:wrapped` (or `/nightmux:wrapped 7`) prints the report and writes the cards to your home folder. `/nightmux:handoff codex` writes the brief, has Claude add where it stopped, and gives you the line that starts Codex on it in a terminal. Claude also uses them on its own when you ask what your agents cost or to pass the work on. The plugin needs Python 3.8 or newer, and adds no hooks and no MCP server.

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
The dashboard trusts this machine and your tailnet — keep the port on `127.0.0.1` (or behind `tailscale serve`), never on the open internet. See [SECURITY.md](https://github.com/mmr710/nightmux/blob/main/SECURITY.md).

**A fresh VPS** (Hetzner, DigitalOcean, Vultr…): paste
[`deploy/cloud-init.yaml`](https://github.com/mmr710/nightmux/blob/main/deploy/cloud-init.yaml) into the provider's user-data
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
| `!failover <agent>` | out of usage? hand the held work to another agent now |
| `!race claude,codex <task>` | each agent in its own worktree; you keep the winner |
| `!usage` / `!cost` / `!stats` | limit windows, spend, and what to change |
| `!undo` | roll back the agent's last turn |
| `!wrapped` | a card of your month: tokens, projects, when you code |

All of them: [docs/COMMANDS.md](https://github.com/mmr710/nightmux/blob/main/docs/COMMANDS.md).

## How it compares

nightmux is one of several ways to reach a coding agent from your phone, and not the biggest. The others, and where to look first:

| Project | What it is | Start there if |
|---|---|---|
| **[Happy](https://github.com/slopus/happy)** (MIT, 24k★) · **[HAPI](https://github.com/tiann/hapi)** (AGPL-3.0, 5k★) | apps for Claude Code, Codex and more, with communities far larger than this one | you want an app rather than a chat bot |
| **[ccbot](https://github.com/six-ddc/ccbot)** · **[ccgram](https://github.com/alexei-led/ccgram)** | Telegram topics bridged to tmux sessions, the same shape as nightmux's core | a bridge is all you want |
| **[claude-auto-resume](https://github.com/terryso/claude-auto-resume)** | a shell script that resumes Claude Code when a usage limit lifts; nightmux does the same inside a bigger tool | that is the one part you need |
| **[claude-squad](https://github.com/smtg-ai/claude-squad)** | several terminal agents at once, managed from the terminal | you stay at the keyboard |
| **Anthropic's own** Remote Control and Telegram channel plugin | reach a Claude Code session with no third-party code | Claude Code is the only agent you use |

What nightmux is for is the overnight layer across agents: a queue that waits out usage limits or hands the work to another agent, schedules, `!goal` loops that run your tests until they pass, a morning briefing, and a dashboard with an office view. The cost is size: the daemon is a single file of about 20,000 lines, from one maintainer.

## Docs

- [Guide](https://github.com/mmr710/nightmux/blob/main/docs/GUIDE.md): every feature, the config, how it works
- [Commands](https://github.com/mmr710/nightmux/blob/main/docs/COMMANDS.md): generated from `!help`, so it is never out of date
- [Architecture](https://github.com/mmr710/nightmux/blob/main/ARCHITECTURE.md) · [Security](https://github.com/mmr710/nightmux/blob/main/SECURITY.md) · [Cookbook](https://github.com/mmr710/nightmux/blob/main/cookbook/README.md) · [Changelog](https://github.com/mmr710/nightmux/blob/main/CHANGELOG.md)
- [Contributing](https://github.com/mmr710/nightmux/blob/main/CONTRIBUTING.md) · [Roadmap](https://github.com/mmr710/nightmux/blob/main/ROADMAP.md)

## Community & Support

**Join the Community:** Connect with other users, share your overnight agent successes, and get help in our [Telegram Group](https://t.me/+SGmmExdMHTQ3OWVk).

**Support the Project:** If `nightmux` saves you time or money, consider supporting its development! ☕

### 💳 Donate Crypto (USDT on TRX Network)
**Address:** `TG2GZhZHg5N892M3nEzRdqpbDSVT2BffwN`
<br><img src="https://raw.githubusercontent.com/mmr710/nightmux/main/docs/usdt-qr.png" alt="USDT TRX QR Code" width="150">

## Requirements

Python 3.8+ (CI runs 3.8 through 3.13), tmux, a terminal coding agent, and Linux
with systemd (the service is optional — `python3 nightmux.py` in a terminal works
fine). Claude Code gets hooks as well; the
[agent table](https://github.com/mmr710/nightmux#agents) shows what each agent gets.

## Security

**The bot token is a shell on your machine, and `allow_users` is the only thing
between a stranger and your sessions.** Read [SECURITY.md](https://github.com/mmr710/nightmux/blob/main/SECURITY.md) before
you add a second person or a second machine. It is short.

What that means in practice:

- **Nothing is exposed by default.** The dashboard binds `127.0.0.1`; phones reach it through your tailnet or a pairing QR.
- **Only you can drive it.** Telegram messages from anyone not in `allow_users` are ignored.
- **Risky approvals stay human.** `!autoyes` is opt-in per topic and never presses yes on `rm -rf`, `sudo`, `git push`, `curl | sh`, `--force` or publish dialogs (`!policy` tunes this).
- **Spend is capped.** `!budget` (in tokens or dollars) and `!spendcap` stop runaway loops; `!cost top` shows where it went; `!stopall` stops every agent at once.
- **The QR shortcut in setup trusts the maintainer.** The relay passes your new bot's token to your terminal once, from memory, with no logs and no disk copy — but it runs on a machine you can't audit, so paste a BotFather token instead if that matters ([details](https://github.com/mmr710/nightmux/blob/main/SECURITY.md#the-qr-onboarding-relay)).
- **Zero dependencies.** Standard library only, so nothing third-party to audit. The daemon itself is a single file of about 20,000 lines.

## License

MIT. Changes are in [CHANGELOG.md](https://github.com/mmr710/nightmux/blob/main/CHANGELOG.md).

<div align="center">

**Stop babysitting your agents. Let them work the night shift.**

If nightmux saved you a night, a [⭐ star](https://github.com/mmr710/nightmux/stargazers) helps other vibe coders find it.

</div>
