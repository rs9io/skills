# Triple Escalator

A Codex skill that puts cheaper models to work before spending more of your main chat's tokens.

**DeepSeek Flash on OpenRouter → DeepSeek Pro on OpenRouter → your current chat model.**

Flash handles the implementation. If its result fails the agreed checks, Pro gets a turn. If both fail, the model already running your chat finishes the work directly. There is no separate frontier API call or fixed rescue-model name.

The agent drives the workflow: define a done-check, save the starting files, prompt a rung, apply its proposed edits, verify, and retry or escalate. The Python scripts handle individual API calls and edits. They are not a standalone autonomous service.

## What you will see

Before every model switch, the coordinator posts a **bold, standalone banner** naming the model or rung taking over. Use the exact visible form; for example, escalation to Pro is **--- Escalation to Pro ---**. Immediately underneath, one short sentence gives the specific previous failure reason and the recorded cost, or `unknown`. A runner or configuration fault, such as an accidental token cap, is repaired, announced with **--- Restarting with Flash ---**, and restarted on Flash with the corrected runner instead of jumping to a bigger model. Plain tool output or an end-of-task report is not enough. Nothing should move to the next rung silently.

Example:

**--- Starting with Flash ---**  
Starting Flash. No prior failure; cost so far $0.00.

**--- Escalation to Pro ---**  
Flash failed the done-check; recorded cost $0.12.

**--- Restarting with Flash ---**  
Runner repair fixed an accidental token cap; recorded cost $0.12.

## Why it can save money

Implementation and failed attempts move to cheaper external models. Your main model still spends tokens understanding the task, writing prompts and checking results, and it handles difficult rescues. Total tokens can increase because of retries. The aim is fewer expensive model tokens and lower overall cost, not a guaranteed saving on every task.

## Install

Requires Python 3.10 or later, a coding agent that supports SKILL.md, and your own funded OpenRouter account. No Python packages are required.

Download this repository. From its root, copy `triple-escalator` into your agent's skills directory. For Codex:

```sh
mkdir -p ~/.codex/skills
cp -R ./triple-escalator ~/.codex/skills/triple-escalator
```

If that destination already exists, move your old copy aside first. Install in one discovery location only; a second link in `~/.agents/skills` can produce a duplicate skill entry. Reopen the agent's skill picker or start a new chat to refresh discovery.

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

The runner adds `data_collection: "deny"` and `zdr: true` on every request. Each call is pinned to an approved endpoint; automatic fallback is disabled so the output allowance cannot silently shrink. If no allowed endpoint satisfies these settings, the rung fails; the agent must not relax your rules to make it work. Model availability and provider support can change, so check the current model pages before use:

- [DeepSeek V4.1 Flash](https://openrouter.ai/deepseek/deepseek-v4.1-flash)
- [DeepSeek V4 Pro](https://openrouter.ai/deepseek/deepseek-v4-pro)

For a config stored outside the installed skill, set `OPENROUTER_PROVIDER_CONFIG` to its absolute path.

### 3. Use it

Ask your coding agent:

> Use triple-escalator to fix this issue. Define the done-check first, start with Flash, try Pro if Flash fails, and finish in this chat if both fail. Preserve my existing changes and report the checks and cost per rung.

Start with a small task and inspect the diff and results. Irreversible actions, payment or credential work, restricted data, and tasks without a reliable done-check stay in the calling chat, subject to your usual approvals.

## Output and reasoning

The runner reads the selected endpoint's live output capacity and explicitly
requests that allowance, reserving context space for the prompt. It adds no
fixed application token cap. Reasoning counts towards that allowance.
Flash currently selects `morph/fp8`; Pro selects `azure/us`. Both must be in your
approved provider list. Use `--provider baseten/fp4` to select another approved
Pro endpoint. Availability and limits are checked before each call. Flash and Pro
both default to high reasoning; Flash can also be set to low or max. Use
`--reasoning-effort` to select another supported level.
See [OpenRouter's reasoning-token documentation](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

A truncated or empty response fails with a nonzero exit code. It never becomes
the usable reply file. A metadata sidecar records the finish reason, token usage
and cost; partial text stays in a separate file. A completed response still needs
to pass exact-match edit validation and the task's checks.

## Data sovereignty

A provider allowlist is a routing control. A company's country of ownership does not prove where a particular endpoint processes data. Retention rules and processing location are separate questions. Verify the endpoint, region, subprocessors and contractual terms against your actual requirements. Where strict regional processing is required, use a verified in-region service and configuration; do not infer it from a provider name. See [OpenRouter's sovereign routing documentation](https://openrouter.ai/docs/guides/features/sovereign-ai).

OpenRouter documents separate [provider-routing controls](https://openrouter.ai/docs/guides/routing/provider-selection) and [zero-data-retention policies](https://openrouter.ai/docs/guides/features/zdr). ZDR does not mean the data stays on your machine, and OpenRouter permits some in-memory caching within its definition. Review OpenRouter's own privacy settings as well as the downstream provider's terms.

Keep credentials, customer records, proprietary pricing and other restricted material out of delegated prompts unless the chosen service and workflow are approved for it. The runner sends the prompt file you give it; it is not a sensitive-data scanner. The calling chat is also a hosted service with its own policies.

## Verify the package locally

```sh
python3 -m unittest discover -s triple-escalator/tests -v
```

The tests use local fixtures and mocked HTTP calls. They do not spend API credit. The strict edit helper operates on existing files and checks all edit blocks before writing. Keep a snapshot: an interrupted disk write can still leave partial changes.

The public bundle uses user-configured providers and environment-based credentials. It contains no private account configuration.
