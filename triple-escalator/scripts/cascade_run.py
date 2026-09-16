#!/usr/bin/env python3
"""Call one external rung. Rung three stays in the calling chat."""
import argparse
import json
import os
from pathlib import Path
import sys
import subprocess
import time
import uuid
from contextlib import nullcontext
from cascade_session import Session, lock, revision
import urllib.error
import urllib.request
from cascade_apply import parse
from cascade_tokens import input_tokens

MODELS = {
    "deepseek/deepseek-v4.1-flash": {"effort": "max", "efforts": {"low", "high", "max"}, "provider": "morph/fp8"},
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


def output_route(model, provider, tag, messages, catalogue=None, *, request=None):
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
    # A startup catalogue check has no prompt. Actual calls include native chat
    # framing, tool schemas and tool results, counted locally without API spend.
    input_reserve = input_tokens(model, request if request is not None else
                                 {"model": model, "messages": messages}) if request is not None or messages else 0
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


EDIT_INSTRUCTIONS = "Return complete FILE:/FIND:/REPLACE WITH: edit blocks. Every FILE marker needs a colon. No Markdown fences. Make surgical replacements, not entire-file dumps."
SESSION_INSTRUCTIONS = (
    "You are the same generalist worker for this PR. The originating parent owns the plan and acceptance criteria. "
    "Use its current brief, corrections and supplied source; do not repeat rejected approaches. "
    "You cannot run commands in this API call. Never claim tests were executed. "
    'Return REPORT: on its own line, then a JSON object with attempted (string), changes (string), remaining (list of strings). '
    "Then return EDITS: on its own line followed by the edit blocks. If blocked, explain in remaining and leave EDITS empty. "
    + EDIT_INSTRUCTIONS
)


def unpack(content, persistent):
    if not persistent:
        return None, content
    header, marker, edits = content.partition("\nEDITS:\n")
    if not header.startswith("REPORT:\n") or not marker:
        raise ValueError("Persistent workers must return REPORT and EDITS sections.")
    report = json.loads(header[len("REPORT:\n"):])
    if (not isinstance(report, dict) or not isinstance(report.get("attempted"), str)
            or not isinstance(report.get("changes"), str) or not isinstance(report.get("remaining"), list)
            or not all(isinstance(x, str) for x in report["remaining"])):
        raise ValueError("Invalid worker report.")
    return report, edits


def call(args, effort, session, worker):
    attempt, started = str(uuid.uuid4()), time.monotonic()
    sent, content, report = False, None, None
    metadata = {"attempt_id": attempt, "model": args.model, "worker": worker, "task": args.task,
                "reasoning_effort": effort, "usage": None, "status": "failed"}
    try:
        config_path = os.environ.get("OPENROUTER_PROVIDER_CONFIG") or Path(__file__).resolve().parents[1] / "providers.json"
        provider = provider_config(config_path)
        key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not key:
            raise ValueError("Set OPENROUTER_API_KEY in the environment inherited by your coding agent.")
        prompt = args.prompt.read_text()
        if not prompt.strip():
            raise ValueError("The prompt is empty.")
        if session:
            session.check_worker(worker, args.model)
            base = revision(session.meta["repo"])
            messages = session.messages(worker, SESSION_INSTRUCTIONS, prompt, base)
            metadata.update(session_id=session.meta["id"], repo=session.meta["repo"], base_revision=base)
        else:
            messages = [{"role": "system", "content": EDIT_INSTRUCTIONS}, {"role": "user", "content": prompt}]
        tag = args.provider or MODELS[args.model]["provider"]
        provider, allowance = output_route(args.model, provider, tag, messages)
        metadata.update(requested_provider=tag, requested_output_allowance=allowance)
        print(f"route={tag} requested_output_allowance={allowance} reasoning={effort}", flush=True)
        request = urllib.request.Request(ENDPOINT, data=json.dumps({
            "model": args.model, "provider": provider, "messages": messages,
            "reasoning": {"effort": effort}, "max_tokens": allowance,
        }).encode(), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        if session:
            session.append("request", attempt=attempt, worker=worker, task=args.task, prompt=messages[-1]["content"], revision=base)
        sent = True
        api_started = time.monotonic()
        with urllib.request.urlopen(request, timeout=900) as response:
            body = json.load(response)
        metadata["api_seconds"] = time.monotonic() - api_started
        if "error" in body:
            raise ValueError("OpenRouter returned an API error. Treat this as rung failure.")
        choice, usage = body["choices"][0], body.get("usage") or {}
        content = choice["message"].get("content")
        metadata.update(id=body.get("id"), provider=body.get("provider"), finish_reason=choice.get("finish_reason"), usage=usage)
        print(f"model={args.model} provider={body.get('provider', 'unknown')} cost={usage.get('cost', 'unknown')} completion_tokens={usage.get('completion_tokens', 'unknown')} finish={choice.get('finish_reason')}")
        if choice.get("finish_reason") != "stop" or not isinstance(content, str) or not content.strip():
            raise ValueError("Incomplete or empty reply. Do not apply it; retain this worker's history when retrying or escalating.")
        report, edits = unpack(content, bool(session))
        metadata["report"] = report
        blocks = parse(edits)
        if not blocks or any(not block["file"] or not "\n".join(block["find"]).strip() for block in blocks):
            raise ValueError("No complete usable edits. Read the worker report before continuing.")
        if session and revision(session.meta["repo"]) != base:
            raise ValueError("Working tree changed during the call. Feed the current diff back to the same worker.")
        args.reply.write_text(edits)
        metadata["status"] = "proposed"
        return 0
    except (OSError, ValueError, KeyError, IndexError, TypeError, subprocess.CalledProcessError) as error:
        metadata["error"] = f"OpenRouter HTTP {error.code}" if isinstance(error, urllib.error.HTTPError) else str(error)
        print("Rung failed: " + metadata["error"], file=sys.stderr)
        if isinstance(content, str) and content:
            Path(str(args.reply) + ".partial.txt").write_text(content)
        return 2
    finally:
        metadata["elapsed_seconds"] = time.monotonic() - started
        metadata["content_characters"] = len(content) if isinstance(content, str) else 0
        Path(str(args.reply) + ".meta.json").write_text(json.dumps(metadata, indent=2) + "\n")
        if session and sent:
            session.append("response", attempt=attempt, worker=worker, task=args.task, content=content,
                           report=report, usage=metadata["usage"], status=metadata["status"],
                           elapsed_seconds=metadata.get("api_seconds", metadata["elapsed_seconds"]))
            if metadata["status"] != "proposed":
                session.append("failure", attempt=attempt, worker=worker, task=args.task,
                               detail=metadata.get("error", "Call interrupted; outcome unknown. Do not assume edits were applied."))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model")
    parser.add_argument("prompt", type=Path)
    parser.add_argument("reply", type=Path)
    parser.add_argument("--session", type=Path, help="Existing PR-scoped conversation directory")
    parser.add_argument("--task", help="Stable work-item ID; retain it through retries and escalation")
    parser.add_argument("--worker", choices=["flash", "flash-2", "pro"])
    parser.add_argument("--one-shot", action="store_true", help="Protocol diagnostics only, not application work")
    parser.add_argument("--provider", help="Exact approved endpoint tag")
    parser.add_argument("--reasoning-effort", help="Flash: low/high/max; Pro: high/xhigh")
    args = parser.parse_args()
    if args.model not in MODELS:
        parser.error("Only Flash and Pro use this runner. Final rescue belongs to the originating parent.")
    effort = args.reasoning_effort or MODELS[args.model]["effort"]
    if effort not in MODELS[args.model]["efforts"]:
        parser.error("Unsupported reasoning effort for this model; check its live catalogue entry.")
    try:
        if args.reply.exists() or Path(str(args.reply) + ".meta.json").exists():
            raise ValueError("Use a fresh reply path; prior evidence must be preserved.")
        if bool(args.session) == args.one_shot or (args.session and not args.task):
            raise ValueError("Application work requires --session and --task. Use --one-shot only for protocol diagnostics.")
        session = Session(args.session) if args.session else None
        worker = args.worker or ("flash" if args.model.endswith("flash") else "pro")
        if session and args.reply.resolve().is_relative_to(Path(session.meta["repo"])):
            raise ValueError("Keep replies and metadata outside the repository, alongside session history.")
        args.reply.parent.mkdir(parents=True, exist_ok=True)
        with lock(session.path, worker, blocking=False) if session else nullcontext():
            return call(args, effort, session, worker)
    except (OSError, ValueError) as error:
        print(f"Rung failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
