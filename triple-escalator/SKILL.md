---
name: triple-escalator
description: >-
  One persistent Flash coding agent at max reasoning implements, self-reviews and
  tests a clear parent-authored plan. Real failures return directly to the original
  parent. Use for triple escalator or double escalation.
metadata:
  version: "1.0.0"
---

# Triple Escalator

The originating parent owns the plan, architecture, review and rescue.
**One persistent Flash worker implements the plan at max reasoning.** It is a full
coding agent with file, search, terminal, test and repair tools, including for
cross-file implementation and debugging. It is not limited to mechanical edits.

**Route: parent → Flash → parent.** Pro is outside the active workflow. Keep any
old Pro session and its edits/history intact, but do not invoke it. Reuse the same
Flash native session for the entire workstream, including review feedback and
later assignments. Do not create a second worker, specialists or nested agents.

The name and installation path `triple-escalator` remain for compatibility.
No session reset or duplicate skill is needed. This policy supersedes previous
Pro-first and three-step routing instructions in saved briefs.

Resolve `SKILL` to this loaded skill's absolute directory. Read
[worker commands](references/sessions.md) for setup and execution, and
[provider policy](references/provider-policy.md) before external calls.

## Execution and continuity

Use `scripts/cascade_agent.py`, which runs OpenCode's coding tool loop against
OpenRouter. **The old `cascade_run.py`/`cascade_apply.py` patch path is a legacy
protocol diagnostic, not the implementation workflow.** Do not silently fall back
to patch generation or parent-driven shell relays if the coding harness is broken.

- One persistent generalist Flash per workstream. Reuse its native session ID
  through assignments, feedback, compaction and host restarts. Keep the existing
  worker; do not spawn a fresh one per edit or test failure.
- Keep history after completion. Closing marks the PR finished; it does not delete
  journals, transcripts or native sessions. Idle workers incur no API calls.
- A saved conversation is retained context, not training. The parent supplies a
  concise plan and settled decisions, not its whole transcript or copied source.
  The worker reads current files and repository instructions itself.

The tested harness is OpenCode 1.18.31 on macOS. The runner uses a macOS filesystem
and network sandbox; other hosts fail closed pending a tested equivalent. Its
normal access is the assigned checkout, its private runtime and installed coding
tools. Extra dependency directories can be approved read-only. Permission rules
are not an excuse to read credentials or bypass the operating-system boundary.
Keep sensitive files out of delegated checkouts; this is not a secret scanner.

## Parent model

Record the original conversation reference and observed model when creating the
session. If unknown, use `inherit`. Final rescue returns to that conversation and
its host-selected model, never an intermediate coordinator. An explicit host-specific
rescue override takes precedence. Do not hardcode a frontier model in the generic skill.
Updating this skill does not require recursively delegating its own update.

## Workflow

1. **Parent writes the implementation plan.** Define the user outcome, current
   behaviour, relevant components and their interfaces, data flow, dependencies,
   invariants and integration risks. State settled decisions, scope exclusions,
   exact acceptance checks and required evidence. Invest thought here; do not
   outsource unresolved architecture or give the worker a vague outcome alone.
   Keep the plan concise and grounded in current source. Restricted actions stay
   with the parent; arrange safe fixtures and local checks before dispatch.
2. **Flash owns implementation through acceptance.** It reads source and repo
   instructions, checks the baseline, edits code, adds meaningful regressions,
   runs tests/type checks and task-specific acceptance checks, examines failures
   and repairs them in its own tool loop. It self-reviews the full diff and how
   changed components fit together. It must not weaken tests or move the goalposts.
3. **No routine handbacks.** Flash does not stop after a patch, ask the parent to
   run ordinary checks, or return the first failing test. It continues until the
   assigned implementation and accessible acceptance checks pass. A completion
   report with exact evidence is delivery of finished work, not an escalation.
   While unfinished, it returns only for a concrete inability to finish: an
   unresolved permission/external dependency, a plan contradiction needing the
   parent's decision, or repeated failed hypotheses with no credible next step.
4. **Parent reviews finished work.** Inspect the actual diff and reported checks,
   verify material acceptance risks and retain required independent review. Send
   concrete review corrections back to the same Flash worker, which owns fixing
   and retesting them. Do not take routine implementation chores back just because
   a first draft needs correction, and do not replay every passing check.
5. **Real failure returns directly to the parent.** Flash supplies a concise
   handoff: attempts, evidence, exact failures, current diff, tests run and the
   remaining blocker. The parent reads the diff and takes over when Flash cannot
   finish, subject to the host rescue override. Never route through Pro. A provider
   or harness fault is not model failure: repair it and resume the same session.
