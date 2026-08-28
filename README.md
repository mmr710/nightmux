# nightmux

[![tests](https://github.com/mmr710/nightmux/actions/workflows/test.yml/badge.svg)](https://github.com/mmr710/nightmux/actions/workflows/test.yml)
[![Telegram](https://img.shields.io/badge/Telegram-Community-blue.svg?logo=telegram)](https://t.me/+SGmmExdMHTQ3OWVk)
[![PyPI](https://img.shields.io/pypi/v/nightmux.svg)](https://pypi.org/project/nightmux/)

![nightmux — unified Telegram control for multi-agent AI workflows, quota monitoring, and automated recovery](docs/hero.jpg)

**Your night crew, on Telegram.**

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

That is the part nobody else is doing. The rest is what makes it usable:

Run **Claude Code from your phone** — or Codex, Gemini, aider, anything with a
prompt. One Telegram forum topic per project, one tmux session behind it. Text
you send is typed into that session's prompt; what the session says comes back
to the topic. Approvals arrive as tap buttons.

No container, no DNS, no certificates, no ports open, no relay service. It
attaches to tmux sessions you already have, on the machine you already use.
Python stdlib only — one file, ~3,400 lines you can read in an afternoon.

![What a night looks like: the limit hits at 02:14, nightmux resumes the turn at 04:11, and the one approval waits for breakfast](docs/demo.svg)

**Try it:** `curl -fsSL https://raw.githubusercontent.com/mmr710/nightmux/main/install.sh | bash` — five minutes, no
dependencies, no server. [Full install →](#install)

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

## Why this one

There are plenty of ways to reach a coding agent from a phone. Most are one of
two shapes: a bot that drives the agent through its SDK and keeps the
conversation in its own database, or a mobile app that talks to a relay service
you don't run. Both work. Neither leaves you with a terminal session.

nightmux is the third shape — it drives the session you would have started
yourself:

**It works the hours you don't.** A status-line sidecar gives nightmux the real
context percentage and the real 5-hour / 7-day limit windows, so it can act on
them instead of discovering them:

- a turn the limit cut off **resumes itself** when the window reopens
  (`"auto_continue": false` to wait for a human instead)
- a prompt sent during a lockout is **held**, not lost — replayed when the window
  resets, surviving daemon restarts and reboots
- a prompt refused before it ever got a turn goes back on the queue whole
- `!at 03:00 <prompt>` and `!every 4h <prompt>` start work while you are asleep —
  and they queue rather than type, so they wait behind a lockout too
- `/compact` automatically at a context threshold you set (`!autocompact 70`)
- warnings at 80% and 90% of a window, before the wall rather than at it
- `!ctx` shows what is actually filling the window; `!cost` weighs a session or
  every project by token type

Long-running agent sessions cost money and stall in ways chat never does. That is
the part nobody else is watching.

**It attaches to sessions instead of owning them.** nightmux types into tmux. The
session is still yours — SSH in, attach, type directly, and the bot keeps working
mid-conversation. Nothing is wrapped, proxied, or re-hosted, so there is no state
to get out of sync and nothing to lose when the daemon restarts.

**It is not tied to one agent.** `!new` starts your default; `!codex`, `!aider`,
`!gemini` or anything you add to `agents` in the config starts that instead, and
`!resume` remembers which agent a topic belongs to. The hooks and the usage
numbers are Claude Code specific — every other agent degrades to reading the
terminal, which is how nightmux worked before the hooks existed.

**One topic, several agents.** A bare `!agy`, `!codex` or `!opencode` in a topic
that already has a directory switches *that topic* to that agent — same project,
its own tmux session, and the agent you were on left running. `!agents` lists the
bench and marks the live one; switching back lands in the conversation it was in,
not a fresh one. Give a name and a directory (`!agy side ~/code/api`) and it
still means start-a-new-session, as before.

One session belongs to one topic. Two topics pointing at the same session share a
single scrape cursor, so whichever one the watcher reaches first gets the output
and the other goes quiet; `!bind` refuses that now, and `!status` flags any pair
already in your config.

**Not for you if** you want a polished app instead of a chat window, you're on
Windows ([#2](https://github.com/mmr710/nightmux/issues/2) — macOS and Linux
both install as a service), or you want your
teammates in the same group: the allowlist is a list of people trusted with a
shell on your machine, which is not a thing to hand out. One person, their own
box, their own agents.

## Install

The fastest way to install is using the one-line installer:
```bash
curl -fsSL https://raw.githubusercontent.com/mmr710/nightmux/main/install.sh | bash
```
*(This automatically checks for `pipx`, installs nightmux, and runs setup).*

**To test the rate limit auto-recovery instantly:** run `python3 nightmux.py --demo` after installing.

Or install from PyPI manually:
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

Everything works as `!cmd`, and the common ones are registered as `/cmd` so
Telegram autocompletes them. Anything that is not a nightmux command — including
Claude's own `/compact`, `/clear`, `/model` — is typed into the session.

| | |
|---|---|
| `!new <name> [dir] [flags] [@branch]` | start a session with the default agent, bind this topic to it |
| `!codex` / `!aider` / `!gemini` / `!agy` … | same, with that agent |
| `!<agent>` with no arguments | switch this topic to that agent, in the same directory |
| `!agents` | this topic's agents, which one is live, and which report a context figure |
| `!resume [agent]` / `!restore` | relaunch this topic's directory, resuming the last conversation |
| `!bind <session>` / `!unbind` / `!kill` | attach, detach, stop (kill asks first) |
| `!sessions` / `!status` | tmux sessions; every topic and its state |
| `!pane [lines]` / `!ctl` | dump the terminal; button panel |
| `!git` / `!diff` / `!get <path>` | repo state and file upload from the session's cwd |
| `!worktrees` | git worktrees of this topic's repo, and which session sits in each |
| `!undo` | list snapshot branches for this repo and the restore commands — never runs them |
| `!ctx` / `!cost [days]` / `!usage` | context breakdown, token spend, limit windows |
| `!autocompact <pct\|off>` | auto-`/compact` at a context threshold |
| `!idlectx <pct\|off>` | flag parked sessions still holding a big context |
| `!queue [clear\|now]` | prompts held for a rate-limit reset |
| `!at 03:00 <prompt>`, `!at +90m …` | run a prompt later |
| `!every 4h <prompt>`, `!sched [clear]` | run it on a repeat, or list what is set |
| `!shift` + one prompt per line | a sequential overnight plan, one turn at a time |
| `!digest [HH:MM\|off]` | what happened while you slept, on demand or daily |
| `!center [off]` | make this topic watch and control every session |
| `!board` | every topic at a glance, from any topic |
| `!all <targets\|--all> <prompt>` | send one prompt into several sessions at once |
| `!grep <text> [days]` | search every transcript on the machine |
| `!verbose` / `!raw <text>` / `!keys <keys>` | tool detail, type past a menu, raw tmux keys |
| `!1`..`!9` `!y` `!n` `!esc` `!int` `!enter` `!tab` | menu picks and keys |

A pick is checked, not assumed: `!1` sends the digit, looks at the pane, and adds
Enter only if the same question is still there — dialogs disagree about whether a
digit confirms or only moves the highlight. `!y`/`!n` answer a numbered menu with
the digit of its Yes/No option, because the letter does nothing to a list.
| `!version` | build, python, and which hooks are wired |
| `!tz <zone>` / `!reload` / `!log` / `!help` | timezone, re-read config, journal, this list |

Send a photo, file or voice message and it is saved, with the path typed into the
session.

## Several agents, one project

`!new api ~/code/api @refactor-auth` checks out a git worktree for that branch —
new if it doesn't exist, reused if it does — at `~/code/api-wt/refactor-auth`,
and starts the session there instead of in the main tree. Two agents, two
branches, no stepping on each other's uncommitted work. `!worktrees` lists every
worktree of the current topic's repo and which session (if any) is sitting in
it. Nothing here routes work between agents or merges anything — that part is
still yours; this is just isolation.

## Command center

`!center` in any topic makes it the one place that watches and controls every
session — it binds to nothing itself, `!board` there shows every topic's state
at a glance:

```
you   !board
bot   ✅ api      topic 12   idle    2s quiet  5h 40%  ctx 22%
      ⚙️  web      topic 15   busy    0s quiet  5h 40%
      🟠 scratch  topic 19   waiting 1s quiet  🔒held→04:11
      spend  api ~12,400tok · web ~3,100tok
```

Approvals mirror there too: a session's 🟠 needs-input prompt posts to its own
topic as always, and a copy lands in the command center with the same buttons.
Whichever is tapped first answers the pane; the other loses its buttons
immediately rather than sitting there able to send a second, conflicting
keystroke. `!all web,scratch --continue` (or `!all --all <prompt>` for every
bound, writable session) sends the same prompt to several sessions at once —
it replies with exactly who it is about to hit before anything is typed, and a
`"readonly"` topic is never one of them. Nothing here routes work between
agents or decides anything for them; it broadcasts and it aggregates, and every
session still runs on its own.

## Snapshots and !undo

Before nightmux sends a prompt it typed without you watching it happen — a
prompt held for a usage-limit reset, an `!at`/`!every` firing, a `!shift`
step — it takes a git snapshot of the session's cwd first: `git stash create`
captures the worktree without touching it, and a `nightmux/pre-<UTC timestamp>`
branch is left pointing at it (the last 5 per repo; older ones are dropped).
Prompts you type live get no snapshot — there is nothing unattended about them.
`!undo` lists a topic's snapshot branches, newest first, with the exact `git
restore`/`git diff` commands to look at or roll back to one. It never runs them
— a phone is a small thing to fat-finger a hard reset from.

## Zero-Dependency Webhook API

nightmux runs a local HTTP server (`127.0.0.1:9090`) to accept commands from outside Telegram. You can configure `"webhook_port": 9090` in your `~/.nightmux.json` to enable it.

This turns nightmux into the central nervous system for your local agents. You can pipe GitHub Actions test failures or VS Code compiler errors straight into your agent's queue while you sleep.

```bash
curl -X POST http://127.0.0.1:9090/topic/api -d "review the staged changes"
```

Check out the [Cookbook](cookbook/README.md) for copy-paste recipes for GitHub Actions and editor integrations.

## How it works

Four files, no framework:

| | |
|---|---|
| `nightmux.py` | the daemon: long-polls Telegram, watches tmux, everything above |
| `nightmux_state.py` | status-line sidecar — parks context %, limit windows and the transcript path where the daemon can read them |
| `nightmux_stop.py` | `Stop` hook — pushes the final answer as exact text, not scraped pixels |
| `nightmux_notify.py` | `Notification` hook — pushes permission prompts the instant they appear |

The daemon reads the session's JSONL transcript when the sidecar is installed,
which is why output arrives as clean text with a real tool trace. Without it,
nightmux falls back to scraping `tmux capture-pane` — everything still works, just
noisier and without the usage numbers.

One watcher thread polls every bound session; each topic gets its own worker
thread, so a slow command in one topic never blocks another. The polling offset
is only persisted past updates that have actually finished, so a crash replays
work rather than dropping it.

[ARCHITECTURE.md](ARCHITECTURE.md) has the rest: threads, what survives a
restart, how output is chosen, and the decisions that were rejected.

Run the tests: `python3 nightmux.py --selfcheck` (and the same flag on the three
hook scripts). No framework, no fixtures — asserts that fail loudly.

`nightmux --doctor` triages an install without fixing anything: tmux found,
config complete, token accepted by Telegram, hooks wired, service active — one
✓/✗ line each, exit 1 if anything is off.

`python3 tests/test_panes.py` runs the pane corpus: captured terminal screens and
the state nightmux must read from each. Adding an agent whose TUI it misreads is
one file — drop the pane in `tests/panes/` as `<what>.<busy|idle|waiting>.txt` and
the classifier is held to it from then on.

## Config

`~/.nightmux.json`, mode `0600`, written by setup:

```json
{
  "token": "<from @BotFather>",
  "chat_id": -1001234567890,
  "allow_users": [123456789],
  "topics": {"12": "api"},
  "agent": "claude",
  "agents": {"opencode": ["opencode", "--continue"]},
  "autostart": {"api": "~/code/api"},
  "auto_restore": false,
  "projects_root": "~/code",
  "tz_offset": "Africa/Cairo",
  "autocompact": 70,
  "auto_continue": "continue",
  "modes": {"115": "readonly"},
  "poll": 2
}
```

`agent` is what `!new` starts. `agents` adds or overrides entries in the
built-in table as `[command, resume-flags]` — those flags are the part most
likely to drift as these CLIs change, so they are config, not code.
`autostart` recreates named sessions after a reboot. For everything else a
reboot killed, nightmux checks each bound topic against tmux at startup: with
`auto_restore` it just relaunches and says so; without it, the topic gets a
"machine restarted?" message with a Restore button instead of nightmux acting
on its own — `!restore` does the same relaunch on demand. `projects_root` makes
a new topic named after a directory start that project on its first message.
`!reload` picks up hand edits without a restart.

## Requirements

Python 3.8+ (CI runs 3.8 through 3.13), tmux, a terminal coding agent, and Linux
with systemd (the service is optional — `python3 nightmux.py` in a terminal works
fine). Claude Code gets the hooks and the usage numbers; everything else runs on
the terminal scrape.

## Security

**The bot token is a shell on your machine, and `allow_users` is the only thing
between a stranger and your sessions.** Read [SECURITY.md](SECURITY.md) before
you add a second person or a second machine. It is short.

## License

MIT. Changes are in [CHANGELOG.md](CHANGELOG.md).
