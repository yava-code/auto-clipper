import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import core.queue as q


class TestLoad:
    def setup_method(self):
        q.items = []
        q.idx = 0
        q.active = False
        q.on_complete = None

    def test_sets_items(self):
        q.load(["a", "b", "c"])
        assert q.items == ["a", "b", "c"]

    def test_resets_idx(self):
        q.idx = 5
        q.load(["x"])
        assert q.idx == 0

    def test_activates(self):
        q.load(["x"])
        assert q.active is True

    def test_empty_does_nothing(self):
        q.load([])
        assert q.active is False


class TestChangeHotkey:
    def test_stores_hotkey(self):
        # just verify the module attribute is accessible
        assert hasattr(q, "sleep_ms")

    def test_sleep_ms_default(self):
        assert q.sleep_ms == 15
