import { AlarmClockIcon, AlertTriangleIcon, ArrowLeftIcon, CompassIcon, CheckCircle2Icon, CircleDashedIcon, CircleIcon, ExternalLinkIcon, LayoutGridIcon, LoaderIcon, MessageCircleQuestionIcon, MoonIcon, PackageIcon, SunIcon } from "lucide-react"
import { useEffect, useState } from "react"
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { type ChartConfig, ChartContainer, ChartTooltip } from "@/components/ui/chart"
import { Separator } from "@/components/ui/separator"
import {
	Sidebar,
	SidebarContent,
	SidebarFooter,
	SidebarGroup,
	SidebarGroupLabel,
	SidebarHeader,
	SidebarInset,
	SidebarMenu,
	SidebarMenuBadge,
	SidebarMenuButton,
	SidebarMenuItem,
	SidebarProvider,
	SidebarTrigger,
} from "@/components/ui/sidebar"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { TooltipProvider } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { ago, type Dashboard, type FollowUp, until, fmtTime, type Group, groupTasks, hrefFor, REFRESH_MS, type SessionSummary, slug, span, type Task, type TaskStatus, useNow, useSession, useSessions } from "./dash/data"

const QUIET_MINUTES = 15

export default function App() {
	useTheme()
	const match = /^\/s\/([a-z0-9-]+)\/?$/.exec(window.location.pathname)
	return match ? <SessionView id={match[1]} /> : <SessionsIndex />
}

function SessionView({ id }: { id: string }) {
	const { data, missing, nextPoll } = useSession(id)
	const now = useNow()

	useEffect(() => {
		if (!data) return
		const open = data.questions.filter((q) => !q.answer).length
		document.title = `${open ? `(${open}) ` : ""}${data.title}`
	}, [data])

	if (missing) return <Centered>No dashboard for this session yet. <a className="underline" href="/">See all sessions</a></Centered>
	if (!data) return <Centered>Loading…</Centered>

	const groups = groupTasks(data.tasks)
	return (
		<TooltipProvider>
			<SidebarProvider style={{ "--sidebar-width": "calc(var(--spacing) * 72)", "--header-height": "calc(var(--spacing) * 14)" } as React.CSSProperties}>
				<SessionSidebar data={data} groups={groups} now={now} />
				<SidebarInset>
					<SiteHeader data={data} now={now} nextPoll={nextPoll} />
					<div className="@container/main flex flex-1 flex-col gap-4 py-4 md:gap-6 md:py-6">
						{data.goal ? <p className="px-4 text-muted-foreground text-sm lg:px-6">{data.goal}</p> : null}
						<WhereWeAre data={data} now={now} />
						<SectionCards data={data} now={now} />
						<div className="grid gap-4 px-4 md:gap-6 lg:px-6 @5xl/main:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
							<div className="flex min-w-0 flex-col gap-4 md:gap-6">
								<Questions data={data} now={now} />
								<CheckBacks followups={data.followups ?? []} now={now} />
								<StuckList data={data} now={now} />
								<ProgressChart data={data} now={now} />
								{groups.map((group) => (
									<WorkGroup group={group} key={group.name} now={now} tasks={data.tasks} />
								))}
							</div>
							<div className="flex min-w-0 flex-col gap-4 md:gap-6">
								<Deliverables data={data} now={now} />
								<Activity data={data} />
							</div>
						</div>
					</div>
				</SidebarInset>
			</SidebarProvider>
		</TooltipProvider>
	)
}

function liveState(data: Dashboard, now: number): { word: string; tone: "live" | "quiet" | "over" } {
	if (data.finishedAt) return { word: "Finished", tone: "over" }
	const quiet = (now - new Date(data.updatedAt).getTime()) / 60_000
	if (quiet > QUIET_MINUTES) return { word: `Quiet for ${Math.round(quiet)} min`, tone: "quiet" }
	return { word: "Working", tone: "live" }
}

