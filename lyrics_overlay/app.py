from gi.repository import Gtk

from .log import debug
from .ui import LyricsWindow

APP_ID = "io.github.lyricsoverlay"


class App(Gtk.Application):
    """Single-instance app. GTK forwards a second launch to the running
    instance as another 'activate', which we treat as 'close' (toggle)."""

    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.window = None

    def do_activate(self):
        if self.window is not None:
            debug("second launch -> closing")
            self.quit()
            return
        debug("starting")
        self.window = LyricsWindow(self)
        self.window.present()
