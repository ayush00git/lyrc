# lyrics-overlay

A fullscreen black screen showing synced lyrics for whatever is playing.
Works with Spotify, YouTube and YouTube Music in Chrome (any MPRIS2 player, really),
on Wayland and X11. Lyrics come from [LRCLIB](https://lrclib.net), with no API key.

- Run `lyrics-overlay` to open it. Run it again (or press **Esc** / **q**) to close it.
- Lyrics show **one word at a time** in big text. Press **l** to switch to line view
  (current line white, others dimmed, scrolling with the song).
  Most lyrics only have per-line timing, so word timing is estimated within each line.
- Plain (untimed) lyrics scroll with **↑/↓**, **j/k**, **PgUp/PgDn**, **Space** or the mouse wheel.
- Lyrics are cached in `~/.cache/lyrics-overlay/`.
- There's no background process; it exits fully when closed.

## Install

Requires Python 3, GTK 4 and PyGObject.

| Distro | Command |
|---|---|
| Fedora | `sudo dnf install python3-gobject gtk4` |
| Ubuntu / Debian | `sudo apt install python3-gi gir1.2-gtk-4.0` |
| Arch | `sudo pacman -S python-gobject gtk4` |

Then, from this folder:

```sh
./install.sh
```

This copies the app to `~/.local/share/lyrics-overlay` and links the command into
`~/.local/bin` (no root needed). Make sure `~/.local/bin` is in your `PATH`.
To uninstall, run `rm -rf ~/.local/share/lyrics-overlay ~/.local/bin/lyrics-overlay`.

## Keyboard shortcut

Use the full path, since shortcuts don't always see your shell's `PATH`:
`/home/YOU/.local/bin/lyrics-overlay`

**GNOME:** Settings → Keyboard → View and Customize Shortcuts → Custom Shortcuts → **+**.
Name: `Lyrics`, Command: the path above. Then set a shortcut, e.g. Super+Y.

**KDE Plasma:** System Settings → Keyboard → Shortcuts → **Add New** → **Command or Script**.
Enter the path above, then assign a key.

## Troubleshooting

Run it from a terminal with debug output:

```sh
lyrics-overlay --debug
```

This prints the player in use, raw and cleaned artist/title, the lyrics source
(`cache`, `lrclib-get`, `lrclib-search`, `none`) and the sync position every 2 seconds.

- **"Waiting for a player…"**: check that your player shows up in
  `busctl --user list | grep mpris`.
- **Wrong song matched / lyrics out of sync**: delete the file for that song in
  `~/.cache/lyrics-overlay/` and reopen.
- **Chrome not detected**: make sure media keys / the media hub work in Chrome.
  That's the same MPRIS interface.

## Tests

```sh
python3 -m unittest discover tests
```
