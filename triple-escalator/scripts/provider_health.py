#!/usr/bin/env python3
"""Passive request reliability counters. No prompts, credentials or model calls."""
import argparse
import csv
import fcntl
import json
import os
from pathlib import Path
import re
import statistics
import time

DEFAULT_LOG = Path.home() / ".local/share/triple-escalator/provider-reliability/requests.csv"
FIELDS = ["attempt", "at", "provider", "model", "status", "http_status", "seconds", "cost_usd", "prompt_tokens", "completion_tokens"]


def record(attempt, provider, model, status, seconds, usage=None, error=None, at=None, path=DEFAULT_LOG):
    usage = usage or {}
    http = re.search(r"HTTP (\d{3})", error or "")
    row = dict(attempt=attempt, at=at if at is not None else time.time(), provider=provider, model=model,
               status=status, http_status=http.group(1) if http else "", seconds=round(seconds, 3),
               cost_usd=usage.get("cost", ""), prompt_tokens=usage.get("prompt_tokens", ""),
               completion_tokens=usage.get("completion_tokens", ""))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("a", newline="") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        if os.fstat(stream.fileno()).st_size == 0:
            writer.writeheader()
        writer.writerow(row)


def rows(path=DEFAULT_LOG):
    if not Path(path).exists():
        return []
    with Path(path).open(newline="") as stream:
        # Request IDs are stable. Re-importing a journal cannot inflate the report.
        return list({r["attempt"]: r for r in csv.DictReader(stream)}.values())


def summary(path=DEFAULT_LOG):
    result = []
    data = rows(path)
    for provider, model in sorted({(r["provider"], r["model"]) for r in data}):
        group = [r for r in data if (r["provider"], r["model"]) == (provider, model)]
        received = [r for r in group if r["status"] == "received"]
        result.append(dict(provider=provider, model=model, requests=len(group), received=len(received),
            failed=len(group)-len(received), rate_limits=sum(r["http_status"] == "429" for r in group),
            median_received_seconds=round(statistics.median(float(r["seconds"]) for r in received), 3) if received else None,
            known_cost_usd=sum(float(r["cost_usd"]) for r in group if r["cost_usd"] != ""),
            unknown_cost_requests=sum(r["cost_usd"] == "" for r in group)))
    return result


def import_session(directory, path=DEFAULT_LOG):
    events = [json.loads(line) for line in (Path(directory)/"events.jsonl").read_text().splitlines() if line.strip()]
    requests = {r["attempt"]: r for r in events if r["type"] == "request"}
    failures = {r["attempt"]: r.get("detail") for r in events if r["type"] == "failure" and "attempt" in r}
    existing = {r["attempt"] for r in rows(path)}
    for event in events:
        if event["type"] != "response" or event["attempt"] in existing:
            continue
        req = requests[event["attempt"]]
        model = "deepseek/deepseek-v4-pro" if req["worker"] == "pro" else "deepseek/deepseek-v4.1-flash"
        record(event["attempt"], req.get("provider", "unknown"), model, event.get("status", "unknown"),
               event.get("elapsed_seconds", 0), event.get("usage"), failures.get(event["attempt"]), event["at"], path)
        existing.add(event["attempt"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--import-session", type=Path, action="append", default=[])
    args = parser.parse_args()
    for session in args.import_session:
        import_session(session, args.log)
    print(json.dumps(summary(args.log), indent=2))
