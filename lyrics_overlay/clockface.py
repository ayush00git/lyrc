"""Full-screen digital clock: HH:MM:SS across the screen, date underneath."""

import re

import gi

gi.require_version("PangoCairo", "1.0")
from gi.repository import Gio, GLib, Gtk, Pango, PangoCairo  # noqa: E402

WIDTH_FILL = 0.90   # time spans 90% of the screen width...
HEIGHT_MAX = 0.45   # ...unless that would make it taller than 45% of the height
SECONDS_ALPHA = "55%"


def _uses_12h():
    """Follow GNOME's 12h/24h setting when available; default to 24h."""
    schema_id = "org.gnome.desktop.interface"
    source = Gio.SettingsSchemaSource.get_default()
    schema = source.lookup(schema_id, True) if source else None
    if schema is None or not schema.has_key("clock-format"):
        return False
    return Gio.Settings.new(schema_id).get_string("clock-format") == "12h"


class ClockFace(Gtk.DrawingArea):
    def __init__(self):
        super().__init__(hexpand=True, vexpand=True)
        self.inverted = False
        self.twelve_hour = _uses_12h()
        self.last_second = None
        self.set_draw_func(self._draw)

    def tick(self):
        """Call every frame; redraws only when the second changes."""
        s = GLib.DateTime.new_now_local().get_second()
        if s != self.last_second:
            self.last_second = s
            self.queue_draw()

    def _layout(self, cr, px, weight):
        layout = PangoCairo.create_layout(cr)
        font = Pango.FontDescription.from_string("Sans")
        font.set_absolute_size(px * Pango.SCALE)
        font.set_weight(weight)
        layout.set_font_description(font)
        return layout

    def _markup(self, hm, ss):
        """HH:MM in full color, :SS dimmed; equal-width digits so nothing shifts."""
        color = "#000000" if self.inverted else "#ffffff"
        return (f"<span font_features='tnum' foreground='{color}'>{hm}"
                f"<span alpha='{SECONDS_ALPHA}'>:{ss}</span></span>")

    def _draw(self, _area, cr, w, h):
        fg = (0.0, 0.0, 0.0) if self.inverted else (1.0, 1.0, 1.0)
        cr.set_source_rgb(*((1.0, 1.0, 1.0) if self.inverted else (0.0, 0.0, 0.0)))
        cr.paint()

        now = GLib.DateTime.new_now_local()
        hm = now.format("%I:%M" if self.twelve_hour else "%H:%M")
        if self.twelve_hour:
            hm = hm.lstrip("0")

        # Fit to the screen: measure a same-shape sample at 100px, then scale.
        probe = self._layout(cr, 100, Pango.Weight.HEAVY)
        probe.set_markup(self._markup(re.sub(r"\d", "0", hm), "00"), -1)
        pw, ph = probe.get_pixel_size()
        px = min(100 * w * WIDTH_FILL / max(pw, 1), 100 * h * HEIGHT_MAX / max(ph, 1))

        time = self._layout(cr, px, Pango.Weight.HEAVY)
        time.set_markup(self._markup(hm, now.format("%S")), -1)
        tw, th = time.get_pixel_size()

        sub = now.format("%A, %-d %B")
        if self.twelve_hour:
            sub = now.format("%p") + "  ·  " + sub
        date = self._layout(cr, max(14, px * 0.14), Pango.Weight.SEMIBOLD)
        date.set_text(sub, -1)
        dw, dh = date.get_pixel_size()

        top = (h - (th + dh)) / 2
        cr.move_to((w - tw) / 2, top)
        PangoCairo.show_layout(cr, time)
        cr.set_source_rgba(*fg, 0.45)
        cr.move_to((w - dw) / 2, top + th)
        PangoCairo.show_layout(cr, date)
