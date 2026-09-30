#!/usr/bin/env python3
"""Entry point for the Whiteboard application."""
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from whiteboard.application import WhiteboardApplication


def main() -> int:
    app = WhiteboardApplication()
    try:
        return app.run(sys.argv)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
