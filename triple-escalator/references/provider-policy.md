# External routing and data rules

Before running an external rung, confirm the user has set their own `OPENROUTER_API_KEY` and a non-empty `only` list in `providers.json`, or at `OPENROUTER_PROVIDER_CONFIG`.

- Send requests only through the supplied OpenRouter runner.
- Preserve the user's `only` allowlist and `ignore` blocklist. Never broaden them to rescue a failed request.
- The runner requires `data_collection: "deny"` and `zdr: true`. If no compatible endpoint is available, record the failure and escalate within the configured cascade.
- Check current model and provider availability. Provider ownership, inference region, retention, caching and contractual commitments are distinct; do not describe these settings as a blanket sovereignty or compliance guarantee.
- Keep API keys, tokens, environment files and restricted business or personal data out of prompts. The runner does not inspect content for secrets.
- Send only the files and context needed for the bounded task, rather than an entire repository or chat transcript.
- For strict regional-processing requirements, require a separately verified in-region service configuration. This runner uses the standard OpenRouter API endpoint and does not promise regional processing.
- Rung three is direct work in the calling chat under that service's own policies. It is not local/offline inference and is not another external rung.

Official references: [routing](https://openrouter.ai/docs/guides/routing/provider-selection), [retention](https://openrouter.ai/docs/guides/features/zdr), [regional processing](https://openrouter.ai/docs/guides/features/sovereign-ai).
