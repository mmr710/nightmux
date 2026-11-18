"""test_text: cut from the old monolithic selfcheck() (pre-stub part)."""
import calendar
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_parse_reset_and_render():
    with isolated(nightmux) as iso:
        now = time.mktime((2026, 8, 7, 10, 0, 0, 0, 0, -1))
        assert nightmux.parse_reset("· resets in 2h 14m", now) == now + 2 * 3600 + 14 * 60
        assert nightmux.parse_reset("resets in 45m", now) == now + 45 * 60
        assert nightmux.parse_reset("Resets in 4 hr 56 min", now) == now + 4 * 3600 + 56 * 60
        assert nightmux.parse_reset("resets in 2d 3h", now) == now + 2 * 86400 + 3 * 3600
        assert nightmux.parse_reset("Your limit resets 3pm", now) == \
            time.mktime((2026, 8, 7, 15, 0, 0, 0, 0, -1))
        assert nightmux.parse_reset("limit resets at 09:30", now) == \
            time.mktime((2026, 8, 8, 9, 30, 0, 0, 0, -1))   # already past: tomorrow
        assert nightmux.parse_reset("please try again in a minute", now) == now + 60
        assert nightmux.parse_reset("retry in 30s", now) == now + 30
        assert nightmux.parse_reset("UNAVAILABLE (code 503): No capacity available for model gemini-pro-agent", now) == now + 60
        assert nightmux.parse_reset("no time here", now) is None   # never guess a reset
        assert nightmux.left(3 * 3600 + 61) == "3h 1m" and nightmux.left(90) == "1m"
        assert nightmux.brief({"command": "ls -la\nrm x", "file_path": "/a"}) == "ls -la"
        assert nightmux.brief({"file_path": "/a/b.py"}) == "/a/b.py" and nightmux.brief({"n": 1}) == ""
        assert nightmux.render({"type": "user", "message": {"content": "hi"}}) == []
        assert nightmux.render({"type": "assistant", "message": {"content": [
            {"type": "thinking", "thinking": "hmm"},
            {"type": "tool_use", "name": "Bash", "input": {"command": "pytest -q"}},
            {"type": "text", "text": " the answer "}]}}) == \
            ["● Bash(pytest -q)", "the answer"]



def test_clock_and_tz_shift():
    with isolated(nightmux) as iso:
        noon = time.mktime((2026, 8, 7, 12, 0, 0, 0, 0, -1))   # display shifts, never parse
        assert nightmux.clock({}, noon) == "12:00" and nightmux.clock({"tz_offset": 0}, noon) == \
            time.strftime("%H:%M", time.gmtime(noon))
        assert nightmux.clock({"tz_offset": 3}, noon) != nightmux.clock({"tz_offset": 0}, noon)
        assert nightmux.parse_reset("resets 3pm", noon) == nightmux.parse_reset("resets 3pm", noon)
        if os.path.isfile(os.path.join(nightmux.ZONEINFO, "Africa/Cairo")):
            aug = calendar.timegm((2026, 8, 7, 12, 0, 0, 0, 0, 0))    # a zone tracks DST,
            dec = calendar.timegm((2026, 12, 15, 12, 0, 0, 0, 0, 0))  # a fixed offset lies
            assert nightmux.tz_shift("Africa/Cairo", aug) == 3 * 3600
            assert nightmux.tz_shift("Africa/Cairo", dec) == 2 * 3600
            assert nightmux.clock({"tz_offset": "Africa/Cairo"}, aug) == "15:00"
            assert nightmux.clock({"tz_offset": "Africa/Cairo"}, dec) == "14:00"
            assert nightmux.clock({"tz_offset": 3}, dec) == "15:00"            # ... an hour wrong
            assert time.strftime("%Z", time.localtime(aug)) == "UTC"  # process TZ restored
            assert nightmux.tz_shift("Africa/Cairo", aug) == 3 * 3600          # cached, same answer



def test_limit_banner():
    with isolated(nightmux) as iso:
        for banner in ("You've hit your 5-hour limit · resets 3pm",
                       "  You've reached your weekly limit · Resets in 2 hr 16 min",
                       "You're out of usage credits · resets 11am"):
            assert nightmux.LIMIT_HIT.search(banner), banner
        assert not nightmux.LIMIT_HIT.search("● I hit your endpoint and it returned 200")



def test_md_html():
    with isolated(nightmux) as iso:
        assert nightmux.md_html("**bold** and `x_1 & y`") == \
            "<b>bold</b> and <code>x_1 &amp; y</code>", nightmux.md_html("**bold** and `x_1 & y`")
        assert nightmux.md_html("### Title\ntext") == "<b>Title</b>\ntext"
        assert nightmux.md_html("a\n```py\nif a < b:\n    f(**kw)\n```\nb") == \
            "a\n<pre>if a &lt; b:\n    f(**kw)</pre>\nb", nightmux.md_html("a\n```py\nif a < b:\n    f(**kw)\n```\nb")
        assert nightmux.md_html("snake_case and *stars* survive") == "snake_case and *stars* survive"
        assert nightmux.md_html("<script>") == "&lt;script&gt;"


def test_chrome_matches_noise_not_content():
    with isolated(nightmux) as iso:
        for chrome in ("╭──────────╮", "│ ", "", "─" * 40, "╌" * 40, "❯ what I already typed",
                       "✻ Brewed for 2s", "  ⏵⏵ accept edits on",
                       "  ubuntu@host:/home/x  [MODE] ⛏ 5.4M", "  ? for shortcuts"):
            assert nightmux.CHROME.match(chrome), repr(chrome)
        for keep in ("  Wrote 3 files to disk", "● PONG_TGCTL", "    return n + 1",
                     "  Read(src/main.py)", "❯ 1. Yes", "  2. No"):
            assert not nightmux.CHROME.match(keep), repr(keep)



def test_chrome_agy():
    with isolated(nightmux) as iso:
        for chrome in ("⢿  Running...", "> use your shell tool to run: ls",
                       "  ↑/↓ Navigate · enter Confirm",
                       "esc to cancel                    Gemini 3.1 Pro · high",
                       "                                 Gemini 3.1 Pro · high"):
            assert nightmux.CHROME.match(chrome), repr(chrome)   # agy chrome
        for keep in ("● Bash(sleep 8; echo hi) (ctrl+o to expand)", "> 1. Yes",
                     "  I have executed the command. It printed:"):
            assert not nightmux.CHROME.match(keep), repr(keep)



def test_detail_lines():
    with isolated(nightmux) as iso:
        assert nightmux.DETAIL.match("  ⎿  Read 200 lines") and nightmux.DETAIL.match("     … +12 lines")
        assert nightmux.DETAIL.match("▸ Thought for 3s, 282 tokens")
        assert not nightmux.DETAIL.match("● here is the answer")


def test_arabic_layout_translation():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        # Arabic keyboard layout translation
        assert "ظةخيثم".translate(nightmux.AR_EN_MAP) == "/model"
        assert "!ةخيثم".translate(nightmux.AR_EN_MAP) == "!model"
