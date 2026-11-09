#!/usr/bin/env bash
# Installs lyrics-overlay for the current user (no root needed).
set -euo pipefail
SRC="$(dirname "$(readlink -f "$0")")"
DEST="$HOME/.local/share/lyrics-overlay"
BIN="$HOME/.local/bin"

rm -rf "$DEST"
mkdir -p "$DEST" "$BIN"
cp -r "$SRC/lyrics_overlay" "$SRC/lyrics-overlay" "$DEST/"
chmod +x "$DEST/lyrics-overlay"
ln -sf "$DEST/lyrics-overlay" "$BIN/lyrics-overlay"

echo "Installed: $BIN/lyrics-overlay"
case ":$PATH:" in *":$BIN:"*) ;; *) echo "Note: add $BIN to your PATH." ;; esac
