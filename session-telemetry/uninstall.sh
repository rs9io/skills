#!/usr/bin/env bash
# Stops the server and removes the service and agent. Keeps your session data
# in ~/.session-telemetry/data unless you pass --purge.
set -euo pipefail
HOME_DIR="${TELEMETRY_HOME:-$HOME/.session-telemetry}"
if [ "$(uname)" = "Darwin" ]; then
	launchctl bootout "gui/$(id -u)/dev.session-telemetry" 2>/dev/null || true
	rm -f "$HOME/Library/LaunchAgents/dev.session-telemetry.plist"
elif command -v systemctl >/dev/null; then
	systemctl --user disable --now session-telemetry 2>/dev/null || true
	rm -f "$HOME/.config/systemd/user/session-telemetry.service"
fi
pkill -f "$HOME_DIR/server.mjs" 2>/dev/null || true
rm -f "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/agents/telemetry-builder.md"
if [ "${1:-}" = "--purge" ]; then rm -rf "$HOME_DIR"; echo "Removed everything, including session data"; else rm -rf "$HOME_DIR/app" "$HOME_DIR"/*.mjs; echo "Removed; session data kept in $HOME_DIR/data"; fi
