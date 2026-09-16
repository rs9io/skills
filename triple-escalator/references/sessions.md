# Coding workers: setup and commands

Version 1.1 uses one persistent Flash coding worker at max reasoning. The parent
writes a plan that covers component interactions and acceptance. Flash implements,
self-reviews, tests and repairs the work before returning a completion report.
Unfinished work returns only for a concrete blocker or inability to finish.

## Setup (macOS)

Requires Python 3.10+, Git, npm and macOS `sandbox-exec`. Install the pinned harness:

```sh
npm install --prefix "$HOME/.local/share/triple-escalator/runtime" --save-exact opencode-ai@1.18.31
```

Install the native request counter in an isolated Python environment, then activate
that environment whenever running the Python helpers:

```sh
python3 -m venv "$HOME/.local/share/triple-escalator/tokenizer-runtime"
source "$HOME/.local/share/triple-escalator/tokenizer-runtime/bin/activate"
python3 -m pip install deepseek-recipe==0.1.1
python3 "$SKILL/scripts/cascade_tokens.py" --setup
```

Setup downloads checksum-pinned official Flash and Pro tokenizers. Request counting
is local and includes chat framing, tool definitions and results. It uses the native
template, rather than treating bytes as tokens or assuming a characters-per-token
ratio. Provider-specific framing may differ; billed usage still comes only from
the API. Unsupported input fails before sending. No worker history is discarded.

The installed binary is checked before each run. Credentials remain in the parent
process via `OPENROUTER_API_KEY`; public installations use environment-based keys.
Configure approved providers in `providers.json` or `OPENROUTER_PROVIDER_CONFIG`.
No API key is copied into the child process or its config. Its only provider route
is a temporary authenticated loopback adapter owned by the runner.

The adapter verifies the live provider catalogue and enforces pinned routing,
`data_collection: deny`, ZDR, max reasoning for Flash and the full usable output allowance
on every request, including harness helper calls. Other models are refused.

## Start a PR session

Keep the session directory outside the checkout and retain its path in the parent's
progress record. Use a task-specific path, not a new directory per turn.

```sh
python3 "$SKILL/scripts/cascade_session.py" init /private/path/pr-session \
  --repo /path/to/worktree --parent original-conversation-reference \
  --parent-model inherit --file /private/path/parent-plan.md
python3 "$SKILL/scripts/cascade_agent.py" flash /private/path/task.md \
  --session /private/path/pr-session --task issue-123
```

The task contains the goal, relevant pointers, scope and checks. Do not paste every
source file or instruct the parent to apply the worker's edits. Workers read current
source, discover repository instructions, edit and test themselves. The runner emits status on stderr immediately and every 30 seconds, and
prints a report with the persistent native session ID, log path, before/after
revision and actual API cost. Native transcripts live under `session/coding/data`;
per-run command/tool events and reports live under `session/coding/<run-id>`.

A run may inspect, edit, fail tests, fix and retest without a parent turn between
steps. A permission denial must be reported as a boundary, not worked around.
The process has no general outbound network: install dependencies with the parent
before dispatch. `--read-dir /specific/dependency/directory` adds an approved
read-only path for existing dependencies outside the checkout. It does not grant
network access. Local servers may listen; external browsing remains a parent task.

Reuse one Flash worker for the workstream. Do not initialise a second worker or
invoke a retained Pro session. Historical sessions remain available for audit.

## Review, resume and return to the parent

Inspect the actual diff (including committed changes since the task baseline),
relevant tool output and result. `returned` is not a pass verdict. Record parent
acceptance or a concrete failure:

```sh
python3 "$SKILL/scripts/cascade_session.py" parent-check /private/path/pr-session \
  --task issue-123 --result fail --failure-tag wrong-pack-basis \
  --detail 'Observed regression: six-pack price treated as single bottle'
python3 "$SKILL/scripts/cascade_agent.py" flash /private/path/feedback.md \
  --session /private/path/pr-session --task issue-123
```

The second command resumes the same native session. Never use `--fork` or wipe
history to retry. If a run was interrupted, inspect its logs and working tree before
resuming; don't assume its edits rolled back. Only a successfully recorded native
binding may be resumed automatically; investigate any interrupted first-run binding.

When the selected worker cannot finish, announce return to the originating parent
(or configured host rescue), then assemble the evidence:

```sh
python3 "$SKILL/scripts/cascade_session.py" handoff /private/path/pr-session \
  --task issue-123 > /private/path/handoff.json
```

`handoff` exports unfinished-work evidence to the parent; it never launches another
worker. Failure returns directly to the originating parent, never through Pro.
Review corrections go to the same Flash session for implementation and retesting.
The report excludes committed changes from its HEAD diff and does not include
untracked file contents; inspect those separately.

After an accepted worker or parent fix, send accepted corrections back to the workers:

```sh
python3 "$SKILL/scripts/cascade_session.py" note /private/path/pr-session \
  --file /private/path/accepted-correction.md
python3 "$SKILL/scripts/cascade_session.py" brief /private/path/pr-session \
  --file /private/path/current-plan.md --fold-notes
```

Use the second command when the brief incorporates older notes. It stops replaying
those notes without deleting them. Native OpenCode compaction manages tool history;
the legacy `compact` command only affects v0.7 patch conversations.

## Finish and measure

```sh
python3 "$SKILL/scripts/cascade_session.py" parent-check /private/path/pr-session \
  --task issue-123 --result pass --detail 'Acceptance checked against current diff'
python3 "$SKILL/scripts/cascade_session.py" summary /private/path/pr-session
python3 "$SKILL/scripts/cascade_session.py" close /private/path/pr-session \
  --detail 'PR merged and acceptance verified'
```

A worker has a one-hour wall-time stop by default (`--timeout` changes seconds); its
history remains available for resume. This is not a token limit.

Omit `--budget` for ordinary coding work and routing benchmarks. Do not add a small
arbitrary cutoff that interrupts implementation or checks. The optional `--budget`
exists for an explicit user-set worker spending limit. It stops between requests
once known cost reaches that amount or billing is unknown; an in-flight request
can exceed it. It never reduces token output allowance. Monitor spend and stop
actual failure loops instead of forcing repeated budget pauses.

Close preserves every transcript and prevents new dispatches. There is no idle
worker process or paid background polling. A running call must be supervised by its
parent; don't end the parent task while it is still running without a resume path.

## Legacy path

`cascade_run.py` and `cascade_apply.py` remain for old evidence and explicit protocol
diagnostics. They are not full coding agents. Do not use them for application work.

## Codex supervisor

Use the host native agent tool for a bounded lifecycle task while the parent does
independent work. Give the supervisor the exact existing session, task file,
provider and run command. It may launch the runner once, or attach to the known
process, then wait for its report and return that report. It does not implement,
review or fork the Flash conversation. Persist the supervisor ID and exec/run IDs
in the resume note. On every resume inspect the actual process and report first.
Use `status.json` for display only; verify a stale running status against its PID
and exact command, and distinguish completion from unexpected process death.

If returning to the user before completion, use the supported thread heartbeat
so this same parent resumes without a user message. Inspect existing automations
before creating one, avoid duplicates, stay quiet while unchanged, and pause the
heartbeat when its completion has been handled. A native child return alone must
not be described as a guaranteed wake-up after the parent turn has ended.