function LiveDot({ tone }: { tone: "live" | "quiet" | "over" }) {
	return (
		<span className="relative flex size-2.5" aria-hidden>
			{tone === "live" ? <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-60 motion-reduce:animate-none" /> : null}
			<span className={cn("relative inline-flex size-2.5 rounded-full", tone === "live" ? "bg-emerald-500" : tone === "quiet" ? "bg-amber-500" : "bg-muted-foreground")} />
		</span>
	)
}

function Centered({ children }: { children: React.ReactNode }) {
	return <div className="flex min-h-svh items-center justify-center gap-1 text-muted-foreground">{children}</div>
}

function SessionSidebar({ data, groups, now }: { data: Dashboard; groups: Group[]; now: number }) {
	const live = liveState(data, now)
	return (
		<Sidebar collapsible="offcanvas" variant="inset">
			<SidebarHeader>
				<SidebarMenu>
					<SidebarMenuItem>
						<SidebarMenuButton render={<a href="/" />}>
							<ArrowLeftIcon />
							<span>All sessions</span>
						</SidebarMenuButton>
					</SidebarMenuItem>
				</SidebarMenu>
				<div className="flex flex-col gap-1 px-2 py-1.5">
					<span className="flex items-center gap-2 font-medium text-muted-foreground text-xs uppercase tracking-wide">
						<LiveDot tone={live.tone} />
						{live.word}
					</span>
					<span className="font-semibold text-base leading-tight">{data.title}</span>
				</div>
			</SidebarHeader>
			<SidebarContent>
				<SidebarGroup>
					<SidebarGroupLabel>What you asked for</SidebarGroupLabel>
					<SidebarMenu>
						{groups.map((group) => (
							<SidebarMenuItem key={group.name}>
								<SidebarMenuButton className="pr-12" render={<a href={`#${slug(group.name)}`} />} tooltip={group.name}>
									{group.complete ? (
										<CheckCircle2Icon className="text-emerald-500" />
									) : group.tasks.some((t) => t.status === "doing") ? (
										<LoaderIcon className="animate-spin text-blue-500 motion-reduce:animate-none [animation-duration:2.5s]" />
									) : group.tasks.some((t) => t.status === "blocked") ? (
										<AlertTriangleIcon className="text-destructive" />
									) : (
										<CircleDashedIcon className="text-muted-foreground" />
									)}
									<span className={cn("truncate", group.complete && "text-muted-foreground")}>{group.name}</span>
								</SidebarMenuButton>
								<SidebarMenuBadge className="font-mono tabular-nums">
									{group.done}/{group.tasks.length}
								</SidebarMenuBadge>
							</SidebarMenuItem>
						))}
					</SidebarMenu>
				</SidebarGroup>
			</SidebarContent>
			<SidebarFooter>
				<div className="px-2 pb-1 text-muted-foreground text-xs">
					Started {fmtTime(data.startedAt)} · {span(data.startedAt, data.finishedAt, now)} {data.finishedAt ? "in total" : "so far"}
				</div>
			</SidebarFooter>
		</Sidebar>
	)
}

/** Dark by default; the choice is remembered in this browser. */
function useTheme(): [boolean, () => void] {
	const [dark, setDark] = useState(() => {
		try {
			return localStorage.getItem("dash-theme") !== "light"
		} catch {
			return true
		}
	})
	useEffect(() => {
		document.documentElement.classList.toggle("dark", dark)
		try {
			localStorage.setItem("dash-theme", dark ? "dark" : "light")
		} catch {
			// Storage can be blocked; the theme still applies for this visit.
		}
	}, [dark])
	return [dark, () => setDark((value) => !value)]
}

function ThemeButton() {
	const [dark, toggle] = useTheme()
	return (
		<Button aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} onClick={toggle} size="icon" variant="ghost">
			{dark ? <SunIcon /> : <MoonIcon />}
		</Button>
	)
}

