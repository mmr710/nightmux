"""test_help: cut from the old monolithic selfcheck() (the last part)."""
import os
import queue
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_help_index_sections_search():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        cfg2 = {"topics": {}, "agents": {"opencode": ["opencode", "--resume"]}}
        spawned, lk = [], threading.Lock()
        nightmux.spawn = lambda n, cwd, line, cfg=None: spawned.append((n, cwd, line))
        nightmux.has_session = lambda n: False
        nightmux.start_session(cfg2, {}, lk, "9", "box ~ --sandbox", "codex")

        # !help: an index with a button per section, sections, search, everything.
        hi_, rows_ = nightmux.help_text(cfg2)
        assert len([b for r in rows_ for b in r]) == len(nightmux.HELP) + 1 and "!help night" in hi_
        assert nightmux.help_text(cfg2, "night")[0].startswith("🌙") and nightmux.help_text(cfg2, "night")[1] is None
        assert "!goal [n]" in nightmux.help_text(cfg2, "!goal")[0] and "nothing about" in nightmux.help_text(cfg2, "zzz")[0]
        all_ = nightmux.help_text(cfg2, "all")[0]
        assert "opencode" in all_ and "{agents}" not in all_ and nightmux.PLUGIN_DIR in all_


def test_help_names_every_old_command():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        cfg2 = {"topics": {}, "agents": {"opencode": ["opencode", "--resume"]}}
        spawned, lk = [], threading.Lock()
        nightmux.spawn = lambda n, cwd, line, cfg=None: spawned.append((n, cwd, line))
        nightmux.has_session = lambda n: False
        nightmux.start_session(cfg2, {}, lk, "9", "box ~ --sandbox", "codex")
        all_ = nightmux.help_text(cfg2, "all")[0]

        # Every command the old flat list named is still somewhere in a section.
        for c_ in ("!bind", "!consult", "!use", "!shift", "!at", "!queue", "!usage", "!grep", "!plugins",
                   "!autocompact", "!keys", "!raw", "!model", "!worktrees", "!center", "!failover",
                   "!update", "!reload", "!tz", "!digest", "!idea", "!errors", "!desktop", "!memory"):
            assert c_ in all_, c_
