"""MPRIS2 watcher: tracks the active media player over the D-Bus session bus."""

from gi.repository import Gio, GLib

from .log import debug

PREFIX = "org.mpris.MediaPlayer2."
PATH = "/org/mpris/MediaPlayer2"
IFACE = "org.mpris.MediaPlayer2.Player"
PROPS = "org.freedesktop.DBus.Properties"
TIMEOUT_MS = 1000


class Track:
    """Raw metadata of one track, straight from the player."""

    def __init__(self, md):
        self.title = str(md.get("xesam:title", "") or "")
        artist = md.get("xesam:artist", []) or []
        self.artist = ", ".join(artist) if isinstance(artist, list) else str(artist)
        self.album = str(md.get("xesam:album", "") or "")
        self.length = int(md.get("mpris:length", 0) or 0) / 1e6  # seconds
        self.url = str(md.get("xesam:url", "") or "")
        self.trackid = str(md.get("mpris:trackid", "") or "")

    def key(self):
        return (self.trackid, self.title, self.artist)

    def __repr__(self):
        return (f"title={self.title!r} artist={self.artist!r} album={self.album!r} "
                f"length={self.length:.0f}s url={self.url!r}")


class PlayerWatcher:
    """Calls on_event(watcher, kind) with kind in: 'player', 'track', 'status', 'seek', 'none'.
    Read .name, .status, .track and position() for current state."""

    def __init__(self, on_event):
        self.on_event = on_event
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        self.players = {}   # well-known name -> {"owner", "status", "track"}
        self.name = None
        self.status = "Stopped"
        self.track = None

        self.bus.signal_subscribe(
            "org.freedesktop.DBus", "org.freedesktop.DBus", "NameOwnerChanged",
            "/org/freedesktop/DBus", None, Gio.DBusSignalFlags.NONE, self._on_owner_changed)
        self.bus.signal_subscribe(
            None, PROPS, "PropertiesChanged", PATH, None,
            Gio.DBusSignalFlags.NONE, self._on_props_changed)
        self.bus.signal_subscribe(
            None, IFACE, "Seeked", PATH, None,
            Gio.DBusSignalFlags.NONE, self._on_seeked)

        for name in self._call("org.freedesktop.DBus", "/org/freedesktop/DBus",
                               "org.freedesktop.DBus", "ListNames", None)[0]:
            if name.startswith(PREFIX):
                self._add(name)
        self._choose()

    # ---- D-Bus helpers ----

    def _call(self, dest, path, iface, method, args):
        res = self.bus.call_sync(dest, path, iface, method, args, None,
                                 Gio.DBusCallFlags.NONE, TIMEOUT_MS, None)
        return res.unpack()

    def _refresh(self, name):
        """Re-read status and metadata for one player. False if it is gone."""
        try:
            props = self._call(name, PATH, PROPS, "GetAll", GLib.Variant("(s)", (IFACE,)))[0]
        except GLib.Error as e:
            debug(f"player {name}: GetAll failed: {e.message}")
            return False
        p = self.players[name]
        p["status"] = props.get("PlaybackStatus", "Stopped")
        p["track"] = Track(props.get("Metadata", {}) or {})
        return True

    def _add(self, name):
        try:
            owner = self._call("org.freedesktop.DBus", "/org/freedesktop/DBus",
                               "org.freedesktop.DBus", "GetNameOwner",
                               GLib.Variant("(s)", (name,)))[0]
        except GLib.Error:
            return
        self.players[name] = {"owner": owner, "status": "Stopped", "track": None}
        if not self._refresh(name):
            del self.players[name]
            return
        debug(f"found player {name} ({self.players[name]['status']})")

    def _name_for(self, owner):
        for name, p in self.players.items():
            if p["owner"] == owner:
                return name
        return None

    # ---- signal handlers ----

    def _on_owner_changed(self, _bus, _sender, _path, _iface, _sig, params):
        name, _old, new = params.unpack()
        if not name.startswith(PREFIX):
            return
        if new:
            self._add(name)
        else:
            debug(f"player {name} went away")
            self.players.pop(name, None)
        self._choose()

    def _on_props_changed(self, _bus, sender, _path, _iface, _sig, params):
        if params.unpack()[0] != IFACE:
            return
        name = self._name_for(sender)
        if name and self._refresh(name):
            self._choose()

    def _on_seeked(self, _bus, sender, _path, _iface, _sig, params):
        if self._name_for(sender) == self.name:
            debug(f"seeked to {params.unpack()[0] / 1e6:.1f}s")
            self.on_event(self, "seek")

    # ---- selection ----

    def _choose(self):
        """Keep the current player while it plays; else take any playing one;
        else keep the current (paused) one; else any player at all."""
        playing = [n for n, p in self.players.items() if p["status"] == "Playing"]
        if self.name in playing:
            pick = self.name
        elif playing:
            pick = playing[0]
        elif self.name in self.players:
            pick = self.name
        else:
            pick = next(iter(self.players), None)

        if pick is None:
            if self.name is not None:
                self.name, self.track, self.status = None, None, "Stopped"
                self.on_event(self, "none")
            return

        p = self.players[pick]
        if pick != self.name:
            self.name, self.status, self.track = pick, p["status"], p["track"]
            debug(f"using player {pick} ({self.status})")
            self.on_event(self, "player")
            return
        if p["track"] and (self.track is None or p["track"].key() != self.track.key()):
            self.track = p["track"]
            self.on_event(self, "track")
        if p["status"] != self.status:
            self.status = p["status"]
            self.on_event(self, "status")

    def position(self):
        """Player-reported position in seconds, or None if unavailable."""
        if not self.name:
            return None
        try:
            v = self._call(self.name, PATH, PROPS, "Get",
                           GLib.Variant("(ss)", (IFACE, "Position")))[0]
            return int(v) / 1e6
        except (GLib.Error, TypeError, ValueError):
            return None
