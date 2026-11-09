"""Turn raw player metadata into a clean (artist, title) for lyrics lookup."""

import re

# Bracketed parts containing any of these words are noise: "(Official Video)", "[4K]".
NOISE = (r"official|video|audio|lyrics?|visuali[sz]er|music\s*video|m/?v|hd|hq|4k|"
         r"1080p|720p|explicit|clean|remaster(ed)?|color\s*coded|clip\s*officiel|"
         r"full\s*song|high\s*quality")
BRACKETS = re.compile(r"\s*[(\[【][^)\]】]*\b(" + NOISE + r")\b[^)\]】]*[)\]】]", re.I)
FEAT = re.compile(r"\s*[(\[]?\s*\b(feat\.?|ft\.?|featuring)\s[^)\]]*[)\]]?", re.I)
REMASTER = re.compile(r"\s+-\s+.*\bremaster(ed)?\b.*$", re.I)
DASH = re.compile(r"\s+[-–—]\s+")
# Right side of "X - Y" that is a version tag, not a song title.
VERSION = re.compile(r"^(live|acoustic|radio edit|demo|mono|stereo|single version|"
                     r"remix|.*\bremaster(ed)?\b.*)$", re.I)


def _tidy(s):
    s = re.sub(r"\s+", " ", s).strip(" -–—|·")
    return s.strip("\"'“”‘’ ").strip()


def clean_artist(artist):
    a = re.sub(r"\s*-\s*Topic$", "", artist, flags=re.I)
    if re.search(r"VEVO$", a, re.I):
        a = a[:-4]
        if " " not in a:  # "RickAstley" -> "Rick Astley"
            a = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", a)
    a = re.sub(r"\s*(official|music)$", "", a, flags=re.I)
    return _tidy(a)


def clean_title(title):
    t = title.split(" | ")[0]          # "Song | Album Teaser"
    t = BRACKETS.sub("", t)
    t = FEAT.sub("", t)
    t = REMASTER.sub("", t)
    return _tidy(t)


def is_clean_source(player, album, url):
    """Spotify and YouTube Music give proper metadata."""
    return "spotify" in player.lower() or "music.youtube.com" in url or bool(album)


def clean(player, artist, title, album="", url=""):
    """Return (artist, title)."""
    if is_clean_source(player, album, url):
        return artist.strip(), title.strip()

    artist, title = clean_artist(artist), title
    parts = DASH.split(title, maxsplit=1)
    if len(parts) == 2 and not VERSION.match(clean_title(parts[1]) or parts[1]):
        artist, title = clean_artist(parts[0]), parts[1]
    return _tidy(FEAT.sub("", artist)) or artist, clean_title(title)
