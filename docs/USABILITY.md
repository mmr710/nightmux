# Newcomer test

Five people who have used an AI coding agent but never nightmux. One session each,
45 minutes, screen shared. You watch and write down times; you do not help unless
they are stuck for 3 minutes, and every time you help it is logged as a failure of
that step.

Run it again after any change to install, `--setup`, the dashboard's first screen
or `/app`. The numbers matter more than the opinions.

## Setup

- A fresh Linux VM or Mac user account: no `~/.nightmux.json`, tmux not installed,
  one agent CLI installed and logged in (claude, codex or opencode).
- Their own phone with Tailscale installed and logged in to the same tailnet
  (that is the one thing done for them in advance).
- Give them only the repo URL and this sentence:
  *"Get an AI agent building a habit tracker that you can watch and steer from your phone."*

## The funnel

| # | Step | Done when | Target |
|---|------|-----------|--------|
| 1 | Install | `nightmux --doctor` runs | 5 min |
| 2 | First run | dashboard open in a browser | 10 min |
| 3 | First project | a topic exists with an agent session working in it | 15 min |
| 4 | Phone | the dashboard or app is open on their phone | 20 min |
| 5 | Steer | they answer a permission menu or send a prompt from the phone | 25 min |
| 6 | Undo | they roll back a change with `!undo` | 35 min |
| 7 | Result | `./check.sh` passes in the project | 45 min |

For each person and step, record the time reached, or ✗ with where they stopped.

## What to note

- Every place they reread something, scroll back, or open the README: quote the
  words they were looking for.
- Every error message they saw, verbatim, and whether it told them what to do.
- Whether they found the "start from" templates on their own.
- The first thing they said after step 5.

## Afterwards

Add one row per person to the results table below, then fix the step where the
most people stopped before anything else.

## Results

| Date | Person | 1 | 2 | 3 | 4 | 5 | 6 | 7 | Stopped at / quote |
|------|--------|---|---|---|---|---|---|---|--------------------|
