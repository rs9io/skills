# Triple Escalator

A skill for Codex, Claude Code and Cursor that keeps one coding worker on a workstream until its implementation is finished.

**Route: parent → DeepSeek Flash at max reasoning → parent.**

The parent invests in a clear implementation plan: how the components fit together,
what must stay true, and what evidence proves the job works. One persistent Flash
coding agent reads and edits source, runs terminal commands, self-reviews its diff,
and fixes its tests and acceptance checks. It handles the whole implementation,
including debugging and integration, without handing routine chores back.

Flash delivers a completion report when the assigned work passes. It returns
unfinished work only when it cannot finish or needs a decision/access outside its
scope. The parent reviews the result, handles release boundaries and rescues real
failures. Pro is outside the active route. Reuse the same Flash session for feedback
and later assignments; saved context is not training. Idle sessions make no calls.
Version 1.0 preserves existing installation paths and all worker histories.

Codex and Claude return to their originating conversation and host-selected model.
A configured host rescue override remains valid, such as Fable in Cursor. No extra
frontier API call is made by this runner.

## What you will see

Before starting, resuming or escalating, the parent posts a standalone bold banner
and one sentence with the reason and recorded cost, or `unknown`:

**--- Continuing with Flash ---**

The same worker is implementing the agreed plan at max reasoning; recorded cost $0.12.

**--- Escalation to the originating parent ---**

Flash cannot complete the acceptance check after testing its remaining hypotheses;
it returns the current diff, failed checks and blocker. Recorded cost $0.42.

Harness faults are repaired and the same worker resumes. Workers never delegate.

## Why it can save money

Implementation and failed attempts move to cheaper external models. Your main model still spends tokens understanding the task, writing prompts and checking results, and it handles difficult rescues. Total tokens can increase because of retries. The aim is fewer expensive model tokens and lower overall cost, not a guaranteed saving on every task.

## Install

Requires macOS, Python 3.10 or later, Git, npm, a coding agent that supports SKILL.md, and your own funded OpenRouter account. The runner uses deepseek-recipe 0.1.1 for local native token counting. The coding harness is pinned to OpenCode 1.18.31; the macOS execution boundary must be available. Other operating systems currently fail closed.

Download this repository. From its root, copy `triple-escalator` into your agent's skills directory. For Codex:

```sh
mkdir -p ~/.codex/skills
cp -R ./triple-escalator ~/.codex/skills/triple-escalator
```

For Claude Code use `~/.claude/skills/triple-escalator`; for Cursor use `~/.cursor/skills/triple-escalator`. Keep independent copies where host policies differ.

If that destination already exists, move your old copy aside first. Install in one discovery location only; a second link in `~/.agents/skills` can produce a duplicate skill entry. Reopen the agent's skill picker or start a new chat to refresh discovery.

Install the tested coding harness:

```sh
npm install --prefix "$HOME/.local/share/triple-escalator/runtime" --save-exact opencode-ai@1.18.31
```