function Clock({ now }: { now: number }) {
	return <span className="font-mono text-lg tabular-nums tracking-tight">{new Date(now).toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" })}</span>
}

function SiteHeader({ data, now, nextPoll }: { data: Dashboard; now: number; nextPoll: number }) {
	const left = Math.max(0, nextPoll - now) / REFRESH_MS
	return (
		<header className="sticky top-0 z-10 flex h-(--header-height) shrink-0 items-center gap-2 border-b bg-background/80 backdrop-blur">
			<div className="flex w-full items-center gap-2 px-4 lg:px-6">
				<SidebarTrigger className="-ml-1" />
				<Separator className="mx-2 h-4 data-vertical:self-auto" orientation="vertical" />
				<h1 className="truncate font-medium text-base">{data.title}</h1>
				<div className="ml-auto flex items-center gap-3">
					<span className="hidden items-center gap-1.5 text-muted-foreground text-xs sm:flex" title="Checks for updates every 10 seconds">
						<svg aria-hidden className="size-3.5 -rotate-90" viewBox="0 0 14 14">
							<circle className="stroke-muted" cx="7" cy="7" fill="none" r="5" strokeWidth="2.5" />
							<circle className="stroke-muted-foreground transition-[stroke-dashoffset] duration-1000 ease-linear" cx="7" cy="7" fill="none" r="5" strokeDasharray="31.4" strokeDashoffset={31.4 * left} strokeLinecap="round" strokeWidth="2.5" />
						</svg>
						Updated {ago(data.updatedAt, now)}
					</span>
					<Clock now={now} />
					<ThemeButton />
				</div>
			</div>
		</header>
	)
}

function count(tasks: Task[], status: TaskStatus) {
	return tasks.filter((task) => task.status === status).length
}

function SectionCards({ data, now }: { data: Dashboard; now: number }) {
	const total = data.tasks.length
	const done = count(data.tasks, "done")
	const doing = data.tasks.filter((task) => task.status === "doing")
	const open = data.questions.filter((q) => !q.answer)
	const stuck = data.stuck.filter((s) => !s.clearedAt)
	const oldestQuestion = open[0]?.askedAt ?? null
	return (
		<div className="grid grid-cols-1 gap-4 px-4 *:data-[slot=card]:bg-linear-to-t *:data-[slot=card]:from-primary/5 *:data-[slot=card]:to-card *:data-[slot=card]:shadow-xs lg:px-6 @xl/main:grid-cols-2 @5xl/main:grid-cols-4 dark:*:data-[slot=card]:bg-card">
			<Card className="@container/card">
				<CardHeader>
					<CardDescription>Steps done</CardDescription>
					<CardTitle className="font-semibold text-2xl tabular-nums @[250px]/card:text-3xl">
						{done}
						<span className="text-muted-foreground text-lg"> / {total}</span>
					</CardTitle>
					<CardAction>
						<Badge variant="outline">{total ? Math.round((done / total) * 100) : 0}%</Badge>
					</CardAction>
				</CardHeader>
				<CardFooter>
					<div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
						<div className="h-full rounded-full bg-emerald-500 transition-[width] duration-700 ease-out" style={{ width: `${total ? (done / total) * 100 : 0}%` }} />
					</div>
				</CardFooter>
			</Card>
			<Card className="@container/card">
				<CardHeader>
					<CardDescription>In progress</CardDescription>
					<CardTitle className="font-semibold text-2xl tabular-nums @[250px]/card:text-3xl">{doing.length}</CardTitle>
					<CardAction>
						<LoaderIcon className={cn("size-4 text-blue-500", doing.length && "animate-spin motion-reduce:animate-none [animation-duration:2.5s]")} />
					</CardAction>
				</CardHeader>
				<CardFooter className="text-muted-foreground text-sm">
					<span className="line-clamp-1">{doing[0] ? doing[0].title : "Nothing running right now"}</span>
				</CardFooter>
			</Card>
			<Card className={cn("@container/card", open.length && "ring-1 ring-amber-500/60")}>
				<CardHeader>
					<CardDescription>Questions for you</CardDescription>
					<CardTitle className={cn("font-semibold text-2xl tabular-nums @[250px]/card:text-3xl", open.length && "text-amber-600 dark:text-amber-400")}>{open.length}</CardTitle>
					<CardAction>
						<MessageCircleQuestionIcon className={cn("size-4", open.length ? "text-amber-500" : "text-muted-foreground")} />
					</CardAction>
				</CardHeader>
				<CardFooter className="text-muted-foreground text-sm">{oldestQuestion ? `Oldest asked ${ago(oldestQuestion, now)}` : "Nothing waiting on you"}</CardFooter>
			</Card>
			<Card className={cn("@container/card", stuck.length && "ring-1 ring-destructive/60")}>
				<CardHeader>
					<CardDescription>Stuck</CardDescription>
					<CardTitle className={cn("font-semibold text-2xl tabular-nums @[250px]/card:text-3xl", stuck.length && "text-destructive")}>{stuck.length}</CardTitle>
					<CardAction>
						<AlertTriangleIcon className={cn("size-4", stuck.length ? "text-destructive" : "text-muted-foreground")} />
					</CardAction>
				</CardHeader>
				<CardFooter className="text-muted-foreground text-sm">{stuck[0] ? `Longest stuck ${span(stuck[0].since, null, now)}` : "Nothing blocked"}</CardFooter>
			</Card>
		</div>
	)
}

/** The North Star: someone back after hours away knows where this is up to in seconds. */
function WhereWeAre({ data, now }: { data: Dashboard; now: number }) {
	const s = data.summary
	return (
		<div className="px-4 lg:px-6">
			<Card className="border-primary/30 bg-linear-to-br from-primary/10 via-card to-card">
				<CardHeader>
					<CardTitle className="flex items-center gap-2">
						<CompassIcon className="size-4" />
						Where we're up to
					</CardTitle>
					<CardAction className="text-muted-foreground text-xs">{s ? `Updated ${ago(s.at, now)}` : null}</CardAction>
				</CardHeader>
				<CardContent>
					{s ? (
						<dl className="grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-4">
							{[
								["What this is for", s.for],
								["Where it's at", s.now],
								["What's next", s.next],
								["Waiting on you", s.waiting || "Nothing"],
							].map(([label, text]) => (
								<div className="animate-in fade-in duration-500" key={label}>
									<dt className="font-medium text-muted-foreground text-xs uppercase tracking-wide">{label}</dt>
									<dd className={cn("mt-1 leading-relaxed", label === "Waiting on you" && s.waiting && "font-medium text-amber-600 dark:text-amber-400")}>{text}</dd>
								</div>
							))}
						</dl>
					) : (
						<p className="text-muted-foreground text-sm">No summary yet. {data.goal}</p>
					)}
				</CardContent>
			</Card>
		</div>
	)
}

function CheckBacks({ followups, now }: { followups: FollowUp[]; now: number }) {
	const open = followups.filter((f) => !f.doneAt).sort((a, b) => a.dueAt.localeCompare(b.dueAt))
	const recent = followups.filter((f) => f.doneAt).slice(-3).reverse()
	if (open.length + recent.length === 0) return null
	return (
		<Card>
			<CardHeader>
				<CardTitle className="flex items-center gap-2">
					<AlarmClockIcon className="size-4" />
					Check-backs
				</CardTitle>
				<CardDescription>Things to look at again later, to see whether they worked.</CardDescription>
			</CardHeader>
			<CardContent className="flex flex-col gap-2">
				{[...open, ...recent].map((f) => {
					const overdue = !f.doneAt && new Date(f.dueAt).getTime() <= now
					return (
						<div className={cn("animate-in fade-in slide-in-from-bottom-1 rounded-lg border p-3 duration-500", overdue && "border-amber-500/60 bg-amber-500/5", f.doneAt && "opacity-70")} key={`${f.id}-${f.doneAt ? "d" : "o"}`}>
							<div className="flex items-start justify-between gap-3">
								<p className="font-medium">{f.what}</p>
								<Badge className={cn("shrink-0", overdue && "border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-400")} variant="outline">
									{f.doneAt ? "Checked" : overdue ? "Due now" : until(f.dueAt, now)}
								</Badge>
							</div>
							{f.how ? <p className="text-muted-foreground text-sm">How: {f.how}</p> : null}
							{f.result ? <p className="text-sm">Result: {f.result}</p> : null}
							<p className="mt-1 text-muted-foreground text-xs">{f.doneAt ? `Checked ${fmtTime(f.doneAt)}` : `Due ${fmtTime(f.dueAt)} · ${until(f.dueAt, now)}`}</p>
						</div>
					)
				})}
			</CardContent>
		</Card>
	)
}

function Questions({ data, now }: { data: Dashboard; now: number }) {
	const open = data.questions.filter((q) => !q.answer)
	const answered = data.questions.filter((q) => q.answer).slice(-3).reverse()
	if (open.length + answered.length === 0) return null
	return (
		<Card className="border-amber-500/50 bg-linear-to-b from-amber-500/10 to-card">
			<CardHeader>
				<CardTitle className="flex items-center gap-2 text-amber-700 dark:text-amber-400">
					<MessageCircleQuestionIcon className="size-4" />
					Questions for you
				</CardTitle>
				<CardDescription>Work carries on with the default until you answer.</CardDescription>
			</CardHeader>
			<CardContent className="flex flex-col gap-3">
				{[...open, ...answered].map((q) => (
					<div className={cn("animate-in fade-in slide-in-from-bottom-1 rounded-lg border bg-card p-3 duration-500", q.answer ? "opacity-70" : "border-amber-500/50")} key={`${q.id}-${q.answer ? "a" : "o"}`}>
						<p className="font-medium">{q.question}</p>
						<p className="mt-1 text-muted-foreground text-sm">
							<span className="font-medium text-foreground">{q.answer ? "Your answer: " : "Until you answer: "}</span>
							{q.answer ?? q.default}
						</p>
						<p className="mt-1 text-muted-foreground text-xs">{q.answer && q.answeredAt ? `Answered ${fmtTime(q.answeredAt)}` : `Asked ${fmtTime(q.askedAt)} · ${ago(q.askedAt, now)}`}</p>
					</div>
				))}
			</CardContent>
		</Card>
	)
}

function StuckList({ data, now }: { data: Dashboard; now: number }) {
	const stuck = data.stuck.filter((s) => !s.clearedAt)
	if (stuck.length === 0) return null
	return (
		<Card className="border-destructive/50">
			<CardHeader>
				<CardTitle className="flex items-center gap-2 text-destructive">
					<AlertTriangleIcon className="size-4" />
					Stuck
				</CardTitle>
			</CardHeader>
			<CardContent className="flex flex-col gap-3">
				{stuck.map((s) => (
					<div className="animate-in fade-in slide-in-from-bottom-1 rounded-lg border-destructive border-l-4 bg-destructive/5 p-3 duration-500" key={s.id}>
						<p className="font-medium">{s.what}</p>
						{s.why ? <p className="text-muted-foreground text-sm">{s.why}</p> : null}
						<p className="mt-1 text-muted-foreground text-xs">
							Stuck for {span(s.since, null, now)} · since {fmtTime(s.since)}
						</p>
					</div>
				))}
			</CardContent>
		</Card>
	)
}

const chartConfig = { done: { label: "Steps finished", color: "var(--chart-2)" } } satisfies ChartConfig

function ProgressChart({ data, now }: { data: Dashboard; now: number }) {
	const finished = data.tasks
		.filter((task) => task.status === "done" && task.finishedAt)
		.map((task) => new Date(task.finishedAt ?? "").getTime())
		.sort((a, b) => a - b)
	const start = new Date(data.startedAt).getTime()
	const end = data.finishedAt ? new Date(data.finishedAt).getTime() : now
	const points = [{ t: start, done: 0 }, ...finished.map((t, i) => ({ t, done: i + 1 })), { t: end, done: finished.length }]
	return (
		<Card className="@container/card">
			<CardHeader>
				<CardTitle>Steps finished</CardTitle>
				<CardDescription>Across the session, by the real clock</CardDescription>
			</CardHeader>
			<CardContent className="px-2 pt-0 sm:px-6">
				<ChartContainer className="aspect-auto h-[180px] w-full" config={chartConfig}>
					<AreaChart data={points} margin={{ left: 0, right: 8, top: 8 }}>
						<defs>
							<linearGradient id="fillDone" x1="0" x2="0" y1="0" y2="1">
								<stop offset="5%" stopColor="var(--color-done)" stopOpacity={0.8} />
								<stop offset="95%" stopColor="var(--color-done)" stopOpacity={0.05} />
							</linearGradient>
						</defs>
						<CartesianGrid vertical={false} />
						<XAxis axisLine={false} dataKey="t" domain={[start, end]} minTickGap={48} scale="time" tickFormatter={(t: number) => fmtTime(new Date(t).toISOString())} tickLine={false} tickMargin={8} type="number" />
						<YAxis allowDecimals={false} axisLine={false} tickLine={false} width={28} />
						<ChartTooltip
							content={({ active, payload }) =>
								active && payload?.[0] ? (
									<div className="rounded-lg border bg-background px-2.5 py-1.5 text-xs shadow-xl">
										<div className="font-medium">{fmtTime(new Date(payload[0].payload.t).toISOString())}</div>
										<div className="text-muted-foreground">{payload[0].payload.done} steps finished</div>
									</div>
								) : null
							}
							cursor={false}
						/>
						<Area dataKey="done" fill="url(#fillDone)" stroke="var(--color-done)" type="stepAfter" />
					</AreaChart>
				</ChartContainer>
			</CardContent>
		</Card>
	)
}

const STATUS: Record<TaskStatus, { label: string; className: string }> = {
	todo: { label: "To do", className: "text-muted-foreground" },
	doing: { label: "In progress", className: "border-blue-500/40 bg-blue-500/10 text-blue-600 dark:text-blue-400" },
	done: { label: "Done", className: "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" },
	blocked: { label: "Blocked", className: "border-destructive/40 bg-destructive/10 text-destructive" },
}

function StatusBadge({ status }: { status: TaskStatus }) {
	const meta = STATUS[status]
	return (
		<Badge className={cn("animate-in fade-in zoom-in-95 gap-1.5 duration-500", meta.className)} key={status} variant="outline">
			{status === "doing" ? <span className="size-1.5 animate-pulse rounded-full bg-current motion-reduce:animate-none" /> : status === "done" ? <CheckCircle2Icon /> : <CircleIcon />}
			{meta.label}
		</Badge>
	)
}

function WorkGroup({ group, now, tasks }: { group: Group; now: number; tasks: Task[] }) {
	return (
		<Card className={cn("scroll-mt-20 transition-opacity", group.complete && "opacity-80")} id={slug(group.name)}>
			<CardHeader>
				<CardTitle className="text-base">{group.name}</CardTitle>
				<CardAction>
					<Badge className="font-mono tabular-nums" variant={group.complete ? "secondary" : "outline"}>
						{group.done}/{group.tasks.length}
					</Badge>
				</CardAction>
				<div className="col-span-full mt-2 h-1 overflow-hidden rounded-full bg-muted">
					<div className="h-full rounded-full bg-emerald-500 transition-[width] duration-700 ease-out" style={{ width: `${(group.done / group.tasks.length) * 100}%` }} />
				</div>
			</CardHeader>
			<CardContent className="px-0">
				<Table>
					<TableHeader className="sr-only">
						<TableRow>
							<TableHead>Step</TableHead>
							<TableHead>Status</TableHead>
						</TableRow>
					</TableHeader>
					<TableBody>
						{group.tasks.map((task) => (
							<TableRow className="animate-in fade-in slide-in-from-bottom-1 duration-500" key={task.id}>
								<TableCell className="w-10 pl-6 align-top font-mono text-muted-foreground text-xs tabular-nums">{tasks.indexOf(task) + 1}</TableCell>
								<TableCell className="whitespace-normal align-top">
									<div className={cn("font-medium", task.status === "done" && "text-muted-foreground")}>{task.title}</div>
									{timing(task, now) ? <div className="text-muted-foreground text-xs">{timing(task, now)}</div> : null}
									{task.note ? <div className="mt-0.5 text-muted-foreground text-sm">{task.note}</div> : null}
								</TableCell>
								<TableCell className="pr-6 text-right align-top">
									<StatusBadge status={task.status} />
								</TableCell>
							</TableRow>
						))}
					</TableBody>
				</Table>
			</CardContent>
		</Card>
	)
}

function timing(task: Task, now: number): string {
	if (task.status === "done" && task.startedAt && task.finishedAt) return `Took ${span(task.startedAt, task.finishedAt, now)} · finished ${fmtTime(task.finishedAt)}`
	if (task.status === "done" && task.finishedAt) return `Finished ${fmtTime(task.finishedAt)}`
	if (task.status === "doing" && task.startedAt) return `Started ${fmtTime(task.startedAt)} · ${span(task.startedAt, null, now)} so far`
	return ""
}

function Deliverables({ data, now }: { data: Dashboard; now: number }) {
	return (
		<Card>
			<CardHeader>
				<CardTitle className="flex items-center gap-2">
					<PackageIcon className="size-4" />
					Latest deliverables
				</CardTitle>
				<CardAction>
					<Badge variant="outline">{data.deliverables.length}</Badge>
				</CardAction>
			</CardHeader>
			<CardContent className="flex flex-col gap-2">
				{data.deliverables.length === 0 ? <p className="text-muted-foreground text-sm">Nothing delivered yet.</p> : null}
				{data.deliverables.slice(0, 10).map((d) => {
					const href = hrefFor(d.link)
					return (
						<div className="animate-in fade-in slide-in-from-bottom-1 rounded-lg border p-3 duration-500" key={`${d.at}-${d.title}`}>
							{href ? (
								<a className="inline-flex items-center gap-1.5 font-medium hover:underline" href={href} rel="noreferrer" target="_blank">
									{d.title}
									<ExternalLinkIcon className="size-3.5 text-muted-foreground" />
								</a>
							) : (
								<span className="font-medium">{d.title}</span>
							)}
							{d.note ? <p className="text-muted-foreground text-sm">{d.note}</p> : null}
							<p className="text-muted-foreground text-xs">
								{fmtTime(d.at)} · {ago(d.at, now)}
							</p>
						</div>
					)
				})}
			</CardContent>
		</Card>
	)
}

function Activity({ data }: { data: Dashboard }) {
	return (
		<Card>
			<CardHeader>
				<CardTitle>Activity</CardTitle>
			</CardHeader>
			<CardContent>
				<ol className="flex flex-col gap-2">
					{data.log.slice(0, 16).map((entry) => (
						<li className="grid animate-in grid-cols-[4.5rem_1fr] gap-2 fade-in text-sm duration-500" key={`${entry.at}-${entry.text}`}>
							<span className="font-mono text-muted-foreground text-xs tabular-nums leading-5">{fmtTime(entry.at)}</span>
							<span>{entry.text}</span>
						</li>
					))}
				</ol>
			</CardContent>
		</Card>
	)
}

function SessionsIndex() {
	const { data } = useSessions()
	const now = useNow()
	useEffect(() => {
		const waiting = (data ?? []).reduce((n, s) => n + s.openQuestions, 0)
		document.title = `${waiting ? `(${waiting}) ` : ""}Sessions`
	}, [data])
	const live = (data ?? []).filter((s) => !s.finishedAt)
	const finished = (data ?? []).filter((s) => s.finishedAt)
	return (
		<div className="min-h-svh bg-background">
			<header className="sticky top-0 z-10 flex h-14 items-center gap-2 border-b bg-background/80 px-4 backdrop-blur lg:px-6">
				<LayoutGridIcon className="size-4 text-muted-foreground" />
				<h1 className="font-medium text-base">Sessions</h1>
				<div className="ml-auto flex items-center gap-3">
					<Clock now={now} />
					<ThemeButton />
				</div>
			</header>
			<main className="mx-auto flex max-w-6xl flex-col gap-6 p-4 lg:p-6">
				{data && data.length === 0 ? <p className="text-muted-foreground">No sessions yet. A dashboard appears here when a Claude session starts one.</p> : null}
				{live.length ? <SessionGrid now={now} sessions={live} title="Running" /> : null}
				{finished.length ? <SessionGrid now={now} sessions={finished} title="Finished" /> : null}
			</main>
		</div>
	)
}

function SessionGrid({ title, sessions, now }: { title: string; sessions: SessionSummary[]; now: number }) {
	return (
		<section className="flex flex-col gap-3">
			<h2 className="font-medium text-muted-foreground text-xs uppercase tracking-wide">{title}</h2>
			<div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
				{sessions.map((s) => {
					const quiet = (now - new Date(s.updatedAt).getTime()) / 60_000
					const tone = s.finishedAt ? "over" : quiet > QUIET_MINUTES ? "quiet" : "live"
					return (
						<a className="group animate-in fade-in slide-in-from-bottom-1 duration-500" href={`/s/${s.id}`} key={s.id}>
							<Card className={cn("h-full transition-colors group-hover:border-foreground/20", s.openQuestions && "ring-1 ring-amber-500/60")}>
								<CardHeader>
									<CardDescription className="flex items-center gap-2">
										<LiveDot tone={tone} />
										{s.finishedAt ? `Finished ${fmtTime(s.finishedAt)}` : `Updated ${ago(s.updatedAt, now)}`}
									</CardDescription>
									<CardTitle className="text-base leading-snug">{s.title}</CardTitle>
								</CardHeader>
								<CardContent className="flex flex-col gap-3">
									<p className="line-clamp-2 text-muted-foreground text-sm">{s.whereNow ?? (s.current ? `Now: ${s.current}` : s.goal)}</p>
									<div className="h-1.5 overflow-hidden rounded-full bg-muted">
										<div className="h-full rounded-full bg-emerald-500 transition-[width] duration-700 ease-out" style={{ width: `${s.total ? (s.done / s.total) * 100 : 0}%` }} />
									</div>
									<div className="flex flex-wrap items-center gap-2">
										<Badge className="font-mono tabular-nums" variant="outline">
											{s.done}/{s.total} done
										</Badge>
										{s.openQuestions ? (
											<Badge className="border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-400" variant="outline">
												{s.openQuestions} question{s.openQuestions === 1 ? "" : "s"} for you
											</Badge>
										) : null}
										{s.stuck ? <Badge variant="destructive">{s.stuck} stuck</Badge> : null}
										{s.checkBacksDue ? (
											<Badge className="border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-400" variant="outline">
												{s.checkBacksDue} check-back{s.checkBacksDue === 1 ? "" : "s"} due
											</Badge>
										) : null}
									</div>
								</CardContent>
							</Card>
						</a>
					)
				})}
			</div>
		</section>
	)
}

