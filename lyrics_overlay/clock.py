"""Local playback clock: anchored to the player's position, counts forward itself."""

import time

DRIFT = 1.0  # seconds of disagreement before we re-anchor


class SyncClock:
    def __init__(self):
        self.pos = 0.0
        self.at = time.monotonic()
        self.playing = False

    def now(self):
        return self.pos + (time.monotonic() - self.at if self.playing else 0.0)

    def set(self, pos, playing):
        self.pos, self.at, self.playing = max(0.0, pos), time.monotonic(), playing

    def sane(self, reported):
        """Some players (some Spotify versions) report 0 forever. Treat a 0
        as bogus when our own clock says we're clearly past the start."""
        if reported is None or reported < 0:
            return False
        return not (reported < 0.5 and self.now() > DRIFT)

    def update(self, reported, playing):
        """Re-anchor on play/pause changes; trust the reported position if sane."""
        self.set(reported if self.sane(reported) else self.now(), playing)

    def check(self, reported):
        """Periodic drift check. Returns True if we re-anchored."""
        if self.sane(reported) and abs(reported - self.now()) > DRIFT:
            self.set(reported, self.playing)
            return True
        return False
