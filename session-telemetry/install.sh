#!/usr/bin/env bash
# Installs the session dashboard: builds the app, copies the runtime to
# ~/.session-telemetry, installs the telemetry-builder agent for Claude Code,
# and starts the server on login (launchd on macOS, systemd on Linux).
#
#   ./install.sh [--no-service] [--no-agent]
#   TELEMETRY_HOME=~/somewhere TELEMETRY_PORT=4300 ./install.sh
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_DIR="${TELEMETRY_HOME:-$HOME/.session-telemetry}"
PORT="${TELEMETRY_PORT:-4200}"
SERVICE=1
AGENT=1
for arg in "$@"; do
	case "$arg" in
		--no-service) SERVICE=0 ;;
		--no-agent) AGENT=0 ;;
		*) echo "Unknown option: $arg" >&2; exit 1 ;;
	esac
done

command -v node >/dev/null || { echo "Needs Node.js 20 or newer: https://nodejs.org" >&2; exit 1; }
NODE="$(command -v node)"
[ "$("$NODE" -p 'process.versions.node.split(".")[0]')" -ge 20 ] || { echo "Needs Node.js 20 or newer" >&2; exit 1; }

echo "Building the dashboard app…"
BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT
cp -R "$SKILL_DIR/app/." "$BUILD/"
rm -rf "$BUILD/node_modules" "$BUILD/dist"
(cd "$BUILD" && npm ci --no-audit --no-fund --loglevel=error && npm run build --silent)

mkdir -p "$HOME_DIR/data" "$HOME_DIR/logs"
cp "$SKILL_DIR"/scripts/{server,dash,guard}.mjs "$HOME_DIR/"
rm -rf "$HOME_DIR/app"
cp -R "$BUILD/dist" "$HOME_DIR/app"
echo "Installed to $HOME_DIR"

if [ "$AGENT" = 1 ]; then
	AGENTS_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/agents"
	mkdir -p "$AGENTS_DIR"
	sed -e "s#__HOME__#$HOME_DIR#g" -e "s#__PORT__#$PORT#g" "$SKILL_DIR/agents/telemetry-builder.md" > "$AGENTS_DIR/telemetry-builder.md"
	echo "Installed the telemetry-builder agent to $AGENTS_DIR"
fi

if [ "$SERVICE" = 1 ] && [ "$(uname)" = "Darwin" ]; then
	PLIST="$HOME/Library/LaunchAgents/dev.session-telemetry.plist"
	mkdir -p "$(dirname "$PLIST")"
	cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key><string>dev.session-telemetry</string>
	<key>ProgramArguments</key><array><string>$NODE</string><string>$HOME_DIR/server.mjs</string></array>
	<key>EnvironmentVariables</key><dict><key>TELEMETRY_HOME</key><string>$HOME_DIR</string><key>TELEMETRY_PORT</key><string>$PORT</string></dict>
	<key>RunAtLoad</key><true/>
	<key>KeepAlive</key><true/>
	<key>StandardOutPath</key><string>$HOME_DIR/logs/server.log</string>
	<key>StandardErrorPath</key><string>$HOME_DIR/logs/server.log</string>
</dict>
</plist>
PLIST
	launchctl bootout "gui/$(id -u)/dev.session-telemetry" 2>/dev/null || true
	launchctl bootstrap "gui/$(id -u)" "$PLIST"
	echo "Starts on login and restarts itself (launchd: dev.session-telemetry)"
elif [ "$SERVICE" = 1 ] && command -v systemctl >/dev/null && systemctl --user show-environment >/dev/null 2>&1; then
	UNIT="$HOME/.config/systemd/user/session-telemetry.service"
	mkdir -p "$(dirname "$UNIT")"
	cat > "$UNIT" <<UNIT
[Unit]
Description=Session telemetry

[Service]
ExecStart=$NODE $HOME_DIR/server.mjs
Environment=TELEMETRY_HOME=$HOME_DIR
Environment=TELEMETRY_PORT=$PORT
Restart=always
StandardOutput=append:$HOME_DIR/logs/server.log
StandardError=append:$HOME_DIR/logs/server.log

[Install]
WantedBy=default.target
UNIT
	systemctl --user daemon-reload
	systemctl --user enable --now session-telemetry
	systemctl --user restart session-telemetry
	echo "Starts on login and restarts itself (systemd --user: session-telemetry)"
else
	TELEMETRY_HOME="$HOME_DIR" TELEMETRY_PORT="$PORT" nohup "$NODE" "$HOME_DIR/server.mjs" >> "$HOME_DIR/logs/server.log" 2>&1 &
	echo "Started the server for this login only (no service installed)"
fi

for _ in $(seq 1 20); do
	if curl -fsS "http://localhost:$PORT/api/sessions" >/dev/null 2>&1; then
		echo "Ready: http://localhost:$PORT"
		exit 0
	fi
	sleep 0.5
done
echo "The server did not answer on port $PORT; see $HOME_DIR/logs/server.log" >&2
exit 1
