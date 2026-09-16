---
name: triple-escalator
description: >-
  Run coding work through persistent PR-scoped DeepSeek Flash and Pro workers
  on OpenRouter, with final rescue by the originating conversation's model.
  Use when asked for triple escalator or the cheap-first coding cascade.
metadata:
  version: "0.7.0"
---

# Triple Escalator

The originating conversation owns diagnosis, architecture, the plan and acceptance
criteria. One generalist Flash worker carries implementation through the PR. Pro
handles failed tasks in its own persistent conversation. Final rescue returns to
the originating parent, never an intermediate coordinator or a newly chosen model.

Resolve this skill's directory from the loaded SKILL.md. In the commands below,
`SKILL` means that absolute directory, not another agent's installation.

## Parent and workers

At session creation, record the originating conversation reference and its observed
model identity. If the model name is unavailable, record `inherit` and preserve the
conversation reference. Never guess a model slug or hardcode a frontier model.
Host model selection remains under the user's control; return rescue to that same
conversation using its host-selected model. An explicit user rescue-model override
is recorded separately in the parent brief and takes precedence.

- Default to one Flash worker per PR/workstream. Reuse it across tasks and retries.
- Create Pro only on escalation and reuse it for later escalations in this PR.
- A second generalist Flash worker is optional when independent work warrants it;
  enable it at session creation. Do not create auth/UI/database specialist swarms.
- Keep worker history until the PR is finished or abandoned. Close the session then;
  preserve its journal. Workers resume after host restarts and incur no idle API calls.
- Persistence is saved conversation context, not model training. Root-chat history
  is not automatically exported to workers. Supply only approved, relevant context.

Read [provider-policy.md](references/provider-policy.md) before external calls.
Keep restricted data, credentials, money/account operations and work without a
reliable done-check in the originating parent. Updating this skill itself does
not require recursively running its cascade.

## Start and resume

Use `scripts/cascade_session.py` to initialise one private directory outside the
repository. Keep its path in the parent task's progress record. Do not initialise
a new session just because a task, rung or conversation turn changed.

The short parent-approved brief contains the goal, settled architecture/schema
choices, constraints, rejected approaches, current plan and runnable done-checks.
Update it when decisions change. Read [session commands](references/sessions.md)
for the commands and report format.

For each task:

1. Establish the baseline and a stable task ID. The parent diagnoses baseline failures.
   Include current source for the task, relevant changes since the worker last acted,
   exact scope and acceptance checks. Old conversation code is not current evidence.
2. Run the existing Flash worker with `--session` and `--task`. A fresh reply filename
   preserves attempt evidence; it does not create a fresh worker. The runner checks
   the live provider catalogue, pins an approved endpoint and restores the conversation.
3. Inspect the proposed edits, apply with `cascade_apply.py`, and run the done-checks.
   API workers propose edits; they cannot execute tests. Their report is not verification.
   Record the observed check result, brief failure detail and a stable failure tag.
4. Feed the result back to the same worker. Allow one attempt and one justified retry
   per external rung per task. A new task does not erase earlier lessons. Do not rename
   the same failed task to reset its retry allowance.
5. If Flash fails, prepare the handover below and resume/start Pro. If Pro fails,
   the originating parent reads the actual diff and failure evidence, then rescues
   directly. Never launch a separate expensive coordinator or rescue API call unless
   the user explicitly configured a host-specific rescue override.
6. Preserve valid edits. Identify which edits remain applied and which were reverted;
   do not automatically reset the whole task between rungs. Restore only attributable
   failed changes and keep unrelated user work. The next worker gets the current state.
7. Send accepted Pro/parent corrections back as a shared session note before Flash's
   next assignment. Do not send Flash back into the same unresolved escalated failure.

The runner and applier reject stale revisions. Coordinate writes when using two
workers; parallel edits in one checkout can invalidate another proposal. Rebase the
brief/source and resume the same worker, never silently apply stale output.

A demonstrated runner/configuration defect is repaired and restarted at Flash,
using the same saved worker. It does not count as a model failure. Record its cost;
if the identical infrastructure fault repeats, report it instead of looping.

## Escalation handover

The worker returns a short report with its attempted approach, proposed changes
and remaining problems alongside its edits. The parent adds observed tests/errors,
rejected approaches and the applied/reverted state. `handoff` assembles the recorded
reports, checks, current revision and actual working-tree diff without an API call.

Before handing over, the parent **must read the actual diff and failure output**.
Include committed changes and untracked files when relevant; the helper's HEAD diff
alone does not contain them. Pass Pro a relevant handover and current source, not
an unfiltered copy of the root conversation. A background coordinator hands this
back to the originating parent for final rescue; it never promotes itself.

## Visible transitions

Before starting, retrying, restarting or escalating, post the appropriate standalone
bold banner, followed by one sentence giving the previous failure and recorded
cost (or unknown). Tool output alone is not the announcement.

- `**--- Starting with Flash ---**`
- `**--- Continuing with Flash ---**` for a new task in the same worker
- `**--- Retrying Flash ---**` or `**--- Retrying Pro ---**`
- `**--- Restarting with Flash ---**` after a runner repair
- `**--- Escalation to Pro ---**`
- `**--- Escalation to <originating parent model> ---**` using the observed identity;
  if unavailable, say `--- Escalation to originating parent ---` rather than inventing one.

## Context and measurements

When context gets unwieldy, the parent writes a concise checkpoint preserving the
settled decisions, rejected approaches, feedback, current revision, edits and open
checks. `compact` uses it for future requests while preserving the full journal.
Do this at a useful task boundary or before capacity exhaustion, not every turn.
No extra model call is required. Shared notes can be folded into the current brief
using `brief`; use the documented note checkpoint to avoid resending folded notes.

The runner records API-reported input/output tokens, known cost, request duration
and failed responses. The parent records check results and concise failure tags
from checks it already ran. `summary` reports repeated tags and wall time to the
first passing check. Reasoning tokens are part of completion tokens, not added twice.
Parent usage is separate and unknown unless the host supplies it. Missing usage/cost
stays unknown. No extra LLM graders, periodic self-analysis, dashboards or benchmark
reruns solely to fill counters. Inspect the summary at PR completion or when asked.

Compare similar tasks using total available cost/tokens, elapsed time, repeated
failures and correctness. Do not claim intelligence gains or savings from the
existence of metrics. Preserve independent final review required by the repository.

## Provider limits

Flash and Pro default to high reasoning. The runner requests the approved endpoint's
live output allowance after reserving input context; it adds no fixed application
output cap. Provider/model limits still exist. Do not weaken the provider allowlist,
no-data-collection or zero-retention controls to get a response. Truncated, empty or
invalid replies remain in history but are never usable patches. `--one-shot` is for
explicit protocol diagnostics only, never the normal implementation path.
