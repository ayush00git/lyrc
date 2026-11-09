from gi.repository import Gtk

from .log import debug
from .player import PlayerWatcher
from .ui import LyricsWindow

APP_ID = "io.github.lyricsoverlay"


class App(Gtk.Application):
    """Single-instance app. GTK forwards a second launch to the running
    instance as another 'activate', which we treat as 'close' (toggle)."""

    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.window = None
        self.watcher = None

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

    def on_player_event(self, w, kind):
        debug(f"event={kind} player={w.name} status={w.status} pos={w.position()}")
        if kind in ("player", "track") and w.track:
            debug(f"raw: {w.track!r}")
        if w.track is None:
            self.window.status.set_label("Waiting for a player…")
        else:
            self.window.status.set_label(f"{w.track.artist}\n{w.track.title}\n({w.status})")
