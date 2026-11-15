"""chunks(): message splitting. Duplicates the first asserts of selfcheck.py until it is gone."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402


def test_chunks():
    chunks, LIMIT = nightmux.chunks, nightmux.LIMIT
    assert chunks("a\nb") == ["a\nb"]
    assert chunks("x" * 10, 4) == ["xxxx", "xxxx", "xx"]
    big = "\n".join("y" * 100 for _ in range(100))
    assert all(len(c) <= LIMIT for c in chunks(big))
    assert "\n".join(chunks(big)) == big
