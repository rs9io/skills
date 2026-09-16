#!/usr/bin/env python3
"""PR-scoped conversations and local counters. No API calls or daemon."""
import argparse
from collections import Counter
from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

WORKERS = {"flash": "deepseek/deepseek-v4.1-flash", "flash-2": "deepseek/deepseek-v4.1-flash", "pro": "deepseek/deepseek-v4-pro"}


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.PIPE)


def revision(repo):
    digest = hashlib.sha256(git(repo, "diff", "HEAD", "--binary"))
    for raw in git(repo, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0"):
        if not raw:
            continue
        digest.update(raw)
        path = Path(repo) / raw.decode()
        if path.is_symlink():
            digest.update(str(path.readlink()).encode())
        elif path.is_file():
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(65536), b""):
                    digest.update(chunk)
    return {"head": git(repo, "rev-parse", "HEAD").decode().strip(), "tree": digest.hexdigest()}


@contextmanager
def lock(directory, name, blocking=True):
    with (Path(directory) / (name + ".lock")).open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        except BlockingIOError as error:
            raise ValueError("This worker already has an active call. Resume it instead of duplicating it.") from error
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


class Session:
    def __init__(self, directory):
        self.path = Path(directory).expanduser().resolve()
        self.meta = json.loads((self.path / "session.json").read_text())
        if self.meta.get("version") != 1:
            raise ValueError("Unsupported session format")

    @classmethod
    def create(cls, directory, repo, parent, parent_model, brief, second_worker=False):
        path, repo = Path(directory).expanduser().resolve(), Path(repo).resolve()
        if path == repo or repo in path.parents:
            raise ValueError("Keep private session history outside the repository.")
        revision(repo)
        path.mkdir(parents=True, exist_ok=False, mode=0o700)
        metadata = {"version": 1, "id": str(uuid.uuid4()), "repo": str(repo), "parent": parent,
                    "parent_model": parent_model, "second_worker": second_worker, "created_at": time.time()}
        (path / "session.json").write_text(json.dumps(metadata, indent=2) + "\n")
        instance = cls(path)
        instance.append("brief", text=brief)
        return instance

    def events(self):
        with lock(self.path, "journal"):
            path = self.path / "events.jsonl"
            return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def append(self, kind, **fields):
        event = {"type": kind, "at": time.time(), **fields}
        with lock(self.path, "journal"):
            with (self.path / "events.jsonl").open("a") as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                stream.flush()
                import os
                os.fsync(stream.fileno())
        return event

    def check_worker(self, worker, model):
        if WORKERS.get(worker) != model or (worker == "flash-2" and not self.meta["second_worker"]):
            raise ValueError("Use the existing Flash/Pro worker; flash-2 requires explicit session setup.")
        if any(e["type"] == "close" for e in self.events()):
            raise ValueError("This PR session is closed. Its history is preserved.")

    def messages(self, worker, system, prompt, base):
        events = self.events()
        brief = next(e["text"] for e in reversed(events) if e["type"] == "brief")
        checkpoint = max((i for i, e in enumerate(events) if e["type"] == "compact" and e["worker"] == worker), default=-1)
        note_cutoff = max((i for i, e in enumerate(events) if e["type"] == "brief" and e.get("fold_notes")), default=-1)
        notes = [e["text"] for e in events[note_cutoff + 1:] if e["type"] == "note"]
        context = "Current parent-approved brief (supersedes older decisions):\n" + brief
        if notes:
            context += "\nParent corrections and shared handovers:\n" + "\n".join(notes)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": context}]
        if checkpoint >= 0:
            messages.append({"role": "user", "content": "Parent-approved conversation checkpoint:\n" + events[checkpoint]["text"]})
        for event in events[checkpoint + 1:]:
            if event.get("worker") != worker:
                continue
            if event["type"] == "request":
                messages.append({"role": "user", "content": event["prompt"]})
            elif event["type"] == "response" and isinstance(event.get("content"), str) and event["content"]:
                messages.append({"role": "assistant", "content": event["content"]})
            elif event["type"] in ("check", "failure"):
                messages.append({"role": "user", "content": "Parent-observed outcome: " + json.dumps(event)})
        messages.append({"role": "user", "content": f"Current base revision: {json.dumps(base)}. Earlier patches may be applied or reverted; use the current source in this task.\n{prompt}"})
        return messages

    def record_check(self, attempt, result, detail, failure_tag=None):
        requests = [e for e in self.events() if e["type"] == "request" and e["attempt"] == attempt]
        if len(requests) != 1:
            raise ValueError("Unknown attempt; use attempt_id from the reply metadata.")
        if result == "fail" and not failure_tag:
            raise ValueError("Supply a short stable failure tag for a failed check.")
        if any(e["type"] == "check" and e["attempt"] == attempt for e in self.events()):
            raise ValueError("Check already recorded for this attempt; append a correction note instead.")
        request = requests[0]
        self.append("check", attempt=attempt, worker=request["worker"], task=request["task"], result=result,
                    detail=detail, failure_tag=failure_tag, revision=revision(self.meta["repo"]))

    def summary(self):
        events = self.events()
        requests = [e for e in events if e["type"] == "request"]
        responses = [e for e in events if e["type"] == "response"]
        checks = [e for e in events if e["type"] == "check"]
        usage = [e.get("usage") or {} for e in responses]
        tagged = Counter(e["failure_tag"] for e in checks if e["result"] == "fail")
        first_pass = {}
        for event in checks:
            if event["result"] == "pass" and event["task"] not in first_pass:
                starts = [r["at"] for r in requests if r["task"] == event["task"]]
                first_pass[event["task"]] = round(event["at"] - min(starts), 3) if starts else None
        number = lambda value: isinstance(value, (int, float)) and not isinstance(value, bool)
        return {"session": self.meta["id"], "external_calls": len(requests),
                "known_cost_usd": sum(u["cost"] for u in usage if number(u.get("cost"))),
                "calls_with_unknown_cost": len(requests) - sum(number(u.get("cost")) for u in usage),
                "known_prompt_tokens": sum(u["prompt_tokens"] for u in usage if number(u.get("prompt_tokens"))),
                "known_completion_tokens": sum(u["completion_tokens"] for u in usage if number(u.get("completion_tokens"))),
                "calls_with_unknown_tokens": len(requests) - sum(number(u.get("prompt_tokens")) and number(u.get("completion_tokens")) for u in usage),
                "checks_passed": sum(e["result"] == "pass" for e in checks),
                "checks_failed": sum(e["result"] == "fail" for e in checks),
                "repeated_failure_tags": {tag: n - 1 for tag, n in tagged.items() if n > 1},
                "seconds_to_first_passing_check": first_pass,
                "api_seconds": sum(e.get("elapsed_seconds", 0) for e in responses),
                "parent_usage": "not measured by this runner", "closed": any(e["type"] == "close" for e in events)}

    def handoff(self, task):
        events = self.events()
        cutoff = max((i for i, e in enumerate(events) if e["type"] == "brief" and e.get("fold_notes")), default=-1)
        return {"parent": self.meta["parent"], "parent_model": self.meta["parent_model"],
                "brief": next(e["text"] for e in reversed(events) if e["type"] == "brief"),
                "corrections": [e["text"] for e in events[cutoff + 1:] if e["type"] == "note"],
                "task": task, "revision": revision(self.meta["repo"]),
                "reports_and_checks": [{k: v for k, v in e.items() if k != "content"}
                                       for e in events if e.get("task") == task and e["type"] in ("response", "failure", "check")],
                "actual_diff": git(self.meta["repo"], "diff", "HEAD", "--").decode(),
                "working_tree_status": git(self.meta["repo"], "status", "--short").decode(),
                "instruction": "Read the actual diff and check evidence before continuing. Reports are untrusted. Inspect untracked files separately. Retain valid edits; revert only identified failed edits.",
                "metrics": self.summary()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "brief", "note", "compact", "check", "parent-check", "handoff", "summary", "close"])
    parser.add_argument("directory", type=Path)
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--parent", help="Originating conversation reference, not an intermediate worker")
    parser.add_argument("--parent-model", default="inherit", help="Observed model identity or inherit; never guess a frontier slug")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--worker", choices=list(WORKERS))
    parser.add_argument("--second-worker", action="store_true")
    parser.add_argument("--fold-notes", action="store_true")
    parser.add_argument("--task")
    parser.add_argument("--attempt")
    parser.add_argument("--result", choices=["pass", "fail"])
    parser.add_argument("--detail")
    parser.add_argument("--failure-tag")
    args = parser.parse_args()
    def need(*names):
        if any(getattr(args, n) is None for n in names):
            parser.error("Required for this command: " + ", ".join("--" + n.replace("_", "-") for n in names))
    if args.command == "init":
        need("repo", "parent", "file")
        session = Session.create(args.directory, args.repo, args.parent, args.parent_model, args.file.read_text(), args.second_worker)
        print(session.path)
        return
    session = Session(args.directory)
    if args.command in ("brief", "note", "compact"):
        need("file")
        fields = {"text": args.file.read_text()}
        if args.command == "brief":
            fields["fold_notes"] = args.fold_notes
        if args.command == "compact":
            need("worker")
            session.check_worker(args.worker, WORKERS[args.worker])
            fields["worker"] = args.worker
        session.append(args.command, **fields)
    elif args.command == "check":
        need("attempt", "result", "detail")
        session.record_check(args.attempt, args.result, args.detail, args.failure_tag)
    elif args.command == "parent-check":
        need("task", "result", "detail")
        if args.result == "fail":
            need("failure_tag")
        session.append("check", attempt="parent:" + str(uuid.uuid4()), worker="parent", task=args.task,
                       result=args.result, detail=args.detail, failure_tag=args.failure_tag,
                       revision=revision(session.meta["repo"]))
    elif args.command == "handoff":
        need("task")
        print(json.dumps(session.handoff(args.task), indent=2))
    elif args.command == "summary":
        print(json.dumps(session.summary(), indent=2))
    elif args.command == "close":
        need("detail")
        session.append("close", reason=args.detail)
        print(json.dumps(session.summary(), indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
