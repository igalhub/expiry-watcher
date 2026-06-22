#!/usr/bin/env bash
# Installs the expiry-watcher systemd user units and starts the timer.
# Run from any directory — paths are resolved relative to this script.
set -euo pipefail

UNIT_DIR="$HOME/.config/systemd/user"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$UNIT_DIR"

cp "$REPO_DIR/systemd/expiry-watcher.service" "$UNIT_DIR/"
cp "$REPO_DIR/systemd/expiry-watcher.timer"   "$UNIT_DIR/"

systemctl --user daemon-reload
systemctl --user enable --now expiry-watcher.timer

echo ""
echo "Installed. Timer status:"
systemctl --user status expiry-watcher.timer
