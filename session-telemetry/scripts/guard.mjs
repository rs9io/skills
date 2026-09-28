#!/usr/bin/env node
/**
 * The telemetry-builder's fence, run before every tool call it makes. It may
 * read ~/.session-telemetry, read and write its own memory, and run only the
 * dashboard updater, `open` (or `xdg-open`) on a dashboard page, and `date`. Anything else is
 * refused with the reason (exit code 2 tells Claude Code to block the call).
 */

import { readFileSync } from "node:fs"
import { homedir } from "node:os"
import { join, resolve } from "node:path"

const HOME = homedir()
const PROJECT = `${resolve(process.env.TELEMETRY_HOME || join(HOME, ".session-telemetry"))}/`
const PORT = Number(process.env.TELEMETRY_PORT || 4200)
const MEMORY = /\/\.claude[^/]*\/agent-memory\/telemetry-builder(\/|$)/

const input = JSON.parse(readFileSync(0, "utf8"))
const tool = input.tool_name
const args = input.tool_input ?? {}

function refuse(reason) {
	process.stderr.write(`telemetry-builder fence: ${reason}`)
	process.exit(2)
}

const expand = (p) => resolve(String(p ?? "").replace(/^~(?=\/|$)/, HOME))

if (["Read", "Glob", "Grep"].includes(tool)) {
	const target = expand(args.file_path ?? args.path ?? PROJECT)
	if (!(target.startsWith(PROJECT) || target === PROJECT.slice(0, -1) || MEMORY.test(target))) refuse(`reading is limited to ${PROJECT} and your memory folder, not ${target}`)
	process.exit(0)
}

if (["Write", "Edit", "MultiEdit"].includes(tool)) {
	const target = expand(args.file_path)
	if (!MEMORY.test(target)) refuse(`you may only write your own memory; change dashboard data with node ~/.session-telemetry/dash.mjs, not ${target}`)
	process.exit(0)
}

if (tool === "Bash") {
	const command = String(args.command ?? "").trim()
	if (/[;&|`<>\n]|\$\(/.test(command)) refuse("one command at a time, with no chaining, pipes, redirects or substitutions (leave characters like & out of notes)")
	const dash = command.match(/^node (\S+)( |$)/)?.[1]
	const isUpdater = dash !== undefined && resolve(dash.replace(/^~(?=\/)/, HOME)) === join(PROJECT, "dash.mjs")
	const isOpen = new RegExp(`^(open|xdg-open) "?http://localhost:${PORT}/[^\\s"]*"?$`).test(command)
	const isDate = /^date( \+[%A-Za-z-]+)?$/.test(command)
	if (!(isUpdater || isOpen || isDate)) refuse(`only the dashboard updater, opening a localhost:${PORT} page, and date are allowed, not: ${command}`)
	process.exit(0)
}

refuse(`${tool} is not available to the dashboard builder`)
