import sys
import time

enabled = False


def debug(*parts):
    """Print to stderr only when --debug is on."""
    if enabled:
        print(time.strftime("[%H:%M:%S]"), *parts, file=sys.stderr, flush=True)
