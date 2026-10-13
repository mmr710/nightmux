# Companion: one persona over every project

The companion is a single persona you talk to about everything. It watches every
project, keeps its own memory, and hands work to agents in role.

`!companion [agent]` in any topic starts it.

## What the owner decided (2026-10-13)

| Question | Answer |
|---|---|
| What is it? | A companion: one persona you talk to about everything. It is not a router. |
| Night autonomy | It acts alone, within a budget. |
| Personality | Tone and style, plus how much risk it takes. |
| Agents | Agents are roles instead of one expert per project. Any role works on any project. |
| Shareable personas | No. Persona and memory stay private. |

## Design

- **It is an ordinary agent session.** It runs in `~/.nightmux-companion/` (mode
  700, never a repo), so it gets the queue, limits, undo, compaction and failover
  that every topic already has. nightmux needs no second agent loop.
- **`PERSONA.md`** holds the name, the tone, and `risk: cautious | balanced | bold`.
  Each risk level is spelled out as concrete actions: what it may do alone, and
  what it always asks about (deploy, delete, pay, post). The owner edits the file
  and the companion rereads it.
- **`MEMORY.md`** is written by the companion itself. It holds the owner's
  preferences, where each project stands, and what worked. It is rewritten
  rather than appended, kept under 150 lines, and never holds secrets.
  - Each project's own notes stay in `<dir>/.nightmux/memory.md`, which the
    companion reads before directing that project.
  - Two layers: a private one about the owner, and a per-repo one about the code.
- **`roles/*.md`** ship as builder, reviewer, tester and researcher.
  - `send_prompt(topic, text, role=…)` puts the role file in front of the task.
  - The same project can be built by one role and checked by another, and one
    role can work across projects.
  - The companion adds a role file when none fits.
- **Tools** come from the nightmux MCP server started with `--companion`:
  `list_topics` (now with dir and budget), `read_chat`, `read_terminal` and
  `send_prompt`.
- **Autonomy is enforced in code, not in the prompt.** `send_prompt` from the
  companion refuses any topic without a `!budget`.
  - A budget caps spend per day, week or month and holds the queue once spent,
    so it bounds what the companion can do alone.
  - Without a budget it can only suggest, and the owner sends.

## Why this shape (best practice it follows)

- **Persona as an editable file, memory as a separate file the agent curates.**
  This keeps identity stable while what it knows changes. It is the pattern of
  CLAUDE.md/AGENTS.md plus a memory index, and it avoids personas drifting through
  a long chat.
- **Hard limits outside the model.** A prompt saying "don't overspend" is advice;
  a budget check in the tool is a limit. The risk level only shapes judgement
  inside that limit.
- **Orchestrator plus specialised workers via tools.** This is the
  supervisor/worker pattern. Workers stay ordinary CLI sessions in their own
  repos, so their context stays small and the companion's context holds only
  summaries (`read_chat`), not whole terminals.
- **Roles are prompts, not new processes.** Most of a "role agent" is its
  instructions. Separate sessions per role cost a full context each. This
  approach adds none until it is shown to be needed.

## Phases

1. **Done in this PR:**
   - `!companion`, seeded persona, memory and roles;
   - the budget-gated `--mcp --companion`;
   - `role=` on `send_prompt`;
   - dir and budget shown in `list_topics`.
2. **Next:**
   - **Night loop:** a scheduled `!every` nudge to the companion ("check every
     project, act within budget, report"), plus a morning summary.
   - **Per-project personas:** an optional `PERSONA.md` override per project.
3. **Later, once phase 2 shows a need:**
   - dedicated role sessions (a standing reviewer on a branch worktree);
   - per-role models (reviewer on opus, tester on haiku) via the model ladder;
   - companion memory search once MEMORY.md outgrows 150 lines.
