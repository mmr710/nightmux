# 🌙 nightmux Product Roadmap

`nightmux` is the **Autonomous Hypervisor & Mobile Cockpit for CLI Coding Agents** (`claude`, `codex`, `agy`, `opencode`, `gemini`, `cursor`, `amp`, `goose`, `qwen`).

Want one of these sooner, or have a better idea? Open an [issue](https://github.com/mmr710/nightmux/issues/new/choose) — and say if you'd like to build it.

---

## Phase 1: Frictionless Onboarding, Super-Intents & Zero-Click Viral Sharing
*Goal: Sub-60s time-to-first-prompt, zero memorized CLI flags on mobile, and 1-tap social cards that unfurl natively on X and Reddit.*

- [x] **5 Super-Intents Action Bar (`!vibe`):** Consolidate 70+ commands into a 1-tap mobile action bar (`🚀 Build`, `🌙 Night Shift`, `⚡ Race`, `🧬 Teleport`, `🌾 Harvest`, `🎁 Wrapped`).
- [x] **Dynamic OpenGraph Social Cards (`/share` & `/share/card.svg`):** Stateless SVG/HTML OpenGraph card generator + Web Share API Level 2 (`navigator.share({ files })`) for native 1-tap photo/GIF sharing to X and Reddit without manual file attachment.
- [ ] **Telegram-Free 60s First Run & QR Mobile Pairing (PR #128):** Boot straight into the mobile PWA via terminal QR code before configuring BotFather.

## Phase 2: Cross-Agent Context Teleportation & Subscription Quota Arbitrage
*Goal: Zero wasted tokens on agent failover and zero wasted 5-hour subscription windows while you sleep.*

- [x] **Context Teleportation (`!teleport` & Smart Failover):** Extract recent transcript turns, tool calls, `git status/diff`, and `.nightmux/memory.md` into a structured `.nightmux/HANDOFF.md` packet so failover or switched agents continue mid-thought without re-exploring the codebase.
- [x] **Unused Quota Window Harvester (`!harvest`):** Monitor 5-hour subscription quota windows; when a window is about to reset with unused capacity (`< 60m` left and below the safety ceiling, default `85%`), automatically wake idle sessions to run queued tech-debt, test, and cleanup tasks.
- [ ] **Universal Agent Schema Adapters & Drift Guard (PR #111):** First-class structured transcript & limit readers across Claude Code, Codex, OpenCode, and Antigravity (`agy`).

## Phase 3: "Walkie-Talkie" & "Swipe-to-Ship" Mobile Vibe UX
*Goal: True hands-free and thumb-native vibe coding away from a desk.*

- [ ] **Walkie-Talkie Voice Supervisor:** Automatically route natural-language voice notes into multi-step overnight plans (`!shift`), test-verified loops (`!goal`), or multi-agent worktree races (`!race`).
- [ ] **Swipe-to-Ship Visual Review Mini-App:** Mobile card stack combining per-turn git checkpoints, side-by-side visual diffs, and headless browser screenshots (`!shot`) with 1-tap Merge or Rollback (`!undo`).
- [ ] **Prompt-to-PR Interactive Cartridges:** Shareable self-contained HTML replays combining the 20x Pixel Office time-lapse, token savings ledger, and winning prompt.

## Phase 4: Modular Source Tree with Single-File Release Compiler
*Goal: Preserve the zero-dependency 1-file stdlib magic for users while making contributor PRs effortless.*

- [ ] **`src/` Modular Split + `build.py` Bundler:** Split daemon, token accounting, agent adapters, and embedded HTML/CSS/JS views into `src/` with a deterministic CI bundler that emits the single distributable `nightmux.py`.
- [ ] **Cross-Peer Session Replay & Dollar Budgets:** Provider-priced dollar caps and unified replay scrubbing across peer machines.

---

## Shipped Recently
- **Companion Supervisor (`!companion`):** Cross-project autonomous night rounds, morning briefings, and tap-to-send idea ledger ([docs/COMPANION.md](docs/COMPANION.md)).
- **Token Optimization Suite:** Tiered `!autocompact`, `!ladder` model/effort scaling, parked-session compaction, and fleet-wide `!wrapped` / `!coach` analytics.
- **Multi-Server Mesh (`--join` / `!server`):** Run one bot and dashboard across multiple machines over Tailscale.
- **Discord & Slack Experimental Bridge:** Native stdlib WebSocket gateway / Socket Mode support.

Full history: [CHANGELOG.md](CHANGELOG.md).
