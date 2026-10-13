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

## Night rounds and the morning summary

`!companion night [01:00] [07:30]` schedules work on the companion's own queue
(`!sched` lists it), so it waits out usage limits and survives restarts:

- **Rounds every 2h from 01:00.** It runs `list_topics`, reads only what changed,
  and hands clear work to budgeted projects with a role. It doesn't wait for
  results: the next round reads them and reviews before handing out more.
- **The 07:30 summary** covers what it handed out and what came of it, budget
  spent per project, decisions waiting on you, and what it would do next. It is
  built from `actions.log`, the log of every prompt it sent, not from its own
  recollection.

`!companion night off` stops it.

## By day: progress and ideas

`!companion watch [3h]` runs a watch round every few hours. In each round it:

- **Calls `progress` once.** nightmux builds the report from the chat log and
  git, not from model reads. It lists each project that moved: replies,
  commits, last answer, budget. It flags the two things someone scanning topics
  misses: **✋ a question nobody answered**, and **⚠ many replies with no
  commit** (an agent going in circles). Quiet projects share one line.
- **Posts one line per project to you:** what got done and what is stuck.
- **Shares at most 3 ideas with `suggest`.** Each idea lands in that project's
  topic with **▶ send to agent** and **✕** buttons, so you decide with one tap
  and no budget is needed. Ideas must name a file, feature or command; generic
  advice is out. Capped at 6 per hour, 10 pending per topic.
- **Answers an agent's waiting question itself** only when its memory or the
  project's notes already hold the answer, and its risk level and budget allow.

A round is **skipped without a model call** while no project's chat has moved,
so a quiet day costs nothing. Its own scheduled rounds no longer post
"⏰ queued" pings.

## Cost: what keeps it cheap

The companion reads every project every round, so its context, not its
output, is the bill:

- **Persona and memory load through `CLAUDE.md` imports** (`AGENTS.md`/`GEMINI.md`
  for other CLIs). They load at every conversation start and after every
  compaction, with no read turn and no persona drift after `/compact`.
- **`read_chat` keeps a cursor per project.** It returns only messages not yet
  seen: at most the last 15, each cut at 1500 characters. `read_terminal`
  defaults to 40 lines.
- **`list_topics` shows the budget spent** (`1.2M of 5M this day`), so one call
  answers "where can I still act" without reading anything else.
- **It can't prompt its own topic**, which would be a loop that bills itself.
- **A cheaper model is one flag away:** `!companion claude --model sonnet`.
  Routing and summaries rarely need the top tier, and the project agents still
  do the heavy work on their own models.

## Phases

1. **Done:**
   - `!companion`, budget-gated tools, roles, project dir and budget in `list_topics`;
   - night rounds and the morning summary, `actions.log`, read cursors,
     persona via `CLAUDE.md`;
   - the day watch: `progress`, `suggest` with tap-to-send, stuck and
     going-in-circles flags, quiet-skip.
2. **Next:**
   - per-project persona overrides;
   - the morning summary as a voice note (reuse `!briefing voice`).
3. **Later, once a need shows:**
   - dedicated role sessions;
   - per-role models via the model ladder;
   - memory search once MEMORY.md outgrows 150 lines.
