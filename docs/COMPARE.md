# nightmux compared

Other tools do parts of this job, and some do their part better. This page says where. The cells about other projects were checked against each project's README on 2026-11-11; "not listed" means the README does not mention it, not that it cannot be done. The vendor column is general and marked (unverified). If something here is wrong, open an issue.

| | nightmux | [Happy](https://github.com/slopus/happy) | [vibe-kanban](https://github.com/BloopAI/vibe-kanban) | [claude-squad](https://github.com/smtg-ai/claude-squad) | Vendors' own remote control |
|---|---|---|---|---|---|
| Main shape | tmux sessions driven by a daemon; `nightmux run` for one task from a terminal | Native iOS and Android apps plus web, reaching agents on your machine | Kanban board; each task gets a branch, a terminal and a dev server | Terminal UI over tmux sessions and git worktrees | Phone or web access to that vendor's own agent |
| Agents | Claude Code, Codex, Gemini, agy, OpenCode, Aider, Qwen Code and others ([table](../README.md#agents)) | Claude Code, Codex, Gemini, OpenCode and other Agent Client Protocol agents | Claude Code, Codex, Gemini CLI, Copilot, Amp, Cursor, OpenCode, Droid, Qwen Code | Claude Code, Codex, Gemini, Aider and other local agents | One vendor each |
| Moves work to another vendor's agent when one hits a limit | Yes: `nightmux run` and `!failover`. Limit text is recognised for Claude Code only | Not listed | Not listed | Not listed | No, by design (unverified) |
| Runs until your tests pass | Yes: `--until "<check>"` and `!goal` | Not listed | Not listed | Not listed | No (unverified) |
| Runs without a bot, account or server of its own | `nightmux run`, `wrapped` and `up` do | Syncs through a relay server, end-to-end encrypted | Yes: `npx vibe-kanban` | Yes | Needs the vendor's account |
| Phone | Telegram topics, or the dashboard and a pairing QR over a route such as Tailscale | Native apps with push notifications; this is its main strength | Web UI, reachable through a tunnel you set up | Not listed; it is a terminal app | Vendor's mobile app or web (unverified) |
| Review of changes | Diffs and `!undo` in chat; `!review` page per topic | Not its focus | Diffs with inline comments per task; opens PRs | Diff tab per session | Vendor's own |
| Licence | MIT | MIT | Apache-2.0 | AGPL-3.0 | Proprietary |
| Size | One Python file, standard library only, one maintainer | Much larger project and community | Much larger project and community; its README says it is sunsetting | Larger project and community | Maintained by the vendor |

## What the others do better

- **Happy** has real native apps with push notifications, end-to-end encryption and a far larger community. If you want an app rather than a chat bot, start there.
- **vibe-kanban** gives you a board to plan and review many tasks at once, with inline comments on diffs. nightmux's `/board` shows the state of each session; it is not a planning board. Its README says the project is sunsetting, so check its status first.
- **claude-squad** is simpler if you stay at the keyboard: one terminal UI, no daemon, no phone setup.
- **[HAPI](https://github.com/tiann/hapi)** controls Claude Code, Codex, Cursor Agent, OpenCode and more from native apps, a web app or a Telegram Mini App.
- **[ccbot](https://github.com/six-ddc/ccbot)** (Claude Code) and **[ccgram](https://github.com/alexei-led/ccgram)** (Claude Code, Codex, Gemini, Pi) bridge Telegram topics to tmux windows, the same shape as nightmux's core. If a bridge is all you want, start there.
- **[claude-auto-resume](https://github.com/terryso/claude-auto-resume)** is a shell script that resumes Claude Code when a usage limit lifts. If that is the one part you need, use it.
- **The vendors' own remote control** needs no third-party code, and the vendor supports it. If Claude Code is the only agent you use and you are awake, it is enough.

## What nightmux is for

The overnight layer across vendors: a task that keeps going when one agent is out of usage, and stops when your check passes. `nightmux run` does that for one task in one folder. The daemon adds queues, schedules, a morning briefing and a phone interface on top; those are in the [guide](GUIDE.md).

`nightmux run` does not answer permission menus; it reports them and waits. It reads usage-limit banners for Claude Code only; any other agent fails over when it exits or a turn takes over an hour.
