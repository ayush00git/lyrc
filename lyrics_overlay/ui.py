"""Fullscreen black window: synced lyrics (word or line view), plain lyrics, or a message."""

import bisect

from gi.repository import Gdk, GLib, Gtk, Pango

from . import settings
from .clockface import ClockFace
from .log import debug

CSS = """
window.lyrics, window.lyrics scrolledwindow, window.lyrics viewport { background: #000000; }
.lyrics label { color: #ffffff; font-weight: 800; }
.lyrics label.line { color: rgba(255,255,255,0.28); transition: color 250ms ease-out; }
.lyrics label.line.current { color: #ffffff; }
.lyrics label.plain { color: #ffffff; }
.lyrics label.hint { color: rgba(255,255,255,0.6); font-size: 20px; font-weight: 600;
                     background: rgba(255,255,255,0.08); border-radius: 12px; padding: 6px 16px; }

/* Inverted (double-tap Shift): white background, black text. */
window.lyrics.inverted, window.lyrics.inverted scrolledwindow,
window.lyrics.inverted viewport { background: #ffffff; }
.lyrics.inverted label, .lyrics.inverted label.plain,
.lyrics.inverted label.line.current { color: #000000; }
.lyrics.inverted label.line { color: rgba(0,0,0,0.28); }
.lyrics.inverted label.hint { color: rgba(0,0,0,0.6); background: rgba(0,0,0,0.08); }
"""
DOUBLE_TAP_S = 0.4
WORD_FADE_S = 0.09  # quick fade-in for each new word


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
        self.add_css_class("lyrics")
        self.set_cursor_from_name("none")

        self.message = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER,
                                 valign=Gtk.Align.CENTER)
        # Line view: a scrolling column of labels.
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                           vscrollbar_policy=Gtk.PolicyType.EXTERNAL)
        self.scroller.set_child(self.box)
        # Word view: one label; each new word fades in quickly (see on_tick).
        # A single label on purpose: GTK can leave a hidden label at a stale font size.
        self.word_label = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        self.word_label.add_css_class("word")
        self.word_shown_at = None

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.stack.add_named(self.message, "message")
        self.stack.add_named(self.scroller, "lyrics")
        self.stack.add_named(self.word_label, "words")
        self.clockface = ClockFace()
        self.stack.add_named(self.clockface, "clock")
        self.page = "message"   # lyrics page to show when the clock is off
        self.clock_mode = False  # Shift+C toggles
        # Small hint at the bottom when a setting changes ("Size 120%").
        self.hint = Gtk.Label(halign=Gtk.Align.CENTER, valign=Gtk.Align.END,
                              margin_bottom=40, visible=False)
        self.hint.add_css_class("hint")
        self.hint_timer = 0
        overlay = Gtk.Overlay(child=self.stack)
        overlay.add_overlay(self.hint)
        self.set_child(overlay)

        self.prefs = settings.load()
        self.word_mode = self.prefs["word_mode"]  # 'l' toggles
        if self.prefs["inverted"]:
            self.add_css_class("inverted")
        self.clockface.inverted = self.prefs["inverted"]
        self.shift_clean = False  # Shift is down and no other key was pressed
        self.last_shift_tap = 0.0
        self.lines = []        # [(seconds, Gtk.Label)] in synced mode
        self.words = []        # [(seconds, word)]
        self.current = -1
        self.current_word = -2
        self.target = None     # scroll target (line view)
        self.time_source = None
        self.last_height = 0
        self.last_frame = None

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_key)
        keys.connect("key-released", self.on_key_release)
        self.add_controller(keys)
        self.add_tick_callback(self.on_tick)
        self.show_message("Waiting for a player…")
        self.fullscreen()

    # ---- content ----

    def _clear(self):
        while (child := self.box.get_first_child()):
            self.box.remove(child)
        self.lines, self.words, self.time_source = [], [], None
        self.current, self.current_word, self.target = -1, -2, None
        self.scroller.get_vadjustment().set_value(0)

    def _show_page(self, name):
        """Switch lyrics page; while the clock is on, just remember it."""
        self.page = name
        if not self.clock_mode:
            self.stack.set_visible_child_name(name)

    def toggle_clock(self):
        self.clock_mode = not self.clock_mode
        self.stack.set_visible_child_name("clock" if self.clock_mode else self.page)
        self.current, self.current_word, self.target = -1, -2, None
        self.last_height = 0
        for _, label in self.lines:
            label.remove_css_class("current")
        self._set_hint("Clock" if self.clock_mode else "Lyrics")
        self.get_application().refresh_awake()

    def show_message(self, text, sub=""):
        self._clear()
        markup = GLib.markup_escape_text(text)
        if sub:
            markup += f"\n<span size='60%' alpha='50%'>{GLib.markup_escape_text(sub)}</span>"
        self.message.set_markup(markup)
        self._show_page("message")

    def show_synced(self, lines, words, time_source):
        self._clear()
        for t, text in lines:
            label = Gtk.Label(label=text or "♪", wrap=True, justify=Gtk.Justification.CENTER)
            label.add_css_class("line")
            self.box.append(label)
            self.lines.append((t, label))
        self.times = [t for t, _ in self.lines]
        self.words = words
        self._build_chunks()
        self.time_source = time_source
        self.last_height = 0  # force padding update
        self._show_synced_view()

    def _build_chunks(self):
        """Group words N at a time (Shift+N), never across a line break."""
        n = self.prefs["words_at_once"]
        groups = []  # [(start, line index, [words])]
        for t, w in self.words:
            li = bisect.bisect_right(self.times, t + 1e-6) - 1
            last = groups[-1] if groups else None
            if (last and last[1] == li and len(last[2]) < n
                    and w != "♪" and last[2][-1] != "♪"):
                last[2].append(w)
            else:
                groups.append((t, li, [w]))
        self.chunks = [(t, " ".join(ws)) for t, _, ws in groups]
        self.chunk_times = [t for t, _ in self.chunks]
        self.current_word = -2

    def _show_synced_view(self):
        use_words = self.word_mode and self.words
        self._show_page("words" if use_words else "lyrics")
        for _, label in self.lines:
            label.remove_css_class("current")
        self.current, self.current_word, self.target = -1, -2, None
        self.last_height = 0

    def show_plain(self, text):
        self._clear()
        label = Gtk.Label(label=text, wrap=True, justify=Gtk.Justification.CENTER)
        label.add_css_class("plain")
        self.box.append(label)
        self.last_height = 0
        self._show_page("lyrics")

    # ---- animation ----

    def on_tick(self, _widget, frame_clock):
        h, w = self.get_height(), self.get_width()
        if h and h != self.last_height:
            self.last_height = h
            self._apply_sizes(w, h)
            pad = h // 2 if self.lines else 0
            self.box.set_margin_top(pad)
            self.box.set_margin_bottom(pad)
            self.target = None  # recompute scroll target

        if self.time_source:
            now = self.time_source()
            if self.clock_mode:
                pass
            elif self.page == "words":
                self._update_word(now)
            else:
                self._update_line(now)
        if self.clock_mode:
            self.clockface.queue_draw()  # redraw every frame: smooth seconds sweep

        t = frame_clock.get_frame_time() / 1e6
        if self.word_shown_at is not None:
            if self.word_shown_at < 0:  # word changed: start fade on this frame
                self.word_shown_at = t
            p = min(1.0, (t - self.word_shown_at) / WORD_FADE_S)
            self.word_label.set_opacity(0.2 + 0.8 * p)
            if p >= 1.0:
                self.word_shown_at = None
        dt = min(0.1, t - self.last_frame) if self.last_frame else 0.016
        self.last_frame = t
        if self.target is not None:
            adj = self.scroller.get_vadjustment()
            v = adj.get_value()
            step = (self.target - v) * min(1.0, dt * 6)
            adj.set_value(self.target if abs(self.target - v) < 0.5 else v + step)
        return True

    def _apply_sizes(self, w, h):
        """Set font size and margins directly on every label. (Not via CSS:
        GTK can leave hidden widgets at a stale CSS font size.)"""
        k = self.prefs["font_scale"]
        text_px, word_px = max(12, h / 16 * k), max(16, h / 6 * k)

        def size(label, px, vmargin, hmargin):
            attrs = Pango.AttrList()
            attrs.insert(Pango.attr_size_new_absolute(int(px * Pango.SCALE)))
            label.set_attributes(attrs)
            label.set_margin_top(vmargin)
            label.set_margin_bottom(vmargin)
            label.set_margin_start(hmargin)
            label.set_margin_end(hmargin)

        size(self.message, text_px, 0, w // 16)
        size(self.word_label, word_px, 0, w // 20)
        for _, label in self.lines:
            size(label, text_px, h // 70, w // 16)
        plain = self.box.get_first_child()
        if plain is not None and plain.has_css_class("plain"):
            size(plain, text_px, h // 8, w // 16)

    def _update_word(self, now):
        i = bisect.bisect_right(self.chunk_times, now) - 1
        if i == self.current_word:
            return
        self.current_word = i
        text = self.chunks[i][1] if i >= 0 else "♪"
        self.word_label.set_label(text)
        self.word_shown_at = -1

    def _update_line(self, now):
        i = bisect.bisect_right(self.times, now) - 1
        if i != self.current:
            if 0 <= self.current < len(self.lines):
                self.lines[self.current][1].remove_css_class("current")
            if i >= 0:
                self.lines[i][1].add_css_class("current")
                debug(f"line {i}: {self.lines[i][1].get_label()!r}")
            self.current = i
            self.target = None
        if self.target is None and self.lines:  # None until layout is done
            self.target = self._center_of(max(i, 0))

    def _center_of(self, i):
        """Scroll value that puts line i in the middle of the screen."""
        ok, rect = self.lines[i][1].compute_bounds(self.box)
        if not ok:
            return None
        # Bounds are relative to the box, but scrolling counts its top margin too.
        y = self.box.get_margin_top() + rect.origin.y + rect.size.height / 2
        return y - self.scroller.get_height() / 2

    # ---- keys ----

    def _set(self, key, value, hint):
        self.prefs[key] = value
        settings.save(self.prefs)
        debug(f"setting {key}={value}")
        self._set_hint(hint)

    def _set_hint(self, hint):
        self.hint.set_label(hint)
        self.hint.set_visible(True)
        if self.hint_timer:
            GLib.source_remove(self.hint_timer)
        self.hint_timer = GLib.timeout_add(1200, self._hide_hint)

    def _hide_hint(self):
        self.hint.set_visible(False)
        self.hint_timer = 0
        return False

    def on_key_release(self, _ctrl, keyval, _code, _state):
        """Double-tap Shift (with no other key in between) toggles colors."""
        if keyval not in (Gdk.KEY_Shift_L, Gdk.KEY_Shift_R) or not self.shift_clean:
            return
        self.shift_clean = False
        now = GLib.get_monotonic_time() / 1e6
        if now - self.last_shift_tap < DOUBLE_TAP_S:
            self.last_shift_tap = 0.0
            inverted = not self.prefs["inverted"]
            (self.add_css_class if inverted else self.remove_css_class)("inverted")
            self.clockface.inverted = inverted
            self._set("inverted", inverted, "Light mode" if inverted else "Dark mode")
        else:
            self.last_shift_tap = now

    def on_key(self, ctrl, keyval, code, state):
        if keyval in (Gdk.KEY_Shift_L, Gdk.KEY_Shift_R):
            self.shift_clean = True
            return False
        self.shift_clean, self.last_shift_tap = False, 0.0  # e.g. Shift+3 is not a tap
        if keyval in (Gdk.KEY_Escape, Gdk.KEY_q, Gdk.KEY_Q):
            self.get_application().quit()
            return True
        # Up/Down: font size.
        if keyval in (Gdk.KEY_Up, Gdk.KEY_Down):
            k = self.prefs["font_scale"] * (1.1 if keyval == Gdk.KEY_Up else 1 / 1.1)
            k = round(min(3.0, max(0.4, k)), 3)
            self._set("font_scale", k, f"Size {round(k * 100)}%")
            self.last_height = 0  # re-apply sizes and re-center on next frame
            return True
        # Shift+1..9: words at once; Shift+C: clock. Look up the unshifted key so it works on any layout.
        if state & Gdk.ModifierType.SHIFT_MASK:
            ok, base, *_ = self.get_display().translate_key(code, 0, ctrl.get_group())
            if (ok and base == Gdk.KEY_c) or keyval == Gdk.KEY_C:
                self.toggle_clock()
                return True
            if ok and Gdk.KEY_1 <= base <= Gdk.KEY_9:
                n = base - Gdk.KEY_0
                self._set("words_at_once", n, f"{n} word{'s' if n > 1 else ''} at a time")
                if self.words:
                    self._build_chunks()
                return True
        if keyval in (Gdk.KEY_l, Gdk.KEY_L) and self.time_source:
            self.word_mode = not self.word_mode
            self.prefs["word_mode"] = self.word_mode
            settings.save(self.prefs)
            debug(f"view: {'words' if self.word_mode else 'lines'}")
            self._show_synced_view()
            return True
        steps = {Gdk.KEY_k: -0.08, Gdk.KEY_j: 0.08,
                 Gdk.KEY_Page_Up: -0.8, Gdk.KEY_Page_Down: 0.8, Gdk.KEY_space: 0.8}
        if keyval in steps and not self.time_source:
            adj = self.scroller.get_vadjustment()
            adj.set_value(adj.get_value() + steps[keyval] * adj.get_page_size())
            return True
        return False
