import unittest
from unittest import mock

from lyrics_overlay import clock as clockmod
from lyrics_overlay.clock import SyncClock


class TestClock(unittest.TestCase):
    def setUp(self):
        self.t = 100.0
        p = mock.patch.object(clockmod.time, "monotonic", lambda: self.t)
        p.start()
        self.addCleanup(p.stop)
        self.c = SyncClock()

    def test_counts_while_playing_only(self):
        self.c.set(10, True)
        self.t += 5
        self.assertAlmostEqual(self.c.now(), 15)
        self.c.update(15, False)
        self.t += 5
        self.assertAlmostEqual(self.c.now(), 15)

    def test_ignores_bogus_zero(self):
        self.c.set(30, True)
        self.t += 2
        self.c.update(0, False)           # pause, player says 0
        self.assertAlmostEqual(self.c.now(), 32)
        self.assertFalse(self.c.check(0))

    def test_zero_at_start_is_fine(self):
        self.c.set(0, True)
        self.t += 0.3
        self.assertFalse(self.c.check(0.0))

    def test_resync_on_drift(self):
        self.c.set(10, True)
        self.t += 2
        self.assertFalse(self.c.check(12.4))
        self.assertTrue(self.c.check(20))
        self.assertAlmostEqual(self.c.now(), 20)


if __name__ == "__main__":
    unittest.main()
