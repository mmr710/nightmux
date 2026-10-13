# Companion: one persona over every project

The companion is a single persona you talk to about everything. It watches every
project, keeps its own memory, and hands work to agents in role.

`!companion [agent]` in an empty topic of its own starts it. It refuses a
project's topic, because it would take the topic over from that project's agent.

**Talking to it:** write in its topic in plain words, as with any agent ("what
moved today?", "push shop toward the checkout redesign tonight"). Its standing
knowledge of you comes from `PERSONA.md` (tone, risk, `## Priorities`), which you
edit, and from `MEMORY.md`, which it keeps.

**Targets:** `!companion focus <target>` in a project's topic sets that
project's target. While any target is set, the progress report covers only
targeted projects, and an idle targeted project is listed anyway with
`📌 target: … — idle`. So a night where nothing happens is spent handing the
next step toward the target to that project (with a `!budget`), or posting it as
an idea to tap (without one). The same report is skipped when it would repeat,
so an idle project gets one push per change, not one per round. Use
`!companion focus off` in that topic to clear it, or in the companion's topic to
clear all targets; `!companion focus` there lists them.

**Talking to it:** `!companion <anything>` in its topic is passed to it as a
message, so "!companion work on pennywise" works the same as writing it there.

**Priorities:** projects named in `PERSONA.md`'s `## Priorities` (`1. nightmux …`,
matched by topic name, session or folder) stay in every report, idle or not and
with or without a session, marked `⭐ priority N`, so the companion moves them
forward instead of waiting for something to happen there.

**Allowance:** a `!budget` in the companion's own topic is its allowance for
projects without a budget of their own. It counts everything those projects spent
this period, including the owner's turns, so it stops early rather than late.
`list_topics` shows what is left.

**Projects with no session:** `send_prompt` to a topic that has a folder and no
running agent starts its default agent there first.

**Watch:** `!companion watch 3h` runs the first round within a minute, looking back
3h, then every 3h.

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
  companion refuses any topic without a `!budget`, unless its own allowance
  (the `!budget` in its topic) still has room.
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

`!companion watch [3h]` runs a watch round every few hours. nightmux builds
the progress report itself, from the chat log and git, with no model reads,
and puts it in the round's prompt. The report covers, per project that moved:

- **What happened:** agent answers (only real ones, not nightmux's status
  lines), commits, the last answer, and budget spent.
- **✋ waiting on you, and for how long:** an open menu, or a question at the
  end of an answer nobody replied to.
- **⚠ going in circles:** many answers and no commit.
- **Health:** 🎯 the last `!goal` check (green, stuck, round N), 🚨 production
  errors, and uncommitted changes (`git diff --shortstat`).
- **The plan:** the project's own "In progress / next" lines from
  `.nightmux/memory.md`, so ideas build on work the project already chose.
- **How ideas landed:** sent, dropped, ignored and waiting over the last week,
  plus what was dropped. This is its feedback on your taste.

Projects with no activity are listed together on one line.

**In each round it:**

- **Posts one line per project that moved** to you: what got done and what is
  stuck.
- **Shares at most 3 ideas with `suggest`.** Each one lands in that project's
  topic with **▶ send to agent** and **✕** buttons, so you decide with one tap
  and no budget is needed.
  - An idea names a file, feature or command and quotes the line it builds on.
  - Limits: 6 per hour, and 3 waiting per topic.
  - Ideas and taps are kept in `ideas.jsonl`, so the buttons survive restarts.
  - An idea you dropped is never posted again.
- **Answers an agent's waiting question itself** only when its memory or the
  project's notes already hold the answer, and its risk level and budget allow.
  It can't type into an open menu: the tool says so instead of claiming "sent".

**When rounds are skipped:** a watch or night round makes no model call when
the report shows nothing moved, or says the same as last round. The cursor is
stored in the saved schedule, so it survives restarts.

## Cost: what keeps it cheap

The companion reads every project every round, so its context, not its
output, is the bill:

- **Persona and memory load through `CLAUDE.md` imports** (`AGENTS.md`/`GEMINI.md`
  for other CLIs). They load at every conversation start and after every
  compaction, with no read turn and no persona drift after `/compact`.
- **Fresh thread per round.** Before a scheduled round, a big thread is
  cleared (`/clear`), unless you wrote to the companion within the hour. Every
  round otherwise re-reads all earlier ones. The persona, memory, report and
  `actions.log` hold everything it needs.
- **MEMORY.md holds lasting things only:** your preferences, idea outcomes,
  and standing decisions. It is edited when something new is learned, and is
  not rewritten every round. Project status lives in the report.
- **No project-memory turns for the companion's own topic.**
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
     going-in-circles flags, quiet-skip;
   - after the expert review:
     - only real agent answers count;
     - the report is built by nightmux and gated;
     - fresh threads before rounds;
     - the idea ledger and taste feedback;
     - goal, error, diff and plan signals.
2. **Next:**
   - per-project persona overrides;
   - the morning summary as a voice note (reuse `!briefing voice`).
3. **Later, once a need shows:**
   - dedicated role sessions;
   - per-role models via the model ladder;
   - memory search once MEMORY.md outgrows 150 lines.
