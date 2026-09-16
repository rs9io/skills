---
name: triple-escalator
description: >-
  Delegate implementation to a persistent Pro coding agent, or Flash for a
  parent-selected mechanical task. Workers return directly to the originating
  parent for review and rescue. Use for triple escalator or double escalation.
metadata:
  version: "0.9.1"
---

# Triple Escalator

The originating parent plans, selects a worker, reviews and rescues.
**Pro is the default coding worker.** The parent may choose Flash up front for
small mechanical work with clear checks, such as a prescribed rename or a repetitive
edit with no unresolved design. Use Pro for debugging, uncertain requirements,
cross-file changes and correctness-sensitive implementation. If unsure, choose Pro.
Both are full coding agents with file, terminal, test and repair tools.

**Routes: parent → Pro → parent, or parent → Flash → parent.** There is no
Flash → Pro ladder. Neither worker delegates, chooses a replacement model or
hands work to the other. If the chosen worker cannot finish, the parent takes over
(subject to the host rescue override). Do not manufacture a new task to pass the
same failed implementation to the other worker. Flash remains available as an
explicit choice, never as a compulsory cheap first attempt.

The name and installation path `triple-escalator` remain for compatibility.
Existing worker histories stay intact; no rename, duplicate skill or session reset
is needed. This policy supersedes older Flash-first instructions in saved briefs.

Resolve `SKILL` to this loaded skill's absolute directory. Read
[worker commands](references/sessions.md) for setup and execution, and
[provider policy](references/provider-policy.md) before external calls.

## Execution and continuity

Use `scripts/cascade_agent.py`, which runs OpenCode's coding tool loop against
OpenRouter. **The old `cascade_run.py`/`cascade_apply.py` patch path is a legacy
protocol diagnostic, not the implementation workflow.** Do not silently fall back
to patch generation or parent-driven shell relays if the coding harness is broken.

- One persistent generalist for the selected model per PR/workstream. Reuse its
  native session ID through assignments, feedback and host restarts. Start Pro
  directly by default; no failed Flash run is required.
- Keep an existing Flash session idle when choosing Pro for new independent work.
  Do not initialise both models merely because both are available.
- An optional second generalist Flash needs independent scope and a separate
  checkout/session directory. No specialist swarm or nested model delegation.
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

1. **Parent plans and routes.** Define the outcome, boundaries, settled decisions
   and acceptance checks. Select Pro by default; record one sentence if choosing
   Flash. Create/reuse the PR session. Restricted actions stay with the parent.
2. **Worker executes.** Give the selected worker the task and checkout pointers.
   It reads source, implements, runs checks and repairs failures in its own tool
   loop. The parent does not ferry source, patches or routine commands.
3. **Worker returns to the parent.** Report actual changes, exact check results,
   remaining failures and decisions needing judgement. Save native session identity,
   tool evidence and API usage. `returned` is not acceptance. Never hand off to or
   recommend automatically invoking the other external worker.
4. **Parent judges.** Read the actual diff, including committed and untracked work,
   and execution evidence. Independently verify material acceptance risks. Keep
   required independent review. Do not repeat every already-passing check.
5. **One justified correction or parent rescue.** A run may contain many tool and
   repair steps. Allow at most one corrective run with the same worker when there
   is a concrete new hypothesis. Repeated identical failure, a second failed run
   or poor economics goes directly to the originating parent, not the other worker.
   A provider, harness or permission fault is not model failure: repair the cause
   and resume the same session without bypassing controls.
6. **Parent finishes.** Read the failure report and diff, retain valid work and
   repair the remaining issue directly, subject to the host rescue override.
   Record accepted corrections in the shared brief before the worker's next task.

The wrapper serialises writers in one checkout. Do not run another coding agent
there concurrently. It does not protect against unrelated processes editing files.
Local commits are permitted only within the task's scope; push, merge, deploy,
account actions, credentials and production/data access remain with the parent
under the existing authorisation rules. Never relax provider or sandbox controls
merely to get a passing result.

## Visible transitions

Before starting, retrying, restarting or escalating, post a standalone bold banner
and one sentence with the reason and known cost, or `unknown`:

- `**--- Starting with Pro ---**` (default) or `**--- Starting with Flash ---**`
- `**--- Continuing with Pro ---**` or `**--- Continuing with Flash ---**`
- `**--- Retrying Flash ---**` or `**--- Retrying Pro ---**`
- `**--- Restarting with Pro ---**` or `**--- Restarting with Flash ---**` after a harness repair
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
Both external workers use high reasoning by default. Every wire request receives the
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
