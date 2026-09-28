#!/usr/bin/env node
/**
 * Session dashboard updater: the only way anything writes dashboard data.
 * One structured file per agent session in ~/.session-telemetry/data/, served
 * live at http://localhost:4200/s/<session> by server.mjs. Every time is stamped
 * here from the machine's real clock, never typed by an agent.
 *
 * Settings: TELEMETRY_HOME (default ~/.session-telemetry), TELEMETRY_PORT (default 4200).
 *
 *   node dash.mjs init <session> --title "…" --goal "…"            → prints the page address
 *   node dash.mjs task add "…" --group "<the request>" [--note "…"]  → prints the task id
 *   node dash.mjs task <id> todo|doing|done|blocked [--note "…"]
 *   node dash.mjs ask "question" --default "what happens until the user answers"   → prints the question id
 *   node dash.mjs answer <id> "the user's answer"
 *   node dash.mjs deliver "title" --link <path-or-url> [--note "…"]
 *   node dash.mjs stuck "what" --why "…"                            → prints the stuck id
 *   node dash.mjs unstuck <id> [--note "how it cleared"]
 *   node dash.mjs summary --for "…" --now "…" --next "…" [--waiting "…"]  (the "where are we up to" box)
 *   node dash.mjs followup "what to check" --in 6h [--how "…"]     → prints the check-back id (m, h or d)
 *   node dash.mjs followup <id> done [--note "what it showed"]
 *   node dash.mjs due                                               (lists check-backs that are due, all sessions)
 *   node dash.mjs health                                            (checks the server; restarts it if down)
 *   node dash.mjs log "…"
 *   node dash.mjs finish [--note "…"]
 *
 * North Star: the user opens a session's page after hours away and knows where
 * it is up to within seconds. Keep the summary current after every meaningful step.
 *
 * <session> is a short kebab-case name such as 2026-09-28-curate-queue. Every
 * command except init, due and health takes it from --session or $DASH_SESSION.
 */

import { execFileSync } from "node:child_process"
import { existsSync, mkdirSync, readdirSync, readFileSync, renameSync, writeFileSync } from "node:fs"
import { spawn } from "node:child_process"
import { homedir, platform } from "node:os"
import { join } from "node:path"

const HOME_DIR = process.env.TELEMETRY_HOME || join(homedir(), ".session-telemetry")
const DATA = join(HOME_DIR, "data")
const PORT = Number(process.env.TELEMETRY_PORT || 4200)
const SESSION_ID = /^[a-z0-9][a-z0-9-]{0,80}$/
const STATUSES = ["todo", "doing", "done", "blocked"]

function fail(message) {
	console.error(`dash: ${message}`)
	process.exit(1)
}

function parse(argv) {
	const positional = []
	const flags = {}
	for (let i = 0; i < argv.length; i++) {
		const arg = argv[i]
		if (arg.startsWith("--")) {
			const key = arg.slice(2)
			const next = argv[i + 1]
			if (next === undefined || next.startsWith("--")) flags[key] = true
			else {
				flags[key] = next
				i++
			}
		} else positional.push(arg)
	}
	return { positional, flags }
}

const now = () => new Date().toISOString()

function fileFor(session) {
	if (!SESSION_ID.test(session)) fail(`session must be short kebab-case, got "${session}"`)
	return join(DATA, `${session}.json`)
}

function load(session) {
	const file = fileFor(session)
	if (!existsSync(file)) fail(`no dashboard for session ${session} (run init first)`)
	return JSON.parse(readFileSync(file, "utf8"))
}

function save(session, state, event) {
	state.updatedAt = now()
	if (event) state.log.unshift({ at: state.updatedAt, text: event })
	state.log = state.log.slice(0, 80)
	mkdirSync(DATA, { recursive: true })
	const file = fileFor(session)
	const tmp = `${file}.tmp`
	writeFileSync(tmp, JSON.stringify(state, null, 2))
	renameSync(tmp, file)
}

function nextId(list, prefix) {
	return `${prefix}${list.length + 1}`
}

function find(list, id, kind) {
	const item = list.find((entry) => entry.id === id)
	if (!item) fail(`no ${kind} with id ${id}`)
	return item
}

const { positional, flags } = parse(process.argv.slice(2))
const [command, ...rest] = positional

if (command === "init") {
	const session = rest[0] ?? fail("init needs a session name")
	if (!flags.title) fail("init needs --title")
	if (existsSync(fileFor(session))) fail(`session ${session} already has a dashboard; add to it instead`)
	const at = now()
	const state = {
		id: session,
		title: flags.title,
		goal: typeof flags.goal === "string" ? flags.goal : "",
		startedAt: at,
		updatedAt: at,
		finishedAt: null,
		tasks: [],
		questions: [],
		deliverables: [],
		stuck: [],
		summary: null,
		followups: [],
		log: [],
	}
	save(session, state, "Dashboard started")
	console.log(`http://localhost:${PORT}/s/${session}`)
	process.exit(0)
}

/** Restart the server through whatever keeps it running: launchd on macOS, systemd on Linux, else start it directly. */
function restartServer() {
	try {
		if (platform() === "darwin") return execFileSync("launchctl", ["kickstart", "-k", `gui/${process.getuid()}/dev.session-telemetry`], { stdio: "ignore" })
		if (platform() === "linux") return execFileSync("systemctl", ["--user", "restart", "session-telemetry"], { stdio: "ignore" })
	} catch {
		// No service installed; fall through and start it directly.
	}
	spawn(process.execPath, [join(HOME_DIR, "server.mjs")], { detached: true, stdio: "ignore" }).unref()
}

