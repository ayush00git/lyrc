"""Lyrics lookup: local cache first, then LRCLIB. Blocking; call from a thread."""

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from .log import debug

API = "https://lrclib.net/api"
UA = "lyrics-overlay/0.1"
CACHE_DIR = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"),
                         "lyrics-overlay")
MISS_TTL = 24 * 3600  # retry "not found" songs after a day


class Lyrics:
    def __init__(self, source, lrc="", plain=None):
        self.source = source            # cache / lrclib-get / lrclib-search / none / error
        self.synced = parse_lrc(lrc)    # [(seconds, line), ...]
        self.words = word_timeline(parse_lrc(lrc, keep_word_tags=True))  # [(seconds, word), ...]
        self.plain = plain or ""

    def __repr__(self):
        kind = "synced" if self.synced else "plain" if self.plain else "nothing"
        return f"source={self.source} type={kind} lines={len(self.synced) or self.plain.count(chr(10)) + bool(self.plain)}"


# ---- LRC parsing ----

TAG = re.compile(r"\[(\d+):(\d+(?:[.:]\d+)?)\]")
WORD_TAG = re.compile(r"<(\d+):(\d+(?:\.\d+)?)>")
OFFSET = re.compile(r"\[offset:\s*([+-]?\d+)\]", re.I)


def parse_lrc(text, keep_word_tags=False):
    """'[01:02.50]line' -> [(62.5, 'line'), ...] sorted by time.
    Enhanced LRC word stamps ('<01:02.80>word') are stripped unless kept."""
    m = OFFSET.search(text or "")
    offset = int(m.group(1)) / 1000 if m else 0.0
    out = []
    for raw in (text or "").splitlines():
        stamps = []
        while (m := TAG.match(raw)):
            stamps.append(int(m.group(1)) * 60 + float(m.group(2).replace(":", ".")))
            raw = raw[m.end():]
        if not keep_word_tags:
            raw = WORD_TAG.sub("", raw)
        for t in stamps:
            out.append((max(0.0, t - offset), re.sub(r"\s+", " ", raw).strip()))
    out.sort(key=lambda x: x[0])
    return out


WORD_PACE = 0.42  # max seconds per word when spreading a line over its duration


def word_timeline(lines):
    """Split timed lines into timed words. Uses enhanced-LRC word stamps when
    present, otherwise spreads words over the line, weighted by length."""
    out = []
    for i, (t0, text) in enumerate(lines):
        t1 = lines[i + 1][0] if i + 1 < len(lines) else t0 + 5.0
        if WORD_TAG.search(text):
            stamp = t0
            for part in re.split(r"(<\d+:\d+(?:\.\d+)?>)", text):
                m = WORD_TAG.fullmatch(part)
                if m:
                    stamp = int(m.group(1)) * 60 + float(m.group(2))
                    continue
                for w in part.split():
                    out.append((stamp, w))
            continue
        words = text.split()
        if not words:
            out.append((t0, "♪"))
            continue
        span = max(0.1, min((t1 - t0) * 0.9, len(words) * WORD_PACE))
        weights = [len(w) + 2 for w in words]
        total, acc = sum(weights), 0
        for w, wt in zip(words, weights):
            out.append((t0 + span * acc / total, w))
            acc += wt
        if t1 - (t0 + span) > 3.0:  # long gap after the line: show a note
            out.append((t0 + span + 1.0, "♪"))
    out.sort(key=lambda x: x[0])
    return out


# ---- cache ----

def _cache_path(artist, title):
    key = f"{artist}\n{title}".lower()
    slug = re.sub(r"[^a-z0-9]+", "-", key)[:60].strip("-")
    return os.path.join(CACHE_DIR, f"{slug}-{hashlib.sha1(key.encode()).hexdigest()[:8]}.json")


def _cache_read(path):
    try:
        with open(path) as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    if not d.get("found") and time.time() - d.get("time", 0) > MISS_TTL:
        return None
    return d


def _cache_write(path, synced, plain):
    os.makedirs(CACHE_DIR, exist_ok=True)
    data = {"found": bool(synced or plain), "time": time.time(), "synced": synced, "plain": plain}
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


# ---- LRCLIB ----

def _get(endpoint, **params):
    params = {k: v for k, v in params.items() if v}
    url = f"{API}/{endpoint}?{urllib.parse.urlencode(params)}"
    debug(f"GET {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def _text(rec):
    if rec.get("instrumental"):
        return "", "♪ Instrumental ♪"
    return rec.get("syncedLyrics") or "", rec.get("plainLyrics") or ""


def pick_best(results, duration):
    """Prefer synced lyrics with a close duration."""
    def score(r):
        has = bool(r.get("syncedLyrics")) * 2 + bool(r.get("plainLyrics") or r.get("instrumental"))
        off = abs((r.get("duration") or 0) - duration) if duration else 0
        return (off <= 5, has, -off) if duration else (True, has, 0)
    good = [r for r in results or [] if r.get("syncedLyrics") or r.get("plainLyrics") or r.get("instrumental")]
    if duration:
        good = [r for r in good if abs((r.get("duration") or 0) - duration) <= 15]
    return max(good, key=score) if good else None


def _lookup(artist, title, album, duration):
    """Returns (source, synced_lrc, plain) or None."""
    artists = [artist]
    first = re.split(r",| & | x | and ", artist)[0].strip()
    if first and first != artist:
        artists.append(first)

    for a in artists:
        rec = _get("get", artist_name=a, track_name=title, album_name=album,
                   duration=round(duration) if duration else None)
        if rec and (rec.get("syncedLyrics") or rec.get("plainLyrics") or rec.get("instrumental")):
            return ("lrclib-get", *_text(rec))
    for a in artists:
        rec = pick_best(_get("search", artist_name=a, track_name=title), duration)
        if rec:
            return ("lrclib-search", *_text(rec))
    rec = pick_best(_get("search", q=f"{artist} {title}"), duration)
    if rec:
        return ("lrclib-search", *_text(rec))
    return None


def fetch(artist, title, album="", duration=0):
    """Return a Lyrics object. Never raises."""
    path = _cache_path(artist, title)
    cached = _cache_read(path)
    if cached is not None:
        return Lyrics("cache" if cached["found"] else "none", cached["synced"], cached["plain"])
    try:
        found = _lookup(artist, title, album, duration)
    except (OSError, ValueError) as e:  # network/JSON errors: don't cache
        debug(f"lyrics fetch failed: {e}")
        return Lyrics("error")
    source, synced, plain = found or ("none", "", "")
    try:
        _cache_write(path, synced, plain)
    except OSError as e:
        debug(f"cache write failed: {e}")
    return Lyrics(source, synced, plain)
