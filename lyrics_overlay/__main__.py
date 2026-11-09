import argparse
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from . import log  # noqa: E402
from .app import App  # noqa: E402


def main():
    parser = argparse.ArgumentParser(prog="lyrics-overlay")
    parser.add_argument("--debug", action="store_true",
                        help="print player, metadata, lyrics source and sync position")
    args = parser.parse_args()
    log.enabled = args.debug
    # GTK gets no extra args; we parse our own above.
    return App().run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
