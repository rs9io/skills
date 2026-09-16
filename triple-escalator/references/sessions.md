# Persistent session commands

All paths below are examples. Set `SKILL` to this installed skill's absolute directory
and `SESSION` to a new directory outside the repository, such as
`~/.local/state/triple-escalator/project-pr-123`. Reuse it until the PR is done.
Python 3.10+ and a POSIX host (macOS/Linux) are required. No daemon or database.

The journal contains only briefs/prompts/results you intentionally send and local
check observations. It never reads or exports your root chat automatically. Apply
the same data policy to later notes and checkpoints as to the first prompt.

```sh
python3 "$SKILL/scripts/cascade_session.py" init "$SESSION" \
  --repo /absolute/checkout --parent ORIGINAL_CONVERSATION_REFERENCE \
  --parent-model inherit --file /tmp/approved-brief.txt
```

Use an observed model identity instead of `inherit` when available. It is metadata,
not a model-routing slug. Add `--second-worker` only when a second generalist is
justified. The workers are `flash`, optional `flash-2`, and lazy `pro`.

```sh
python3 "$SKILL/scripts/cascade_run.py" deepseek/deepseek-v4.1-flash \
  /tmp/task.txt "$SESSION/reply-001.txt" --session "$SESSION" --task issue-123
python3 "$SKILL/scripts/cascade_apply.py" /absolute/checkout "$SESSION/reply-001.txt"
```

The next assignment or retry uses the same session and worker, with a fresh reply
filename. Keep the same task ID across retries/escalation. Use a new task ID for a
new bounded task within this PR. Pro uses its model slug and `--worker pro`.

Read `attempt_id` from the reply's `.meta.json`, inspect the diff, then run the checks
in the repository. Record their actual result, including failed application:

```sh
python3 "$SKILL/scripts/cascade_session.py" check "$SESSION" \
  --attempt ATTEMPT_ID --result fail --failure-tag schema-v1 \
  --detail 'Schema v1 returned despite the schema v2 decision; migration test failed.'
```

For success use `--result pass` and omit the failure tag. Tags are parent-assigned
identifiers for the same observed mistake, not an LLM's opinion. Only one check
record is allowed per external attempt, preventing accidental double counting.
Record the combined acceptance verdict once; individual test logs stay in their
normal files. For parent rescue, use `parent-check --task ... --result ... --detail ...`.
It contributes passing-check time but invents no parent token count or API spend.

Share a correction with both workers:

```sh
python3 "$SKILL/scripts/cascade_session.py" note "$SESSION" --file /tmp/correction.txt
```

Before escalation, assemble and read the handover:

```sh
python3 "$SKILL/scripts/cascade_session.py" handoff "$SESSION" \
  --task issue-123 > "$SESSION/handoff-001.json"
```

The helper includes untrusted worker reports, observed checks and the actual HEAD
diff/status. The parent reads the diff and failure logs, adds relevant committed or
untracked changes, and prepares the next task prompt. Use the relevant parts in Pro's
first prompt. Do not repeatedly paste the full handover into shared notes; those
are for concise accepted decisions and corrections.

Replace the current brief when decisions change. To fold accumulated shared notes
into it, use `brief --file /tmp/current-brief.txt --fold-notes` after checking the
brief preserves those decisions. Notes remain in the archive.

```sh
python3 "$SKILL/scripts/cascade_session.py" brief "$SESSION" --file /tmp/current-brief.txt
python3 "$SKILL/scripts/cascade_session.py" compact "$SESSION" \
  --worker flash --file /tmp/parent-approved-checkpoint.txt
```

Compaction is parent-authored, explicit and per worker. It never deletes history.
The next request includes the current brief and checkpoint instead of older worker
messages. Pro retains its own conversation independently.

```sh
python3 "$SKILL/scripts/cascade_session.py" summary "$SESSION"
python3 "$SKILL/scripts/cascade_session.py" close "$SESSION" --detail 'PR merged and verified'
```

Closing refuses new API work while retaining the journal and metrics. Do not delete
session history. Local errors before an API request are not counted as paid calls;
requests with unknown billing are reported as unknown. Times to first pass include
waiting between attempts, not just model computation.

## Worker response

The runner requires this concise header for persistent workers, then passes only
edit blocks to the existing strict applier:

```text
REPORT:
{"attempted":"Used the agreed schema v2","changes":"Updated migration mapping","remaining":["Parent must run the migration tests"]}
EDITS:
FILE: src/example.py
FIND:
old_value
REPLACE WITH:
new_value
```

A blocked worker leaves EDITS empty and explains why in `remaining`. The runner
records its report as a failed attempt, without producing a usable patch. Reports
never count as executed checks. API keys and provider headers are not journalled.
