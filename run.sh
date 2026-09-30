#!/usr/bin/env bash
# Launch the Whiteboard app.
exec python3 "$(dirname "$(readlink -f "$0")")/main.py" "$@"
