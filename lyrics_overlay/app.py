import threading

from gi.repository import GLib, Gtk

from . import lyrics
from .clock import SyncClock
from .log import debug
from .metadata import clean
from .player import PlayerWatcher
from .ui import LyricsWindow

APP_ID = "io.github.lyricsoverlay"
POLL_MS = 2000


class App(Gtk.Application):
    """Single-instance app. GTK forwards a second launch to the running
    instance as another 'activate', which we treat as 'close' (toggle)."""

    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.window = None
        self.watcher = None
        self.clock = SyncClock()
        self.song = None      # (artist, title) currently shown/loading

    def do_activate(self):
        if self.window is not None:
            debug("second launch -> closing")
            self.quit()
            return
        debug("starting")
        self.window = LyricsWindow(self)
        self.window.present()
        self.watcher = PlayerWatcher(self.on_player_event)
        if self.watcher.name is None:
            debug("no MPRIS player found")
        GLib.timeout_add(POLL_MS, self.poll)

    # ---- player events ----

    def on_player_event(self, w, kind):
        playing = w.status == "Playing"
        if kind == "none" or w.track is None:
            self.song = None
            self.window.show_message("Waiting for a player…")
            return
        if kind == "seek" and w.seek_pos is not None:
            self.clock.set(w.seek_pos, playing)
        elif kind in ("player", "track"):
            pos = w.position()
            # A new track starts near 0, so a reported 0 is believable here.
            self.clock.set(pos if pos is not None else 0.0, playing)
            self.load(w)
        else:
            self.clock.update(w.position(), playing)
        debug(f"event={kind} player={w.name} status={w.status} clock={self.clock.now():.1f}s")

    def load(self, w):
        t = w.track
        debug(f"raw: {t!r}")
        artist, title = clean(w.name, t.artist, t.title, t.album, t.url)
        debug(f"clean: artist={artist!r} title={title!r}")
        if (artist, title) == self.song:
            return
        self.song = (artist, title)
        if not title:
            self.window.show_message("No song info", w.name.rsplit(".", 1)[-1])
            return
        self.window.show_message(title, artist)
        song, album, length = self.song, t.album, t.length
        threading.Thread(target=lambda: GLib.idle_add(
            self.on_lyrics, song, lyrics.fetch(artist, title, album, length)),
            daemon=True).start()

    def on_lyrics(self, song, result):
        if song != self.song:  # track changed while fetching
            return False
        artist, title = song
        debug(f"lyrics: {result!r}")
        if result.synced:
            self.window.show_synced(result.synced, result.words, self.clock.now)
        elif result.plain:
            self.window.show_plain(result.plain)
        elif result.source == "error":
            self.window.show_message("Couldn't reach LRCLIB", f"{artist} — {title}")
        else:
            self.window.show_message("No lyrics found", f"{artist} — {title}")
        return False

    # ---- periodic drift check ----

    def poll(self):
        w = self.watcher
        if w.name and w.status == "Playing":
            reported = w.position()
            resynced = self.clock.check(reported)
            rep = "n/a" if reported is None else f"{reported:.1f}s"
            debug(f"sync: clock={self.clock.now():.1f}s reported={rep}"
                  f"{' -> resynced' if resynced else ''}"
                  f"{'' if self.clock.sane(reported) else ' (ignored)'}")
        return True
