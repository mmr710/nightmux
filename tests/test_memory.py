"""test_memory: cut from the old monolithic selfcheck() (the last part)."""
import os
import queue
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_memory_rewrite_and_greet():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        # Project memory: enough turns and a quiet spell ask the agent to rewrite the
        # notes; its reply is swallowed; a session started where notes exist reads them.
        msaid_ = []
        with tempfile.TemporaryDirectory() as md_, nightmux.stubbed(
                send=lambda c, t, x, mode="mono", buttons=None, quiet=False: msaid_.append(x),
                save_cfg=lambda c: None):
            os.makedirs(os.path.join(md_, ".git", "info"))
            mcfg2_, mst2_ = {"topics": {"3": "m"}, "dirs": {"3": md_}}, {"m": {"mode": "idle", "changed": 0}}
            nightmux._mem.clear()
            for _ in range(nightmux.MEM_TURNS):
                nightmux.mem_capture(mcfg2_, "3", "m")
            nightmux.mem_tick(mcfg2_, mst2_)
            assert mst2_["m"]["queue"] == [nightmux.MEM_UPDATE] and nightmux._mem["3"]["wait"] == "m"
            assert ".nightmux/" in open(os.path.join(md_, ".git", "info", "exclude")).read()
            assert nightmux.mem_reply_capture(mcfg2_, "3", "m", "memory updated") and "updated" in msaid_[-1]
            assert not nightmux.mem_reply_capture(mcfg2_, "3", "m", "a normal answer")
            st3_ = {}
            nightmux.mem_greet(mcfg2_, st3_, "3", "m2", md_)
            assert not st3_                                       # no notes yet: nothing to read
            open(os.path.join(md_, nightmux.MEM_REL), "w").write("## What this is\nx")
            nightmux.mem_greet(mcfg2_, st3_, "3", "m2", md_)
            assert st3_["m2"]["queue"] == [nightmux.MEM_READ]
            nightmux.mem_greet(mcfg2_, st3_, "3", "m2", md_)             # back to it: already read
            assert st3_["m2"]["queue"] == [nightmux.MEM_READ]
            later_ = time.time() + 5
            os.utime(os.path.join(md_, nightmux.MEM_REL), (later_, later_))
            nightmux.mem_greet(mcfg2_, st3_, "3", "m2", md_)             # notes rewritten since
            assert st3_["m2"]["queue"] == [nightmux.MEM_READ] * 2
            nightmux.mem_greet(mcfg2_, st3_, "3", "m2", md_, fresh=True)  # new conversation, same name
            assert st3_["m2"]["queue"] == [nightmux.MEM_READ] * 3
            with nightmux.stubbed(tmux_git=lambda c, *a: "c0ffee"):        # a commit since: the notes may lag it
                nightmux.mem_greet(mcfg2_, st3_, "3", "m2", md_)
                assert st3_["m2"]["queue"] == [nightmux.MEM_READ] * 4
                nightmux.mem_greet(mcfg2_, st3_, "3", "m2", md_)
                assert st3_["m2"]["queue"] == [nightmux.MEM_READ] * 4
            # No change to the project since the last rewrite: no rewrite.
            nightmux._mem["3"] = {"turns": nightmux.MEM_TURNS, "fp": "same"}
            mst2_["m"]["queue"] = []
            with nightmux.stubbed(mem_print=lambda c: "same"):
                nightmux.mem_tick(mcfg2_, mst2_)
            assert mst2_["m"]["queue"] == [] and nightmux._mem["3"]["turns"] == 0
            nightmux._mem["3"]["turns"] = nightmux.MEM_TURNS
            with nightmux.stubbed(mem_print=lambda c: "moved"):
                nightmux.mem_tick(mcfg2_, mst2_)
            assert mst2_["m"]["queue"] == [nightmux.MEM_UPDATE]
            mcfg2_["memory"] = {"3": "off"}
            nightmux.mem_capture(mcfg2_, "3", "m")
            assert nightmux._mem["3"]["turns"] == 0
            nightmux._mem.clear()
