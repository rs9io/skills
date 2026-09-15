---
name: triple-escalator
description: >-
  Runs a cheap-first coding cascade: DeepSeek Flash on OpenRouter,
  then DeepSeek Pro on OpenRouter if Flash fails, then direct rescue by
  the model in the calling chat if both fail. Use when the user says
  "triple escalator", "use the cascade on X", or asks for delegated coding
  work through this cascade. No manual prompt courier or separate final-model API call.
---

# Triple Escalator for Codex

The calling chat coordinates and judges. Flash does the heavy lifting, Pro
handles failures, and the calling chat's current model performs the final
rescue directly. If the caller is Astra, Astra rescues. If the caller uses a
different model, that model rescues. Never hardcode a frontier model.

Read [provider-policy.md](references/provider-policy.md) before sending any
prompt externally. The runner requires the user's own explicit provider allowlist and applies
blocked-provider, no-data-collection and zero-retention routing controls.
Install and configure it using the repository README before running a rung.

## Rungs

| Rung | Model | Execution |
|---|---|---|
| 1 | DeepSeek V4.1 Flash | OpenRouter: `deepseek/deepseek-v4.1-flash` |
| 2 | DeepSeek V4 Pro | OpenRouter: `deepseek/deepseek-v4-pro`, after Flash fails |
| 3 | Current model in the calling chat | Direct work in that chat, after both external rungs fail |

Start with Flash for both small and multi-file tasks. Do not skip to Pro just
because a task is large. Check the live OpenRouter catalogue before running;
if a configured model is unavailable, record that rung as unavailable and move
on. Do not invent a replacement slug or weaken provider restrictions.

One attempt per external rung. One prompt-fixed retry is allowed on that rung
only when a failure taught something specific. Never a third attempt on a rung.
After Pro fails, continue in the calling chat without asking the user to courier
anything or approve an already authorised fix.

## Coordinator discipline

While this skill is executing delegated application work, the coordinator
writes prompts, runs the runner and patch applier, runs checks, and judges.
Application source edits go through the external rungs until both have failed.
Do not quietly patch a failed external answer to avoid recording an escalation.
At rung three, the calling chat may edit source directly to finish the task.

This restriction governs work delegated through the skill. Editing or installing
the skill itself does not require invoking its own cascade recursively.

Do not spawn a separate expensive coordinator or rescue model. There is no
Cursor spend-pool dependency and no requirement for a Codex API credential.
If a background agent invokes the skill on behalf of a parent chat, it returns
its failure evidence to that parent. The parent chat's current model performs
the rescue; the background agent does not choose or launch a replacement.

## Workflow

1. **Done-check first.** Define a runnable check appropriate to the requested
   outcome. UI work includes rendered interaction checks. Checks supplement
   focused inspection of the changed behaviour; a green test alone is not proof
   that the entire request is complete.
2. **Baseline.** Run the check before any rung edits. If already failing,
   separate the existing failure from the requested work. Do not judge a rung
   against an unexplained broken baseline; use the calling chat to resolve it.
3. **Snapshot.** Record the targeted files and their contents, including any
   existing user changes and which paths did not exist. Restore only this run's
   changes between rungs. Never reset unrelated work or delete agent history.
4. **Prompt.** Write a self-contained prompt file with the scope, relevant
   source, exact signatures, insertion anchors, constraints and done-check.
   Exclude credentials and restricted data. Require only the strict
   FILE/FIND/REPLACE WITH edit format accepted by `cascade_apply.py`.
5. **Run Flash, then Pro if needed:**

   ```sh
   python3 ~/.codex/skills/triple-escalator/scripts/cascade_run.py <model-slug> <prompt-file> <reply-file>
   python3 ~/.codex/skills/triple-escalator/scripts/cascade_apply.py <repo-root> <reply-file>
   ```

   The runner prints provider, cost, tokens and finish reason. API failures,
   incomplete output, invalid edits and failed done-checks are rung evidence.
   The applier validates all edit blocks before writing. Restore the snapshot
   after a failed check before retrying or escalating. Keep edits within scope.
6. **Judge.** Ship, retry with the newly learned detail, or escalate. Keep one
   concise progress line per rung. Read focused failures and changed sections,
   not entire transcripts. Preserve any required independent review and release checks.
7. **Rescue in the calling chat.** Restore the snapshot, retain the useful
   failure findings, and have the current chat model implement and verify the
   fix directly. Do not call OpenRouter, the OpenAI/Codex API, Cursor API, or a
   hardcoded Fable/Astra subagent for rung three. Do not recursively invoke this
   skill for the rescue or stop at a handoff report when the caller can continue.
8. **Report.** State rungs used, recorded OpenRouter cost per rung and final
   verification. Report unknown cost as unknown. Rung three uses the existing
   chat's normal usage, not a separate external inference charge. Mention the
   OpenRouter balance if below $5, using `GET https://openrouter.ai/api/v1/credits`.

## Work that stays in the calling chat

Keep irreversible actions, security/credential/payment work, restricted data,
and tasks without a reliable done-check in the calling chat from the start.
Explain the reason briefly. This exception does not permit a separate frontier
API call and does not override the user's existing approval boundaries.

## Files

- `scripts/cascade_run.py`: only the two DeepSeek rungs, through OpenRouter.
- `scripts/cascade_apply.py`: strict single-match source edits.
- `references/provider-policy.md`: the local copy of external-routing and data rules.

## Output limits and truncated replies

The runner does not send a token cap. The provider's own defaults and model
limits still apply, and reasoning shares the completion allowance with the
answer. Flash explicitly uses low reasoning; Pro uses its supported high level.
Use `--reasoning-effort high` when the task justifies more reasoning. Check
supported efforts in the live model catalogue before changing this setting.

`finish_reason: length`, empty content and invalid edit format return a nonzero
exit code. The usable reply path is written only for a complete, correctly shaped
answer. A `.meta.json` sidecar records cost, token counts, provider and finish
reason; partial text is kept separately as `.partial.txt` and must not be applied.
A complete answer still has to pass the edit helper and the task's done-check.
Never apply a stale output after a failed command. Use a fresh output path for
each attempt. A justified settings retry counts toward the one-retry-per-rung
limit; it does not restart the cascade indefinitely. If the provider still
truncates an answer, split the work into smaller changes or escalate.
