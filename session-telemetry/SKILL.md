---
name: session-telemetry
description: Gives every long agent session one live dashboard at http://localhost:4200, so the user can come back after hours away and see where it's up to in seconds. Use at the start of any session whose work will take more than 5 steps or 30 minutes, and keep it updated after every step. Covers the "where we're up to" summary, tasks grouped by request, questions with a default action, deliverables, stuck items and timed check-backs. Also use when the user says "set up a dashboard", "where are we up to" or "show me the dashboard".
---

# Session telemetry

**North Star:** someone runs many agent sessions at once and loses the thread of each one. They open a session's page after hours away and know within seconds what it's for, where it's at, what's next, and what's waiting on them. Every update you make serves that.

One dashboard per session, not per task. Each thing the user asks for becomes a group of steps on it. All sessions are listed at `http://localhost:4200`; each session lives at `/s/<session>`. The page updates the moment data changes.

## One-time setup

If `~/.session-telemetry/dash.mjs` doesn't exist, run `./install.sh` from this skill's folder. It needs Node 20+. It builds the app, installs the server to start on login (launchd or systemd) and installs the `telemetry-builder` agent. Then `node ~/.session-telemetry/dash.mjs health` should say the server is up.

## When to start

As soon as the session's work has **more than 5 steps, or should take longer than 30 minutes**. Start once per session and never make a second dashboard for the same session.

## Starting it

If the `telemetry-builder` agent is available, launch it **in the background** and carry on with the work straight away. Never wait on it. Give it:

- a session name: `<YYYY-MM-DD>-<short-kebab-name>`, with the date from `date +%F`
- a title and a one-line goal
- every request so far as a group, with its steps in order and the status of any already done
- any questions (with defaults), deliverables and check-backs

It replies with `export DASH_SESSION=<session>` and the task IDs. They run t1, t2… in the order you gave the steps.

With no agent available, do it yourself with the commands below: `init`, `task add`, `summary`, then `open` the page.

## Keeping it current

The updater is `node ~/.session-telemetry/dash.mjs` (`$DASH_SESSION` or `--session <name>` picks the session). Updates are quick commands; don't send them to the agent.

- **After every step:** `task t7 done`, then `task t8 doing`.
- **New request:** `task add "<step>" --group "<the request, in the user's words>"`, one per step.
- **Where we're up to:** after every meaningful step, run `summary --for "<what this session is for>" --now "<where it's at>" --next "<what's next>" --waiting "<what needs the user, or leave it out>"`. It's the first thing they read, so write it for someone with no context: say what changed for them, not how it was built.
- **Decisions:** don't stop and wait. Run `ask "<question>" --default "<what you'll do meanwhile>"`, carry on with the default, and record the reply with `answer q2 "…"` when it comes.
- **Deliverables:** `deliver "<title>" --link <url-or-absolute-path>` for anything they can open.
- **Blockers:** `stuck "<what>" --why "<why>"` the moment something blocks you, and `unstuck s1` when it clears.
- **Check-backs:** `followup "<what to check>" --in 6h --how "<how to check>"` for anything worth a second look later (a deploy, a scheduled job, a reply). At the start of every turn, run `due` and handle anything it lists, then close it with `followup f1 done --note "<what it showed>"`.
- **End:** `finish`, and give the page address in your last message.

## Rules

- **Never type a time or date.** The updater stamps every time from the machine's clock.
- **Plain words everywhere.** No ticket numbers, commit hashes or branch names unless you explain them in the same breath.
- **If the page doesn't load,** run `dash.mjs health`, which restarts the server.
- **Don't edit files in `~/.session-telemetry/data` by hand.** Always go through the updater.

## All commands

```
dash.mjs init <session> --title "…" --goal "…"
dash.mjs task add "…" --group "…" [--note "…"]
dash.mjs task <id> todo|doing|done|blocked [--note "…"]
dash.mjs summary --for "…" --now "…" --next "…" [--waiting "…"]
dash.mjs ask "…" --default "…"        dash.mjs answer <id> "…"
dash.mjs deliver "…" --link <url-or-path> [--note "…"]
dash.mjs stuck "…" --why "…"          dash.mjs unstuck <id> [--note "…"]
dash.mjs followup "…" --in 30m|6h|2d [--how "…"]
dash.mjs followup <id> done [--note "…"]
dash.mjs due                          dash.mjs health
dash.mjs log "…"                      dash.mjs finish [--note "…"]
```
