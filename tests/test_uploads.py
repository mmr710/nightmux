"""test_uploads: cut from the old monolithic selfcheck() (the last part)."""
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import nightmux  # noqa: E402
from _iso import isolated  # noqa: E402
from _legacy import legacy_stubs  # noqa: E402


def test_voice_audio_video_note_updates():
    with isolated(nightmux) as iso:
        legacy_stubs(nightmux)
        # Voice/audio/video-note updates ride the same download-and-type path as a
        # photo or a document — just another field to notice on the way in.
        cfg5, fetched = {"chat_id": -1}, []
        with nightmux.stubbed(fetch_file=lambda c, fid, name=None: fetched.append((fid, name)) or "/f/x",
                    handle=lambda *a, **k: None, api=lambda c, m, **kw: {}):
            nightmux.process(cfg5, {}, threading.Lock(), {7}, {
                "update_id": 1, "message": {"chat": {"id": -1}, "from": {"id": 7},
                 "message_thread_id": "1", "voice": {"file_id": "v1", "duration": 3}}})
            assert fetched[-1] == ("v1", None), fetched
            nightmux.process(cfg5, {}, threading.Lock(), {7}, {
                "update_id": 2, "message": {"chat": {"id": -1}, "from": {"id": 7},
                 "message_thread_id": "1",
                 "video_note": {"file_id": "vn1", "duration": 5}}})
            assert fetched[-1] == ("vn1", None), fetched
            nightmux.process(cfg5, {}, threading.Lock(), {7}, {   # audio can carry a name; voice never does
                "update_id": 3, "message": {"chat": {"id": -1}, "from": {"id": 7},
                 "message_thread_id": "1",
                 "audio": {"file_id": "a1", "file_name": "song.mp3"}}})
            assert fetched[-1] == ("a1", "song.mp3"), fetched
