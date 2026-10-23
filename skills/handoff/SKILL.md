---
name: handoff
description: Hand this repository's work to another coding agent (Codex, Gemini CLI, OpenCode, Qwen Code, agy) with a written brief, so it can carry on when Claude Code is near its usage limit or the user wants another agent on it. Use when the user asks to hand off or pass on the work, or to continue in another agent.
argument-hint: "[agent] [what to do next]"
---

Request: $ARGUMENTS

1. At the root of the repository, run `python3 "${CLAUDE_PLUGIN_ROOT}/nightmux.py" handoff` with the Bash tool and no other arguments: given an agent, it would start that agent's interface here, and that cannot run inside this session. It writes `.nightmux/HANDOFF.md` (the last instruction, recent actions, `git status`, the diffstat and recent commits, from the agents' own logs; the file stays out of `git status`), prints it, and lists the agents installed here.
2. Append a section `## Where Claude stopped` to `.nightmux/HANDOFF.md`: what is done, what is half done (files and functions), the next steps, and anything the next agent is likely to get wrong. Thirty lines at most; the working tree has the rest. Outside a git repository nothing was written, so put that section in your reply instead.
3. Give the user the line that starts the next agent on it, to run in a terminal of their own:

   ```
   cd "<repository root>" && python3 "${CLAUDE_PLUGIN_ROOT}/nightmux.py" handoff <agent> "<what to do next>"
   ```

   Use the agent named in the request, or else one of the installed agents the command listed. With nightmux installed, `nightmux handoff <agent> "..."` does the same.
