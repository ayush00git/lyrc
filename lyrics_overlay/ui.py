from gi.repository import Gdk, Gtk

CSS = """
window.lyrics { background-color: #000000; }
.lyrics label { color: #ffffff; font-weight: 800; font-size: 32pt; }
"""


def load_css():
    provider = Gtk.CssProvider()
    try:
        provider.load_from_string(CSS)  # GTK >= 4.12
    except AttributeError:
        provider.load_from_data(CSS.encode(), -1)  # older GTK 4
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), provider,
        Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)  # beat ~/.config/gtk-4.0/gtk.css themes


class LyricsWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="lyrics-overlay")
        load_css()
        self.add_css_class("lyrics")

        self.status = Gtk.Label(label="Waiting for a player…", wrap=True,
                                justify=Gtk.Justification.CENTER)
        self.status.set_valign(Gtk.Align.CENTER)
        self.set_child(self.status)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key)
        self.add_controller(keys)

        self.fullscreen()

    def on_key(self, _ctrl, keyval, _code, _state):
        if keyval in (Gdk.KEY_Escape, Gdk.KEY_q, Gdk.KEY_Q):
            self.get_application().quit()
            return True
        return False
