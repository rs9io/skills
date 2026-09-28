/**
 * The dashboard's data, served by server.mjs from ~/.session-telemetry/data.
 * The server pushes a change the moment a session's file is written; the page
 * also re-reads every 10 seconds in case a push is missed.
 */

import { useEffect, useState } from "react"

export type TaskStatus = "todo" | "doing" | "done" | "blocked"

export type Task = {
	id: string
	title: string
	group: string
	status: TaskStatus
	note: string
	addedAt: string
	startedAt: string | null
	finishedAt: string | null
}

export type Question = { id: string; question: string; default: string; askedAt: string; answer: string | null; answeredAt: string | null }
export type Deliverable = { title: string; link: string; note: string; at: string }
export type Stuck = { id: string; what: string; why: string; since: string; clearedAt: string | null; note: string }
export type LogEntry = { at: string; text: string }
/** "Where are we up to": the North Star of the page. Four plain answers for someone with no context. */
export type Summary = { for: string; now: string; next: string; waiting: string; at: string }
export type FollowUp = { id: string; what: string; how: string; setAt: string; dueAt: string; doneAt: string | null; result: string }

export type Dashboard = {
	title: string
	goal: string
	startedAt: string
	updatedAt: string
	finishedAt: string | null
	tasks: Task[]
	questions: Question[]
	deliverables: Deliverable[]
	stuck: Stuck[]
	summary?: Summary | null
	followups?: FollowUp[]
	log: LogEntry[]
}

export type SessionSummary = {
	id: string
	title: string
	goal: string
	startedAt: string
	updatedAt: string
	finishedAt: string | null
	total: number
	done: number
	doing: number
	blocked: number
	openQuestions: number
	stuck: number
	current: string | null
	whereNow: string | null
	checkBacksDue: number
}

export const REFRESH_MS = 10_000

/** Re-fetches `url` on every pushed change and every 10 seconds; returns the latest body and when the next backup read is due. */
function useLive<T>(url: string, matches: (changedId: string) => boolean): { data: T | null; missing: boolean; nextPoll: number } {
	const [data, setData] = useState<T | null>(null)
	const [missing, setMissing] = useState(false)
	const [nextPoll, setNextPoll] = useState(() => Date.now() + REFRESH_MS)

	useEffect(() => {
		let stopped = false
		async function load() {
			setNextPoll(Date.now() + REFRESH_MS)
			try {
				const res = await fetch(url, { cache: "no-store" })
				if (stopped) return
				if (res.status === 404) return setMissing(true)
				if (res.ok) {
					setMissing(false)
					setData(await res.json())
				}
			} catch {
				// Server restarting; the next push or backup read catches up.
			}
		}
		load()
		const timer = setInterval(load, REFRESH_MS)
		const events = new EventSource("/api/events")
		events.addEventListener("change", (event) => {
			const { id } = JSON.parse((event as MessageEvent).data) as { id: string }
			if (matches(id)) load()
		})
		return () => {
			stopped = true
			clearInterval(timer)
			events.close()
		}
		// `matches` is derived from `url`; re-subscribing on url change is enough.
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [url])

	return { data, missing, nextPoll }
}

export function useSession(id: string) {
	return useLive<Dashboard>(`/api/sessions/${encodeURIComponent(id)}`, (changed) => changed === id)
}

export function useSessions() {
	return useLive<SessionSummary[]>("/api/sessions", () => true)
}

/** Re-renders every second, so clocks and "x ago" stay true to the real clock. */
export function useNow(): number {
	const [now, setNow] = useState(() => Date.now())
	useEffect(() => {
		const timer = setInterval(() => setNow(Date.now()), 1000)
		return () => clearInterval(timer)
	}, [])
	return now
}

export const fmtTime = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })

export function ago(iso: string | null, now: number): string {
	if (!iso) return ""
	const s = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000))
	if (s < 10) return "just now"
	if (s < 60) return `${s}s ago`
	const m = Math.round(s / 60)
	if (m < 60) return `${m} min ago`
	return `${Math.floor(m / 60)}h ${m % 60}m ago`
}

/** "in 3h 20m" or "2h 5m overdue", by the real clock. */
export function until(iso: string, now: number): string {
	const s = Math.round((new Date(iso).getTime() - now) / 1000)
	const a = Math.abs(s)
	const h = Math.floor(a / 3600)
	const m = Math.floor((a % 3600) / 60)
	const text = h ? `${h}h ${m}m` : m ? `${m} min` : `${a}s`
	return s >= 0 ? `in ${text}` : `${text} overdue`
}

export function span(fromIso: string | null, toIso: string | null, now: number): string {
	if (!fromIso) return ""
	const s = Math.max(0, Math.round(((toIso ? new Date(toIso).getTime() : now) - new Date(fromIso).getTime()) / 1000))
	const h = Math.floor(s / 3600)
	const m = Math.floor((s % 3600) / 60)
	return h ? `${h}h ${m}m` : m ? `${m} min` : `${s}s`
}

export function hrefFor(link: string): string | null {
	if (!link) return null
	if (/^https?:\/\//.test(link)) return link
	if (link.startsWith("/")) return `file://${encodeURI(link)}`
	return link
}

export type Group = { name: string; tasks: Task[]; done: number; complete: boolean }

/** Tasks by the request they belong to: unfinished requests first (newest on top), finished ones last. */
export function groupTasks(tasks: Task[]): Group[] {
	const order: string[] = []
	const byName = new Map<string, Task[]>()
	for (const task of tasks) {
		const name = task.group || "Tasks"
		if (!byName.has(name)) {
			byName.set(name, [])
			order.push(name)
		}
		byName.get(name)?.push(task)
	}
	const groups = order.reverse().map((name) => {
		const list = byName.get(name) ?? []
		const done = list.filter((task) => task.status === "done").length
		return { name, tasks: list, done, complete: done === list.length }
	})
	return groups.sort((a, b) => Number(a.complete) - Number(b.complete))
}

export const slug = (name: string) => `g-${name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`