Install and activate the local native token counter using [session setup](references/sessions.md#setup-macos) before running the Python helpers. It counts chat and tools locally and does not make paid calls.

### 1. Supply your own API key

Create a key at [OpenRouter API keys](https://openrouter.ai/settings/keys). Give it a spending limit appropriate to your test budget.

Set `OPENROUTER_API_KEY` through your coding tool's secret configuration, or in the environment it inherits:

```sh
export OPENROUTER_API_KEY="YOUR_OWN_OPENROUTER_KEY"
```

Do not commit the key. An export in one terminal does not automatically reach an already-running desktop app. Ensure the agent's shell actually inherits the variable. This package does not read another application's private configuration or bundle somebody else's key.

### 2. Set your allowed and blocked providers

Copy the blank configuration:

```sh
cp ~/.codex/skills/triple-escalator/providers.example.json \
   ~/.codex/skills/triple-escalator/providers.json
```

Edit `providers.json`. `only` is your **allowlist**. `ignore` is your **blocklist**, sometimes called blocked or ignored providers. Use actual OpenRouter provider or endpoint slugs after reviewing the providers that serve your chosen models:

```json
{
  "only": ["REPLACE_WITH_AN_APPROVED_PROVIDER_SLUG"],
  "ignore": ["REPLACE_WITH_A_BLOCKED_PROVIDER_SLUG"]
}
```

Those are placeholders, not working provider names. The bundled `only` list starts empty and the runner refuses to send a request until you configure it. `ignore` may be empty because `only` already limits eligible providers. You can also configure ignored providers in [OpenRouter settings](https://openrouter.ai/settings/preferences).

The runner adds `data_collection: "deny"` and `zdr: true` on every request. Each call is pinned to an approved endpoint; automatic fallback is disabled so the output allowance cannot silently shrink. If no allowed endpoint satisfies these settings, the worker call fails; the agent must not relax your rules to make it work. Model availability and provider support can change, so check the current model pages before use:

- [DeepSeek V4.1 Flash](https://openrouter.ai/deepseek/deepseek-v4.1-flash)
- [DeepSeek V4 Pro](https://openrouter.ai/deepseek/deepseek-v4-pro)

For a config stored outside the installed skill, set `OPENROUTER_PROVIDER_CONFIG` to its absolute path.

### 3. Use it

Ask your coding agent:

> Use triple-escalator to fix this issue. Write a clear implementation plan covering component interactions and acceptance. Keep one persistent Flash worker at max reasoning to implement, self-review, test and repair it. It returns unfinished work only if it cannot finish. Preserve my edits and report checks and total available cost.

The parent creates one session directory **outside the repository**, records its path, and resumes it for later tasks. Use `cascade_agent.py flash task.md --session /private/path/pr-session --task issue-123`. It restores the same native worker, which executes the work itself. The old patch runner is reserved for legacy diagnostics. Follow [session commands](references/sessions.md) for initialisation, feedback, handovers and compaction. Closing a session preserves its journal.

Start with a small task and inspect the diff and results. Irreversible actions, payment or credential work, restricted data, and tasks without a reliable done-check stay in the calling chat, subject to your usual approvals.

## Measurements without extra model calls

Each request records API-reported input/output tokens and cost. Existing checks supply pass/fail results and short failure tags. A local summary counts repeated mistakes and elapsed time from the first external request to the first passing check for each task. Reasoning tokens are not counted twice. Missing usage stays unknown; parent-chat usage is separate and is not measured by this runner.

When comparing policies, freeze the baseline before switching routes and retain the same acceptance checks and fixed samples. Include parent repairs and reviewer work where measurable; cached input, fresh input and output are separate counters. Missing billing stays unknown. Report learning, task differences and downtime as confounders; a before-and-after trial does not prove causal savings. Do not rerun a solved task just to claim an easy win.

Read the summary at PR completion or when requested. There are no model graders, benchmark reruns or dashboards. These counters make comparison possible; they do not prove savings by themselves. Long histories also cost input tokens, so the parent can write a concise checkpoint while the original journal remains intact.

## Output and reasoning

The runner reads the selected endpoint's live output capacity and explicitly
requests that allowance, reserving context space for the prompt. It adds no
fixed application token cap. Reasoning counts towards that allowance.
Flash selects the approved `morph/fp8` endpoint by default. The runner checks live
availability and limits before calling it. Flash defaults to `reasoning.effort: "max"`
in both the harness config and wire adapter. Do not silently downgrade it. Legacy
Pro support remains for retained histories and explicitly requested diagnostics;
it is not part of the active coding workflow.

Omit `--budget` for normal coding work. Do not interrupt implementation or tests
with arbitrary small dollar caps. Record costs and investigate genuine failure
loops. An explicit user-set spending limit is still binding; paid application
canary limits are separate from the worker's implementation loop.
See [OpenRouter's reasoning-token documentation](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

The adapter rejects truncated or empty replies. The worker may already have edited files before a later request fails, so inspect its actual diff and tool logs before resuming. Nothing silently rolls back valid work. A returned worker report is not acceptance; the parent checks the result against the agreed criteria.

## Data sovereignty

A provider allowlist is a routing control. A company's country of ownership does not prove where a particular endpoint processes data. Retention rules and processing location are separate questions. Verify the endpoint, region, subprocessors and contractual terms against your actual requirements. Where strict regional processing is required, use a verified in-region service and configuration; do not infer it from a provider name. See [OpenRouter's sovereign routing documentation](https://openrouter.ai/docs/guides/features/sovereign-ai).

OpenRouter documents separate [provider-routing controls](https://openrouter.ai/docs/guides/routing/provider-selection) and [zero-data-retention policies](https://openrouter.ai/docs/guides/features/zdr). ZDR does not mean the data stays on your machine, and OpenRouter permits some in-memory caching within its definition. Review OpenRouter's own privacy settings as well as the downstream provider's terms.

Keep credentials, customer records, proprietary pricing and other restricted material out of delegated prompts unless the chosen service and workflow are approved for it. The runner sends the worker conversation, including source and command output the worker reads inside its allowed checkout; it is not a sensitive-data scanner. The calling chat is also a hosted service with its own policies.

## Verify the package locally

```sh
python3 -m unittest discover -s triple-escalator/tests -v
```

The tests use local fixtures, mocked HTTP calls and a real local sandbox check. They do not spend API credit. The native harness preserves its conversation and tool history; the parent journal links each result and records actual API usage. Worker tool output and parent acceptance remain distinct.

The OS boundary permits checkout/runtime writes and approved read-only tools and dependencies. It blocks general outbound network, access to unrelated home files, common credential filenames and signalling unrelated processes. The child gets no inherited API/cloud secrets. Repository contents and explicitly allowed dependencies must still be suitable for the approved provider; the boundary is not a secret scanner. Local Git commits are in scope when the parent asks for them; changes to Git hooks/config are blocked.

A live disposable-repo trial verified Flash reading a broken program, running the failing baseline, editing it and passing tests; a follow-up resumed the same worker. Pro independently read, edited and ran tests through its own persistent session. These checks establish the execution path, not a cost or quality advantage on every production task.

The public bundle uses user-configured providers and environment-based credentials. It contains no private account configuration.
