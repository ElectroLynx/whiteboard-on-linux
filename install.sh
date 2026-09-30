#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
install_dir="${XDG_DATA_HOME:-$HOME/.local/share}/whiteboard"
applications_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
desktop_file="$applications_dir/org.victor.Whiteboard.desktop"

mkdir -p "$install_dir" "$applications_dir"
cp "$project_dir/main.py" "$project_dir/run.sh" "$install_dir/"
rm -rf "$install_dir/whiteboard" "$install_dir/data"
cp -R "$project_dir/whiteboard" "$install_dir/whiteboard"
cp -R "$project_dir/data" "$install_dir/data"

sed "s|__WHITEBOARD_EXEC__|$install_dir/run.sh|" \
    "$project_dir/data/org.victor.Whiteboard.desktop" > "$desktop_file"

chmod +x "$install_dir/run.sh"
printf 'Whiteboard installé dans %s\n' "$install_dir"
printf 'Lancez-le depuis le menu GNOME ou avec %s\n' "$install_dir/run.sh"