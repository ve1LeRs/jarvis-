"""Entry point for PyInstaller / double-click JARVIS.exe."""

from __future__ import annotations

import sys


def _bootstrap_frozen_defaults() -> None:
    """Double-click with no args → background app (tray + voice)."""
    if not getattr(sys, "frozen", False):
        return
    # Only argv[0] present → treat as normal program launch
    if len(sys.argv) == 1:
        sys.argv.append("--background")


def main() -> int:
    _bootstrap_frozen_defaults()
    from jarvis.__main__ import main as jarvis_main

    return jarvis_main()


if __name__ == "__main__":
    raise SystemExit(main())
