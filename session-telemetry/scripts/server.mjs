#!/usr/bin/env node
/**
 * The always-on dashboard server. Serves the React app at http://localhost:4200
 * (every session at /s/<session>), reads each session's data from
 * ~/.session-telemetry/data, and pushes a change to open pages the moment a data
 * file is written. Listens on this machine only. No dependencies; install.sh has
 * launchd (macOS) or systemd (Linux) start it on login and restart it.
 */

import { existsSync, readdirSync, readFileSync, statSync, watch } from "node:fs"
import { createServer } from "node:http"
import { homedir } from "node:os"
import { extname, join, normalize } from "node:path"

const ROOT = process.env.TELEMETRY_HOME || join(homedir(), ".session-telemetry")
const DATA = join(ROOT, "data")
const DIST = join(ROOT, "app")
const PORT = Number(process.env.TELEMETRY_PORT || 4200)
const SESSION_ID = /^[a-z0-9][a-z0-9-]{0,80}$/

const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".woff2": "font/woff2", ".png": "image/png", ".ico": "image/x-icon", ".json": "application/json" }

function readSession(id) {
	if (!SESSION_ID.test(id)) return null
	const file = join(DATA, `${id}.json`)
	if (!existsSync(file)) return null
	try {
		return JSON.parse(readFileSync(file, "utf8"))
	} catch {
		return null // mid-write or damaged; the next change event brings a good copy
	}
}

function summaries() {
	if (!existsSync(DATA)) return []
	return readdirSync(DATA)
		.filter((name) => name.endsWith(".json"))
		.map((name) => readSession(name.slice(0, -5)))
		.filter(Boolean)
		.map((s) => {
			const count = (status) => s.tasks.filter((t) => t.status === status).length
			return {
				id: s.id,
				title: s.title,
				goal: s.goal,
				startedAt: s.startedAt,
				updatedAt: s.updatedAt,
				finishedAt: s.finishedAt,
				total: s.tasks.length,
				done: count("done"),
				doing: count("doing"),
				blocked: count("blocked"),
				openQuestions: s.questions.filter((q) => !q.answer).length,
				stuck: s.stuck.filter((x) => !x.clearedAt).length,
				current: s.tasks.find((t) => t.status === "doing")?.title ?? null,
				whereNow: s.summary?.now ?? null,
				checkBacksDue: (s.followups ?? []).filter((f) => !f.doneAt && new Date(f.dueAt).getTime() <= Date.now()).length,
			}
		})
		.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
}

function json(res, status, body) {
	res.writeHead(status, { "content-type": "application/json", "cache-control": "no-store" })
	res.end(JSON.stringify(body))
}

// Live push: every open page holds one event stream; a data file change is sent to all of them.
const streams = new Set()
let pending = new Set()
let timer = null
// ./data appears with the first `dash.mjs init`; until then, look again every 5 seconds.
function watchData() {
	if (!existsSync(DATA)) return setTimeout(watchData, 5000)
	watch(DATA, (_event, name) => {
		if (!name?.endsWith(".json")) return
		pending.add(name.slice(0, -5))
		clearTimeout(timer)
		timer = setTimeout(() => {
			for (const id of pending) for (const res of streams) res.write(`event: change\ndata: ${JSON.stringify({ id })}\n\n`)
			pending = new Set()
		}, 150)
	})
}
watchData()
setInterval(() => {
	for (const res of streams) res.write(": keep-alive\n\n")
}, 25_000)

function serveFile(res, path) {
	res.writeHead(200, { "content-type": TYPES[extname(path)] ?? "application/octet-stream", "cache-control": path.endsWith("index.html") ? "no-store" : "public, max-age=31536000, immutable" })
	res.end(readFileSync(path))
}

const server = createServer((req, res) => {
	const url = new URL(req.url ?? "/", `http://localhost:${PORT}`)
	const path = url.pathname

	if (path === "/api/sessions") return json(res, 200, summaries())
	if (path.startsWith("/api/sessions/")) {
		const session = readSession(decodeURIComponent(path.slice("/api/sessions/".length)))
		return session ? json(res, 200, session) : json(res, 404, { error: "No such session" })
	}
	if (path === "/api/events") {
		res.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-store", connection: "keep-alive" })
		res.write("retry: 3000\n\n")
		streams.add(res)
		req.on("close", () => streams.delete(res))
		return
	}

	// Built app files, and the app itself for every page address (/, /s/<session>).
	const file = normalize(join(DIST, path))
	if (file.startsWith(DIST) && existsSync(file) && statSync(file).isFile()) return serveFile(res, file)
	const index = join(DIST, "index.html")
	if (existsSync(index)) return serveFile(res, index)
	res.writeHead(503, { "content-type": "text/plain" })
	res.end("The dashboard app is missing: run install.sh from the session-telemetry skill.")
})

server.listen(PORT, "127.0.0.1", () => console.log(`Dashboard at http://localhost:${PORT}`))
