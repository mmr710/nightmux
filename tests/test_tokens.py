"""test_tokens: cut from the old monolithic selfcheck() (pre-stub part)."""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402


def test_tail_transcript_baselines_and_partials():
    with isolated(nightmux) as iso:
        tp = os.path.join(nightmux.FILE_DIR, "selfcheck.jsonl")
        os.makedirs(nightmux.FILE_DIR, exist_ok=True)
        rec = json.dumps({"type": "assistant",
                          "message": {"content": [{"type": "text", "text": "one"}]}})
        with open(tp, "w") as f:
            f.write(rec + "\n")
        tst = {}
        assert nightmux.tail_transcript(tst, tp) == []          # first sight baselines, no dump
        with open(tp, "a") as f:
            f.write(rec.replace("one", "two") + "\n")
            f.write('{"type": "assistant", "message": {"content": [{"typ')  # half a line
        assert nightmux.tail_transcript(tst, tp) == ["two"]     # partial record held back
        assert nightmux.tail_transcript(tst, tp) == []
        with open(tp, "w") as f:                       # /clear: file shrank, rebaseline
            f.write(rec + "\n")
        assert nightmux.tail_transcript(tst, tp) == []
        os.remove(tp)


def test_compact_boundary_drops_figure():
    with isolated(nightmux) as iso:
        tp = os.path.join(nightmux.FILE_DIR, "selfcheck.jsonl")
        os.makedirs(nightmux.FILE_DIR, exist_ok=True)
        rec = json.dumps({"type": "assistant",
                          "message": {"content": [{"type": "text", "text": "one"}]}})
        with open(tp, 'w') as f:
            f.write(rec + '\n')
        # /compact: a boundary record and no usage. The figure must drop with it,
        # or autocompact reads the stale size and compacts the summary again.
        booked, ct = [], {}
        nightmux.tail_transcript(ct, tp)                        # its own baseline
        with open(tp, "a") as f:
            f.write(json.dumps({"type": "assistant", "message": {"content": [], "usage": {
                "input_tokens": 5, "cache_read_input_tokens": 200580}}}) + "\n")
            f.write(json.dumps({"type": "system", "subtype": "compact_boundary",
                                "compactMetadata": {"preTokens": 204183, "postTokens": 14219}}) + "\n")
        with nightmux.stubbed(sav_add=lambda *a: booked.append(a)):
            nightmux.tail_transcript(ct, tp)
        assert ct["ctx_tok"] == 14219 and ("drops",) in booked, (ct.get("ctx_tok"), booked)
        actx, asent = {"autocompact": "200k"}, []
        with nightmux.stubbed(send=lambda *a, **k: asent.append(a), inject=lambda *a: asent.append(a)):
            nightmux.autocompact(actx, {"s": dict(ct, mode="idle", compacted=True)}, "1", "s")
        assert asent == [], asent                      # under the line: re-armed, not retried


def test_turn_spend_and_ladder_booking():
    with isolated(nightmux) as iso:
        tp = os.path.join(nightmux.FILE_DIR, "selfcheck.jsonl")
        os.makedirs(nightmux.FILE_DIR, exist_ok=True)
        rec = json.dumps({"type": "assistant",
                          "message": {"content": [{"type": "text", "text": "one"}]}})
        tst = {}
        with open(tp, "w") as f:                       # leave the file as the next check expects
            f.write(rec + "\n")
        nightmux.tail_transcript(tst, tp)
        assert "spend" not in tst                      # no usage records, nothing to weigh
        with open(tp, "a") as f:                       # what a turn actually cost
            f.write(json.dumps({"type": "assistant", "message": {
                "usage": {"input_tokens": 100, "output_tokens": 10},
                "content": [{"type": "text", "text": "hi"}]}}) + "\n")
        nightmux.tail_transcript(tst, tp)
        assert int(tst["spend"][-1][1]) == 150, tst["spend"]   # 100*1.0 + 10*5.0
        with open(tp, "a") as f:                       # the same turn on haiku, under !ladder
            f.write(json.dumps({"type": "assistant", "message": {
                "model": "claude-haiku-4-5", "usage": {"input_tokens": 100, "output_tokens": 10},
                "content": [{"type": "text", "text": "hi"}]}}) + "\n")
        with nightmux.stubbed(sav_add=lambda k, n=1: tst.setdefault("booked", []).append((k, n))):
            nightmux.tail_transcript(tst, tp, ladder=True)
        assert tst["booked"] == [("model_tokens", 120)], tst["booked"]   # 150 * (1 - 0.2)
        assert nightmux.model_cost("claude-opus-4-8") == 1 and nightmux.model_cost("claude-sonnet-4-6") == 0.6
        os.remove(tp)


