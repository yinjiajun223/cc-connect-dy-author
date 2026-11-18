"""UTF-8 stdout/stderr for the CLI entry points.

On Windows the console and pipe encoding follow the machine's regional code
page (cp936 on a Chinese host), so the Chinese JSON these scripts emit with
ensure_ascii=False reaches the caller as mojibake. Host agents parse that
stdout, so its encoding must not depend on regional settings.
"""
from __future__ import annotations

import sys


def force_utf8():
    """Re-point stdout and stderr at UTF-8; streams that cannot be reconfigured are left alone."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
