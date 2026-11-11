# nightmux compared

Other tools do parts of this job, and some do their part better. This page says where. The cells about other projects come from their public descriptions and have not been checked against their current releases; (unverified) marks the ones most likely to be out of date. If something here is wrong, open an issue.

| | nightmux | [Happy](https://github.com/slopus/happy) | [vibe-kanban](https://github.com/BloopAI/vibe-kanban) | [claude-squad](https://github.com/smtg-ai/claude-squad) | Vendors' own remote control |
|---|---|---|---|---|---|
| Main shape | tmux sessions driven by a daemon; `nightmux run` for one task from a terminal | Mobile and web app that reaches agents on your machine | Kanban board that runs agents in git worktrees | Terminal UI over tmux and git worktrees | Phone or web access to that vendor's own agent |
| Agents | Claude Code, Codex, Gemini, agy, OpenCode, Aider, Qwen Code and others ([table](../README.md#agents)) | Claude Code and Codex (unverified: others) | Several coding agents (unverified: exact list) | Claude Code, Codex, Gemini, Aider (unverified: exact list) | One vendor each |
| Moves work to another vendor's agent when one hits a limit | Yes: `nightmux run` and `!failover`. Limit text is recognised for Claude Code only | Not a listed feature (unverified) | Not a listed feature (unverified) | Not a listed feature (unverified) | No, by design |
| Runs until your tests pass | Yes: `--until "<check>"` and `!goal` | No (unverified) | No (unverified) | No (unverified) | No (unverified) |
| Runs without a bot, account or server of its own | `nightmux run`, `wrapped` and `up` do | Uses a relay server (unverified: self-hosting) | Yes, runs locally (unverified) | Yes, runs locally (unverified) | Needs the vendor's account |
| Phone | Telegram topics, or the dashboard and a pairing QR over a route such as Tailscale | A native app; this is its main strength | Browser (unverified: mobile support) | Terminal only (unverified) | Vendor's mobile app or web |
| Review of changes | Diffs and `!undo` in chat; a PR per task | Not its focus (unverified) | Board with diff review per task | Diff view per session (unverified) | Vendor's own |
| Size | One Python file, standard library only, one maintainer | Larger project and community | Larger project and community (unverified) | Larger project and community (unverified) | Maintained by the vendor |

## What the others do better

- **Happy** has a real mobile app with push notifications and a far larger community. If you want an app rather than a chat bot, start there.
- **vibe-kanban** gives you a board to plan and review many tasks at once. nightmux's `/board` shows the state of each session; it is not a planning board.
- **claude-squad** is simpler if you stay at the keyboard: one terminal UI, no daemon, no phone setup.
- **[HAPI](https://github.com/tiann/hapi)** is another app for Claude Code, Codex and more.
- **[ccbot](https://github.com/six-ddc/ccbot)** and **[ccgram](https://github.com/alexei-led/ccgram)** bridge Telegram topics to tmux sessions, the same shape as nightmux's core. If a bridge is all you want, start there.
- **[claude-auto-resume](https://github.com/terryso/claude-auto-resume)** is a shell script that resumes Claude Code when a usage limit lifts. If that is the one part you need, use it.
- **The vendors' own remote control** needs no third-party code, and the vendor supports it. If Claude Code is the only agent you use and you are awake, it is enough.

## What nightmux is for

The overnight layer across vendors: a task that keeps going when one agent is out of usage, and stops when your check passes. `nightmux run` does that for one task in one folder. The daemon adds queues, schedules, a morning briefing and a phone interface on top; those are in the [guide](GUIDE.md).

`nightmux run` does not answer permission menus; it reports them and waits. It reads usage-limit banners for Claude Code only; any other agent fails over when it exits or a turn takes over an hour.