6. **Parent finishes release work.** Perform restricted verification, required
   approvals, push/merge/deploy and live checks under the task's existing rules.
   Record accepted corrections in the shared brief. Do not equate local worker
   completion with a deployed, live-verified feature.

The wrapper serialises writers in one checkout. Do not run another coding agent
there concurrently. It does not protect against unrelated processes editing files.
Local commits are permitted only within the task's scope; push, merge, deploy,
account actions, credentials and production/data access remain with the parent
under the existing authorisation rules. Never relax provider or sandbox controls
merely to get a passing result.

## Visible transitions

Before starting, retrying, restarting or escalating, post a standalone bold banner
and one sentence with the reason and known cost, or `unknown`:

- `**--- Starting with Flash ---**`
- `**--- Continuing with Flash ---**`
- `**--- Retrying Flash ---**` for a justified correction
- `**--- Restarting with Flash ---**` after a harness repair
- `**--- Escalation to <originating parent model> ---**`

If the parent's model is unavailable, name the originating parent instead of
inventing a slug. Do not wake the parent for each worker tool call. Surface a real
blocker, escalation or returned result; do not generate commentary-only model calls.

## Context and measurement

OpenCode retains the worker's tools and conversation and compacts when needed.
Archives remain intact. Keep a short authoritative brief of decisions, rejected
approaches and review corrections. Fold old shared notes into it when useful.
Compact the parent's context too: persistence must not mean replaying an ever-growing
launch history. Do not restart workers simply to save the parent context.

The adapter records actual OpenRouter usage for all requests, including automatic
compaction. It does not substitute OpenCode's estimated prices for billed API cost.
Unknown cost/tokens remain unknown. Worker tool logs and parent acceptance are separate.
Use stable failure tags when recording repeated mistakes. Measure elapsed time to
acceptance and total available cost/tokens, including parent work when the host
provides it. Do not claim savings from cheap worker tokens alone.

Do not impose arbitrary dollar cutoffs on coding workers. Track actual spend and let the worker finish its implementation and checks. Stop for a real failure loop, a user-set spending limit or an unresolved safety boundary. Benchmarking alone is not a reason to add `--budget`. A separately authorised paid application canary may still have its own cap; it does not cap the coding agent.

No extra LLM graders, dashboards or benchmark reruns just to fill counters. Inspect
metrics at PR completion or when asked. Preserve required independent review.
Flash uses `reasoning.effort: "max"` by default, including SDK helper calls. Verify
the live model supports max; do not silently downgrade it. Every wire request receives the
approved endpoint's live output allowance, adjusted for input context, so harness
SDK defaults cannot impose a hidden fixed token cap. Provider limits still exist.

### Comparing routing policies when requested

Freeze the old run's journal, revision, task and acceptance results before starting
the new route. Record the new route, chosen model and starting revision in a note.
Use the same correctness checks and fixed evaluation sample; count failures,
unknown results and parent repairs. Never improve the denominator or weaken checks.
Compare cost per accepted task, fresh and cached input, output tokens, failed calls,
corrective runs, review defects and elapsed time to acceptance. Include available
parent and reviewer usage; mark missing attribution or dollar cost unknown. Separate
provider/harness faults and downtime from coding quality, but retain their costs.
A cheaper run with worse accepted quality is a regression, not a win.

A before-and-after trial has learning and task-difficulty confounders. Say so. Do not
claim causal savings from it or rerun a known fix as a fresh benchmark. Prefer normal
work and passive logs. If a controlled replay is explicitly requested, freeze the
same starting source, brief and checks in isolated checkouts, preserve all histories,
and agree a small spend limit before running it. No extra model graders or broad
benchmark framework. Report improvement, regression or inconclusive with evidence.

## Provider reliability and pending decisions

Each upstream request also appends passive counters to
`~/.local/share/triple-escalator/provider-reliability/requests.csv`.
Run `python3 "$SKILL/scripts/provider_health.py"` for request success, rate-limit
counts, latency and known costs by endpoint. Unknown billing stays unknown. The log
contains no prompts, source, response bodies or credentials and makes no extra API
calls. `--import-session PATH` imports an existing journal without inflating reports
when repeated. API reliability is separate from code quality and task acceptance.
For repeated provider failures, try another already approved compatible endpoint
with the same model and native session before treating this as a model failure.

When a user decision is outstanding, announce **Your input is needed** separately
from routine progress. State the blocked action and continue only independent work.
Include unresolved decisions in the final status. Silence is never approval.
