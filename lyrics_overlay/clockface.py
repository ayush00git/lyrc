"""Full-screen clock: big time, date, and a ring whose arc sweeps smoothly with the seconds."""

import math

import gi

gi.require_version("PangoCairo", "1.0")
from gi.repository import Gio, GLib, Gtk, Pango, PangoCairo  # noqa: E402


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
        self.set_draw_func(self._draw)

    def _colors(self):
        fg = (0.0, 0.0, 0.0) if self.inverted else (1.0, 1.0, 1.0)
        return {
            "bg": (1.0, 1.0, 1.0) if self.inverted else (0.0, 0.0, 0.0),
            "time": (*fg, 1.0),
            "date": (*fg, 0.45),
            "track": (*fg, 0.08),
            "arc": (*fg, 0.42),
            "dot": (*fg, 1.0),
        }

    def _text(self, cr, text, px, weight, rgba, cx, cy):
        layout = PangoCairo.create_layout(cr)
        font = Pango.FontDescription.from_string("Sans")
        font.set_absolute_size(px * Pango.SCALE)
        font.set_weight(weight)
        layout.set_font_description(font)
        layout.set_text(text, -1)
        _ink, logical = layout.get_pixel_extents()
        cr.set_source_rgba(*rgba)
        cr.move_to(cx - logical.width / 2, cy - logical.height / 2)
        PangoCairo.show_layout(cr, layout)

    def _draw(self, _area, cr, w, h):
        c = self._colors()
        cr.set_source_rgb(*c["bg"])
        cr.paint()

        now = GLib.DateTime.new_now_local()
        sec = now.get_second() + now.get_microsecond() / 1e6
        cx, cy = w / 2, h / 2
        r = min(w, h) * 0.36
        line = max(2.0, r * 0.012)

        # Ring track, then the sweeping arc. Even minutes fill the ring,
        # odd minutes empty it, so it never snaps back to zero.
        top = -math.pi / 2
        frac = sec / 60
        cr.set_line_width(line)
        cr.set_line_cap(1)  # round
        cr.set_source_rgba(*c["track"])
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.stroke()
        if now.get_minute() % 2 == 0:
            start, end = top, top + frac * 2 * math.pi
        else:
            start, end = top + frac * 2 * math.pi, top + 2 * math.pi
        if end - start > 0.001:
            cr.set_source_rgba(*c["arc"])
            cr.arc(cx, cy, r, start, end)
            cr.stroke()
        # Bright dot at the moving tip.
        tip = top + frac * 2 * math.pi
        cr.set_source_rgba(*c["dot"])
        cr.arc(cx + r * math.cos(tip), cy + r * math.sin(tip), line * 2.2, 0, 2 * math.pi)
        cr.fill()

        fmt = "%I:%M" if self.twelve_hour else "%H:%M"
        time_text = now.format(fmt).lstrip("0") if self.twelve_hour else now.format(fmt)
        self._text(cr, time_text, r * 0.42, Pango.Weight.HEAVY, c["time"], cx, cy - r * 0.06)
        sub = now.format("%A, %-d %B")
        if self.twelve_hour:
            sub = now.format("%p") + "  ·  " + sub
        self._text(cr, sub, r * 0.075, Pango.Weight.SEMIBOLD, c["date"], cx, cy + r * 0.30)
