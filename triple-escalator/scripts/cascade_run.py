#!/usr/bin/env python3
"""Call one external rung. Rung three stays in the calling chat."""
import argparse
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request
from cascade_apply import parse

MODELS = {
    "deepseek/deepseek-v4.1-flash": {"effort": "high", "efforts": {"low", "high", "max"}, "provider": "morph/fp8"},
    "deepseek/deepseek-v4-pro": {"effort": "high", "efforts": {"high", "xhigh"}, "provider": "azure/us"},
}

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


def provider_config(path):
    config = json.loads(Path(path).read_text())
    allowed, blocked = config.get("only"), config.get("ignore", [])
    if not isinstance(allowed, list) or not allowed or not all(isinstance(x, str) and x.strip() for x in allowed):
        raise ValueError("Configure a non-empty 'only' list of providers you have approved.")
    if not isinstance(blocked, list) or not all(isinstance(x, str) and x.strip() for x in blocked):
        raise ValueError("'ignore' must be a list of blocked provider slugs.")
    if set(allowed) & set(blocked):
        raise ValueError("A provider cannot be both allowed and blocked.")
    return {"only": allowed, "ignore": blocked, "data_collection": "deny", "zdr": True, "allow_fallbacks": True, "require_parameters": True}


def output_route(model, provider, tag, messages, catalogue=None):
    """Use the selected endpoint's live capacity, never an application token cap."""
    base = tag.split("/", 1)[0]
    def includes(slug):
        return tag == slug or base == slug
    if not any(includes(x) for x in provider["only"]) or any(includes(x) for x in provider["ignore"]):
        raise ValueError("Selected provider is outside the approved allowlist.")
    if catalogue is None:
        with urllib.request.urlopen("https://openrouter.ai/api/v1/models/" + model + "/endpoints", timeout=30) as response:
            catalogue = json.load(response)
    endpoints = [e for e in catalogue.get("data", {}).get("endpoints", []) if e.get("tag") == tag]
    if not endpoints:
        raise ValueError("Selected endpoint is absent from the live catalogue.")
    # Bytes conservatively reserve input space without relying on a guessed tokenizer.
    input_reserve = len(json.dumps(messages, ensure_ascii=False).encode("utf-8"))
    capacities = []
    for endpoint in endpoints:
        maximum, context = endpoint.get("max_completion_tokens"), endpoint.get("context_length")
        if not isinstance(maximum, int) or not isinstance(context, int) or maximum <= 0:
            raise ValueError("Selected endpoint does not advertise a usable output capacity.")
        if "max_tokens" not in endpoint.get("supported_parameters", []):
            raise ValueError("Selected endpoint cannot honour an explicit output allowance.")
        capacities.append(min(maximum, context - input_reserve))
    allowance = min(capacities)
    if allowance <= 0:
        raise ValueError("Prompt exceeds the selected endpoint's context capacity.")
    return {**provider, "only": [tag], "allow_fallbacks": False}, allowance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model")
    parser.add_argument("prompt", type=Path)
    parser.add_argument("reply", type=Path)
    parser.add_argument("--provider", help="Exact approved endpoint tag, e.g. azure/us or baseten/fp4")
    parser.add_argument("--reasoning-effort", help="Flash: low/high/max; Pro: high/xhigh")
    args = parser.parse_args()
    if args.model not in MODELS:
        parser.error("Only Flash and Pro use this runner. Final rescue runs directly in the calling chat.")
    effort = args.reasoning_effort or MODELS[args.model]["effort"]
    if effort not in MODELS[args.model]["efforts"]:
        parser.error("Unsupported reasoning effort for this model; check its live catalogue entry.")
    try:
        if args.reply.exists() or Path(str(args.reply) + ".meta.json").exists():
            raise ValueError("Use a fresh reply path for each attempt so earlier evidence is preserved.")
        config_path = os.environ.get("OPENROUTER_PROVIDER_CONFIG") or Path(__file__).resolve().parents[1] / "providers.json"
        provider = provider_config(config_path)
        key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not key:
            raise ValueError("Set OPENROUTER_API_KEY in the environment inherited by your coding agent.")
        prompt = args.prompt.read_text()
        if not prompt.strip():
            raise ValueError("The prompt is empty.")
        messages = [
            {"role": "system", "content": "Return only complete FILE:/FIND:/REPLACE WITH: edit blocks. Every FILE marker needs a colon. No prose or Markdown fences. Make surgical replacements, not entire-file dumps. Follow the user's task and output format."},
            {"role": "user", "content": prompt},
        ]
        tag = args.provider or MODELS[args.model]["provider"]
        provider, allowance = output_route(args.model, provider, tag, messages)
        print(f"route={tag} requested_output_allowance={allowance} reasoning={effort}", flush=True)
        request = urllib.request.Request(ENDPOINT, data=json.dumps({
            "model": args.model, "provider": provider, "messages": messages,
            "reasoning": {"effort": effort}, "max_tokens": allowance,
        }).encode(), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=900) as response:
            body = json.load(response)
        if "error" in body:
            raise ValueError("OpenRouter returned an API error. Treat this as rung failure.")
        choice = body["choices"][0]
        usage = body.get("usage") or {}
        content = choice["message"].get("content")
        metadata = {
            "id": body.get("id"), "model": args.model, "provider": body.get("provider"),
            "reasoning_effort": effort, "requested_provider": tag, "requested_output_allowance": allowance,
            "finish_reason": choice.get("finish_reason"), "usage": usage,
            "content_characters": len(content) if isinstance(content, str) else 0,
        }
        Path(str(args.reply) + ".meta.json").write_text(json.dumps(metadata, indent=2) + "\n")
        cost = usage.get("cost")
        reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens", "unknown")
        print(f"model={args.model} provider={body.get('provider', 'unknown')} cost={cost if cost is not None else 'unknown'} completion_tokens={usage.get('completion_tokens', 'unknown')} reasoning_tokens={reasoning} finish={choice.get('finish_reason')}")
        if choice.get("finish_reason") != "stop" or not isinstance(content, str) or not content.strip():
            if isinstance(content, str) and content:
                Path(str(args.reply) + ".partial.txt").write_text(content)
            raise ValueError("Incomplete or empty reply. Do not apply it. Split the task or retry once with a justified prompt/effort change, then escalate.")
        try:
            blocks = parse(content)
            if not blocks or any(not block["file"] or not "\n".join(block["find"]).strip() for block in blocks):
                raise ValueError("Each edit needs a target file and non-empty FIND text.")
        except ValueError as error:
            Path(str(args.reply) + ".partial.txt").write_text(content)
            raise ValueError("Reply is not in the required edit format. Do not apply it.") from error
        args.reply.write_text(content)
    except urllib.error.HTTPError as error:
        print(f"OpenRouter HTTP {error.code}. Do not relax provider restrictions to retry.", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        print(f"Rung failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
