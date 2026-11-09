"""Fullscreen black window: synced lyrics, plain lyrics, or a status message."""

import bisect

from gi.repository import Gdk, GLib, Gtk

from .log import debug

CSS = """
window.lyrics, window.lyrics scrolledwindow, window.lyrics viewport { background: #000000; }
.lyrics label { color: #ffffff; font-weight: 800; }
.lyrics label.line { color: rgba(255,255,255,0.28); transition: color 250ms ease-out; }
.lyrics label.line.current { color: #ffffff; }
.lyrics label.plain { color: #ffffff; }
.lyrics label.dim { color: rgba(255,255,255,0.45); font-weight: 600; }
"""


def _add_css(text, provider=None):
    provider = provider or Gtk.CssProvider()
    try:
        provider.load_from_string(text)  # GTK >= 4.12
    except AttributeError:
        provider.load_from_data(text.encode(), -1)  # older GTK 4
    return provider


class LyricsWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="lyrics-overlay")
        display = Gdk.Display.get_default()
        # USER + 1 so a theme in ~/.config/gtk-4.0/gtk.css can't override us.
        prio = Gtk.STYLE_PROVIDER_PRIORITY_USER + 1
        Gtk.StyleContext.add_provider_for_display(display, _add_css(CSS), prio)
        self.font_css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(display, self.font_css, prio)
        self.add_css_class("lyrics")
        self.set_cursor_from_name("none")

        self.message = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER,
                                 valign=Gtk.Align.CENTER)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                           vscrollbar_policy=Gtk.PolicyType.EXTERNAL)
        self.scroller.set_child(self.box)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.stack.add_named(self.message, "message")
        self.stack.add_named(self.scroller, "lyrics")
        self.set_child(self.stack)

        self.lines = []        # [(seconds, Gtk.Label)] in synced mode
        self.current = -1
        self.target = None     # scroll target (synced mode)
        self.time_source = None
        self.last_height = 0
        self.last_frame = None

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key)
        self.add_controller(keys)
        self.add_tick_callback(self.on_tick)
        self.show_message("Waiting for a player…")
        self.fullscreen()

    # ---- content ----

    def _clear(self):
        while (child := self.box.get_first_child()):
            self.box.remove(child)
        self.lines, self.current, self.target, self.time_source = [], -1, None, None
        self.scroller.get_vadjustment().set_value(0)

    def show_message(self, text, sub=""):
        self._clear()
        markup = GLib.markup_escape_text(text)
        if sub:
            markup += f"\n<span size='60%' alpha='50%'>{GLib.markup_escape_text(sub)}</span>"
        self.message.set_markup(markup)
        self.stack.set_visible_child_name("message")

    def show_synced(self, lines, time_source):
        self._clear()
        for t, text in lines:
            label = Gtk.Label(label=text or "♪", wrap=True, justify=Gtk.Justification.CENTER)
            label.add_css_class("line")
            self.box.append(label)
            self.lines.append((t, label))
        self.times = [t for t, _ in self.lines]
        self.time_source = time_source
        self.last_height = 0  # force padding update
        self.stack.set_visible_child_name("lyrics")

    def show_plain(self, text):
        self._clear()
        label = Gtk.Label(label=text, wrap=True, justify=Gtk.Justification.CENTER)
        label.add_css_class("plain")
        self.box.append(label)
        self.last_height = 0
        self.stack.set_visible_child_name("lyrics")

    # ---- animation ----

    def on_tick(self, _widget, frame_clock):
        h, w = self.get_height(), self.get_width()
        if h and h != self.last_height:
            self.last_height = h
            _add_css(f".lyrics label {{ font-size: {max(16, h // 16)}px; }}"
                     f".lyrics label.line {{ margin: {h // 70}px {w // 16}px; }}"
                     f".lyrics label.plain {{ margin: {h // 8}px {w // 16}px; }}",
                     self.font_css)
            pad = h // 2 if self.lines else 0
            self.box.set_margin_top(pad)
            self.box.set_margin_bottom(pad)
            self.current = -1  # recompute scroll target

        if self.time_source:
            i = bisect.bisect_right(self.times, self.time_source()) - 1
            if i != self.current:
                if 0 <= self.current < len(self.lines):
                    self.lines[self.current][1].remove_css_class("current")
                if i >= 0:
                    self.lines[i][1].add_css_class("current")
                    debug(f"line {i}: {self.lines[i][1].get_label()!r}")
                self.current = i
                self.target = None
            if self.target is None:  # None until layout is done
                self.target = self._center_of(max(i, 0))

        now = frame_clock.get_frame_time() / 1e6
        dt = min(0.1, now - self.last_frame) if self.last_frame else 0.016
        self.last_frame = now
        if self.target is not None:
            adj = self.scroller.get_vadjustment()
            v = adj.get_value()
            step = (self.target - v) * min(1.0, dt * 6)
            adj.set_value(self.target if abs(self.target - v) < 0.5 else v + step)
        return True

    def _center_of(self, i):
        label = self.lines[i][1]
        ok, rect = label.compute_bounds(self.box)
        if not ok:
            return None
        return rect.origin.y + rect.size.height / 2 - self.scroller.get_height() / 2

    # ---- keys ----

    def on_key(self, _ctrl, keyval, _code, _state):
        if keyval in (Gdk.KEY_Escape, Gdk.KEY_q, Gdk.KEY_Q):
            self.get_application().quit()
            return True
        steps = {Gdk.KEY_Up: -0.08, Gdk.KEY_Down: 0.08, Gdk.KEY_k: -0.08, Gdk.KEY_j: 0.08,
                 Gdk.KEY_Page_Up: -0.8, Gdk.KEY_Page_Down: 0.8, Gdk.KEY_space: 0.8}
        if keyval in steps and not self.time_source:
            adj = self.scroller.get_vadjustment()
            adj.set_value(adj.get_value() + steps[keyval] * adj.get_page_size())
            return True
        return False