def test_parse_amount_and_spend_cap():
    with isolated(nightmux) as iso:
        # One parser, two knobs: a bare number keeps each setting's original unit,
        # a k/M suffix means tokens in both.
        assert nightmux.parse_amount(None) == (None, None) and nightmux.parse_amount("nope") == (None, None)
        assert nightmux.parse_amount(70) == (70, None) and nightmux.parse_amount("150k") == (None, 150000)
        assert nightmux.compact_at({"autocompact": 70}) == (70, None)
        assert nightmux.compact_at({"autocompact": "150k"}) == (None, 150000)
        # A percentage stops being a cost control on a big window, so the token form
        # has to leave the percentage warning where it is rather than chase it.
        assert nightmux.ctx_trip({"autocompact": "150k"}) == nightmux.CTX_WARN
        assert nightmux.spend_cap({}) == (None, None)
        assert nightmux.spend_cap({"spendcap": 12}) == (12, None)
        assert nightmux.spend_cap({"spendcap": "12"}) == (12, None)     # a bare string is turns
        assert nightmux.spend_cap({"spendcap": "500k"}) == (None, 500000)
        assert nightmux.spend_cap({"spendcap": "2M"}) == (None, 2000000)
        assert nightmux.spend_cap({"spendcap": "nope"}) == (None, None)


def test_usage_line():
    with isolated(nightmux) as iso:
        assert nightmux.usage_line({}, {"five_hour": {"used_percentage": 87.4, "resets_at": None},
                           "ctx_pct": 41.2}) == "  5h 87%  ctx 41%"
        assert nightmux.usage_line({}, None) == "" and nightmux.usage_line({}, {}) == ""


def test_cost_report():
    with isolated(nightmux) as iso:
        os.makedirs(nightmux.FILE_DIR, exist_ok=True)
        tcx = os.path.join(nightmux.FILE_DIR, "ctx.jsonl")       # what fills a context window
        with open(tcx, "w") as f:
            for rec in ({"message": {"content": [
                            {"type": "tool_use", "id": "t1", "name": "Bash"},
                            {"type": "tool_use", "id": "t2", "name": "Read"}]}},
                        {"message": {"content": [
                            {"type": "tool_result", "tool_use_id": "t1",
                             "content": "b" * 4000},
                            {"type": "tool_result", "tool_use_id": "t2",
                             "content": "r" * 800}]}},
                        {"message": {"content": [{"type": "text", "text": "x" * 400}]}}):
                f.write(json.dumps(rec) + "\n")
        t = nightmux.token_tally([tcx])                          # no usage records in that file
        assert t["turns"] == 0 and nightmux.cost_report(t, "x").endswith("no usage records yet")
        tcost = os.path.join(nightmux.FILE_DIR, "cost.jsonl")
        with open(tcost, "w") as f:
            for i in (1, 2):
                f.write(json.dumps({"message": {"usage": {
                    "input_tokens": 10, "output_tokens": 100,
                    "cache_creation_input_tokens": 1000,
                    "cache_read_input_tokens": 200000}}}) + "\n")
            f.write("not json\n")
            f.write(json.dumps({"message": {"content": []}}) + "\n")   # no usage: skipped
        t = nightmux.token_tally([tcost, "/no/such/file.jsonl"])
        assert t == {"turns": 2, "in": 20, "write": 2000, "read": 400000, "out": 200}, t
        rep = nightmux.cost_report(t, "title")
        assert "2 turns" in rep and "200,000 / turn" in rep, rep       # avg context
        # 400000*0.1=40000 vs 2000*1.25=2500, 200*5=1000, 20 -> reads dominate
        assert re.search(r"cache reads\s+400,000\s+92%", rep), rep
        os.remove(tcost)


def test_ctx_report():
    with isolated(nightmux) as iso:
        os.makedirs(nightmux.FILE_DIR, exist_ok=True)
        tcx = os.path.join(nightmux.FILE_DIR, "ctx.jsonl")       # what fills a context window
        with open(tcx, "w") as f:
            for rec in ({"message": {"content": [
                            {"type": "tool_use", "id": "t1", "name": "Bash"},
                            {"type": "tool_use", "id": "t2", "name": "Read"}]}},
                        {"message": {"content": [
                            {"type": "tool_result", "tool_use_id": "t1",
                             "content": "b" * 4000},
                            {"type": "tool_result", "tool_use_id": "t2",
                             "content": "r" * 800}]}},
                        {"message": {"content": [{"type": "text", "text": "x" * 400}]}}):
                f.write(json.dumps(rec) + "\n")
        rep = nightmux.ctx_report(tcx)
        assert "Bash" in rep.split("\n")[2] and "1,000" in rep, rep   # biggest first
        assert "assistant text" in rep and "2 tool calls" in rep, rep
        assert f"{(4000 + 800 + 400) // 4:,}" in rep.split("\n")[-1], rep
        assert nightmux.ctx_report(tcx) is rep                  # same size: not re-read
        with open(tcx, "a") as f:                      # ...and a grown file is
            f.write(json.dumps({"message": {"content": [
                {"type": "text", "text": "x" * 40}]}}) + "\n")
        assert nightmux.ctx_report(tcx) is not rep, "a grown transcript kept the stale report"
        os.remove(tcx)
