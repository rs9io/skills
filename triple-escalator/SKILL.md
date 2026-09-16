---
name: triple-escalator
description: >-
  Delegate implementation to persistent Flash and Pro coding agents with file,
  terminal and test tools. The originating parent plans, reviews and rescues.
  Use when asked for triple escalator or the cheap-first coding cascade.
metadata:
  version: "0.8.2"
---

# Triple Escalator

The originating parent owns the problem, plan, acceptance criteria and final review.
**Flash is a full coding worker:** it explores the repo, reads source, edits files,
runs commands and tests, diagnoses failures and repairs its work. Pro takes over
when Flash cannot finish. The parent must not become a courier for file contents,
patches, individual commands or routine test failures.

Resolve `SKILL` to this loaded skill's absolute directory. Read
[worker commands](references/sessions.md) for setup and execution, and
[provider policy](references/provider-policy.md) before external calls.

## Execution and continuity

Use `scripts/cascade_agent.py`, which runs OpenCode's coding tool loop against
OpenRouter. **The old `cascade_run.py`/`cascade_apply.py` patch path is a legacy
protocol diagnostic, not the implementation workflow.** Do not silently fall back
to patch generation or parent-driven shell relays if the coding harness is broken.

- One persistent generalist Flash per PR/workstream. Reuse its native session ID
  through assignments, review feedback and host restarts.
- Start one persistent Pro only when escalation is warranted, then reuse it.
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

1. **Parent plans.** Define the outcome, boundaries, relevant settled decisions and
   acceptance checks. Create/reuse the PR session. Identify restricted operations
   that stay with the parent. Do not make the worker invent the product plan.
2. **Worker executes.** Give Flash the task and file/worktree pointers. Let it run
   the baseline, inspect source, implement, test and repair autonomously. Ordinary
   failing tests belong inside its tool loop, not in a new parent conversation turn.
3. **Worker returns evidence.** Its report names the actual changes, commands,
   results, remaining problems and decisions it could not settle. The runner saves
   tool output, native session identity and actual API usage. `returned` means the
   run ended, not that the task passed or is accepted.
4. **Parent judges.** Read the actual diff, including committed and untracked work,
   and the relevant execution evidence. Independently test the acceptance risks
   that warrant review. Do not rerun every routine check just to repeat the worker.
   A report saying "all green" is not acceptance; use observed results.
5. **Retry or escalate.** A bounded worker run can contain many tool/test/fix steps.
   Allow one run and one justified corrective run per rung for the same task.
   Stop repeated identical failures without a new hypothesis. A blocked permission,
   missing input or harness fault is not proof of model failure and must not be
   bypassed by changing model. Fix infrastructure and resume the same Flash session.
6. **Pro takes over the work.** Before escalation, the parent reads the current diff
   and failure evidence. Give Pro the goal, attempted fixes, rejected approaches,
   valid edits to retain and exact remaining failures. Pro then uses its own tools
   to continue in that checkout. Do not reset valid work or erase unrelated edits.
7. **Parent rescue last.** If Pro fails, the original parent reads the handover and
   finishes directly, subject to the host override. Send accepted Pro/parent
   corrections back into the shared brief/notes before Flash's next assignment.

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
- `**--- Retrying Flash ---**` or `**--- Retrying Pro ---**`
- `**--- Restarting with Flash ---**` after a harness repair
- `**--- Escalation to Pro ---**`
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

No extra LLM graders, dashboards or benchmark reruns just to fill counters. Inspect
metrics at PR completion or when asked. Preserve required independent review.
Both external rungs use high reasoning by default. Every wire request receives the
approved endpoint's live output allowance, adjusted for input context, so harness
SDK defaults cannot impose a hidden fixed token cap. Provider limits still exist.

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