if (command === "health") {
	const url = `http://localhost:${PORT}/api/sessions`
	const up = async () => {
		try {
			return (await fetch(url, { signal: AbortSignal.timeout(2000) })).ok
		} catch {
			return false
		}
	}
	if (await up()) {
		console.log(`Dashboard server is up at http://localhost:${PORT}`)
		process.exit(0)
	}
	restartServer()
	for (let i = 0; i < 10; i++) {
		await new Promise((r) => setTimeout(r, 500))
		if (await up()) {
			console.log("Dashboard server was down; restarted it")
			process.exit(0)
		}
	}
	fail(`dashboard server is down and did not restart; see ${join(HOME_DIR, "logs", "server.log")}`)
}

if (command === "due") {
	const at = Date.now()
	const due = existsSync(DATA)
		? readdirSync(DATA)
				.filter((n) => n.endsWith(".json"))
				.flatMap((n) => {
					const s = JSON.parse(readFileSync(join(DATA, n), "utf8"))
					return (s.followups ?? []).filter((f) => !f.doneAt && new Date(f.dueAt).getTime() <= at).map((f) => `${s.id} ${f.id}: ${f.what}${f.how ? ` (how: ${f.how})` : ""}, due ${f.dueAt}`)
				})
		: []
	console.log(due.length ? due.join("\n") : "No check-backs due.")
	process.exit(0)
}

const session = typeof flags.session === "string" ? flags.session : process.env.DASH_SESSION || fail("set --session or DASH_SESSION")
const state = load(session)
const note = typeof flags.note === "string" ? flags.note : undefined

switch (command) {
	case "task": {
		if (rest[0] === "add") {
			const title = rest[1] ?? fail("task add needs a title")
			const id = nextId(state.tasks, "t")
			const group = typeof flags.group === "string" ? flags.group : ""
			state.tasks.push({ id, title, group, status: "todo", note: note ?? "", addedAt: now(), startedAt: null, finishedAt: null })
			save(session, state, `Task added: ${title}`)
			console.log(id)
			break
		}
		const [id, status] = rest
		if (!STATUSES.includes(status)) fail(`status must be one of ${STATUSES.join(", ")}`)
		const task = find(state.tasks, id, "task")
		task.status = status
		if (note !== undefined) task.note = note
		if (status === "doing" && !task.startedAt) task.startedAt = now()
		if (status === "done") task.finishedAt = now()
		if (status !== "done") task.finishedAt = null
		const verb = { todo: "Back to do", doing: "Started", done: "Done", blocked: "Blocked" }[status]
		save(session, state, `${verb}: ${task.title}`)
		break
	}
	case "ask": {
		const question = rest[0] ?? fail("ask needs a question")
		if (typeof flags.default !== "string") fail("ask needs --default: what happens if the user does not answer")
		const id = nextId(state.questions, "q")
		state.questions.push({ id, question, default: flags.default, askedAt: now(), answer: null, answeredAt: null })
		save(session, state, `Question for you: ${question}`)
		console.log(id)
		break
	}
	case "answer": {
		const q = find(state.questions, rest[0], "question")
		q.answer = rest[1] ?? fail("answer needs the answer text")
		q.answeredAt = now()
		save(session, state, `Answered: ${q.question}`)
		break
	}
	case "deliver": {
		const title = rest[0] ?? fail("deliver needs a title")
		state.deliverables.unshift({ title, link: typeof flags.link === "string" ? flags.link : "", note: note ?? "", at: now() })
		save(session, state, `Delivered: ${title}`)
		break
	}
	case "stuck": {
		const what = rest[0] ?? fail("stuck needs a description")
		const id = nextId(state.stuck, "s")
		state.stuck.push({ id, what, why: typeof flags.why === "string" ? flags.why : "", since: now(), clearedAt: null, note: "" })
		save(session, state, `Stuck: ${what}`)
		console.log(id)
		break
	}
	case "unstuck": {
		const s = find(state.stuck, rest[0], "stuck item")
		s.clearedAt = now()
		if (note !== undefined) s.note = note
		save(session, state, `Unstuck: ${s.what}`)
		break
	}
	case "summary": {
		const field = (key) => (typeof flags[key] === "string" ? flags[key] : "")
		if (!(field("for") && field("now") && field("next"))) fail("summary needs --for, --now and --next (and --waiting when something waits on the user)")
		state.summary = { for: field("for"), now: field("now"), next: field("next"), waiting: field("waiting"), at: now() }
		save(session, state, "Updated where we're up to")
		break
	}
	case "followup": {
		state.followups ??= []
		if (rest[1] === "done") {
			const f = find(state.followups, rest[0], "check-back")
			f.doneAt = now()
			if (note !== undefined) f.result = note
			save(session, state, `Checked back: ${f.what}`)
			break
		}
		const what = rest[0] ?? fail("followup needs what to check")
		const m = /^(\d+)([mhd])$/.exec(typeof flags.in === "string" ? flags.in : "")
		if (!m) fail("followup needs --in like 30m, 6h or 2d")
		const ms = Number(m[1]) * { m: 60_000, h: 3_600_000, d: 86_400_000 }[m[2]]
		const id = nextId(state.followups, "f")
		state.followups.push({ id, what, how: typeof flags.how === "string" ? flags.how : "", setAt: now(), dueAt: new Date(Date.now() + ms).toISOString(), doneAt: null, result: "" })
		save(session, state, `Check back in ${flags.in}: ${what}`)
		console.log(id)
		break
	}
	case "log":
		save(session, state, rest[0] ?? fail("log needs text"))
		break
	case "finish":
		state.finishedAt = now()
		save(session, state, note ? `Finished: ${note}` : "Finished")
		break
	default:
		fail(`unknown command ${command ?? "(none)"}`)
}
