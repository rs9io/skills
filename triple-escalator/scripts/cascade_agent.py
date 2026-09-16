#!/usr/bin/env python3
"""Run a persistent OpenCode coding worker through the approved OpenRouter route."""
import argparse
from contextlib import ExitStack
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import socket
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import uuid

from cascade_run import ENDPOINT, MODELS, output_route, provider_config
from cascade_session import Session, lock, revision
from cascade_sandbox import profile
from provider_health import record as record_provider_health

VERSION = "1.18.31"
RUNTIME = Path.home() / ".local/share/triple-escalator/runtime/node_modules/.bin/opencode"
POLICY = """You are the persistent coding worker for this PR, not a patch-writing service.
The original parent owns the plan and acceptance criteria. Read the relevant repository
instructions and source yourself. Use your file, search, edit and terminal tools to
implement the task, run its baseline and acceptance checks, inspect failures, and repair
these yourself. Self-review the complete diff and the integration between changed
components. Do not stop at a patch or ask the parent to do routine implementation,
testing or fixes. Own the work until accessible acceptance checks pass.
Do not send patches or routine shell work back to the parent. Keep working until the
agreed checks pass, a real permission barrier is reached, or evidence shows you cannot
solve it. Repeated identical failures without a new hypothesis mean stop and report.
Do not weaken tests or redefine acceptance to claim success. Preserve user changes.
Return only to the originating parent. Do not hand off to Flash or Pro, invoke
another worker, or turn failure into a request for an automatic model switch.
Use no other agents or models. No credentials, .env files, private account data,
production access, external messages, push, merge, deployment, or destructive Git.
If the task needs any of these, return the precise blocked action to the parent.
Do not use em dashes in authored prose.
On completion, deliver evidence of finished work. While unfinished, return only for
a concrete inability to finish, with attempts, exact failures, current diff and blocker.
End with a concise report: changed files and approach; exact commands, exit results
and remaining failures; decisions or scope questions; what the parent must verify.
A passing local check is not final acceptance. Never claim a test you did not run.
"""


def api_key():
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise ValueError("Set OPENROUTER_API_KEY in the calling agent's environment.")
    return key


class Progress:
    """Local status only: no prompt, tool input, output or extra model call."""
    def __init__(self, path, bridge, run_id, pid, interval=30):
        self.path, self.bridge, self.run_id, self.pid = path, bridge, run_id, pid
        self.interval, self.started = interval, time.monotonic()
        self.activity = "Starting worker"
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self.watch, daemon=True)

    def emit(self, status):
        state = {"run": self.run_id, "pid": self.pid, "worker": self.bridge.worker,
                 "provider": self.bridge.tag, "status": status, "updated_at": time.time(),
                 "elapsed_seconds": round(time.monotonic()-self.started),
                 "api_calls": self.bridge.calls, "known_cost_usd": self.bridge.cost,
                 "unknown_cost": self.bridge.unknown, "last_activity": self.activity}
        try:
            pending = self.path.with_suffix(".tmp")
            pending.write_text(json.dumps(state, indent=2)+"\n")
            pending.replace(self.path)
        except OSError:
            pass  # Display failure must not stop the worker or its cleanup.
        extra = " + unknown billing" if state["unknown_cost"] else ""
        try:
            print(f"[{state['worker']} {status}] {state['provider']} | "
                  f"{state['elapsed_seconds']}s | {state['api_calls']} calls | "
                  f"US${state['known_cost_usd']:.4f}{extra} | {self.activity}",
                  file=sys.stderr, flush=True)
        except (OSError, ValueError):
            pass  # The parent may close its progress pipe before the worker exits.

    def start(self):
        self.emit("running")
        self.thread.start()

    def watch(self):
        while not self.stopped.wait(self.interval):
            self.emit("running")

    def stop(self, status):
        if self.stopped.is_set():
            return
        self.stopped.set()
        if self.thread.is_alive():
            self.thread.join()
        self.emit(status)


class Bridge:
    """Inject routing at the wire boundary, including SDK-generated requests."""
    def __init__(self, session, worker, task, model, provider, tag, effort, key, catalogue, budget=None):
        self.session, self.worker, self.task = session, worker, task
        self.model, self.provider, self.tag, self.effort = model, provider, tag, effort
        self.key, self.catalogue, self.budget = key, catalogue, budget
        self.token = secrets.token_urlsafe(32)
        self.cost, self.unknown, self.errors, self.calls = 0, False, [], 0
        self.mutex = threading.Lock()

    def prepare(self, body):
        if body.get("model") != self.model:
            raise ValueError("Unexpected model request; no silent worker or helper-model substitution.")
        if self.budget is not None and (self.unknown or self.cost >= self.budget):
            raise ValueError("Canary budget reached or billing unknown. Stop before another request.")
        body.pop("max_completion_tokens", None)
        body.pop("reasoning_effort", None)
        body["reasoning"] = {"effort": self.effort}
        route, allowance = output_route(self.model, self.provider, self.tag, [], self.catalogue, request=body)
        body.update(provider=route, max_tokens=allowance)
        body["stream_options"] = {"include_usage": True}
        return body

    def record_usage(self, attempt, usage, started, status, error=None):
        known = isinstance((usage or {}).get("cost"), (int, float))
        self.cost += usage["cost"] if known else 0
        self.unknown |= not known
        self.session.append("response", attempt=attempt, worker=self.worker, task=self.task,
                            usage=usage, status=status, elapsed_seconds=time.monotonic()-started,
                            content=None, report=None)
        try:
            record_provider_health(attempt, self.tag, self.model, status, time.monotonic()-started, usage, error)
        except OSError as exc:
            print(f"Provider reliability log unavailable: {type(exc).__name__}", file=sys.stderr)

    def handler(self):
        bridge = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                if self.path != "/chat/completions" or self.headers.get("Authorization") != "Bearer " + bridge.token:
                    self.send_error(403)
                    return
                with bridge.mutex:
                    attempt, started, usage, sent, status = str(uuid.uuid4()), time.monotonic(), None, False, "failed"
                    detail = None
                    try:
                        body = bridge.prepare(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                        bridge.session.append("request", attempt=attempt, worker=bridge.worker, task=bridge.task,
                                              prompt="Native coding-worker step; transcript in OpenCode session.",
                                              output_allowance=body["max_tokens"], provider=bridge.tag, reasoning_effort=bridge.effort)
                        bridge.calls += 1
                        sent = True
                        request = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(), headers={
                            "Authorization": "Bearer " + bridge.key, "Content-Type": "application/json"})
                        with urllib.request.urlopen(request, timeout=900) as upstream:
                            content_type = upstream.headers.get("Content-Type", "application/json")
                            self.send_response(200)
                            self.send_header("Content-Type", content_type)
                            self.send_header("Connection", "close")
                            self.end_headers()
                            if "text/event-stream" in content_type:
                                complete, finished, meaningful = False, False, False
                                for line in upstream:
                                    if not line.startswith(b"data: "):
                                        self.wfile.write(line); self.wfile.flush()
                                        continue
                                    value = line[6:].strip()
                                    if value == b"[DONE]":
                                        if not finished or not meaningful:
                                            raise ValueError("Empty or unfinished provider stream")
                                        complete = True
                                        self.wfile.write(line); self.wfile.flush()
                                        continue
                                    chunk = json.loads(value)
                                    if chunk.get("usage"):
                                        usage = chunk["usage"]
                                    if chunk.get("error"):
                                        raise ValueError("Provider returned a streaming error")
                                    for choice in chunk.get("choices", []):
                                        delta = choice.get("delta") or {}
                                        meaningful |= bool((delta.get("content") or "").strip() or delta.get("tool_calls"))
                                        finish = choice.get("finish_reason")
                                        if finish in ("stop", "tool_calls"):
                                            finished = True
                                        if finish and finish not in ("stop", "tool_calls"):
                                            raise ValueError("Incomplete provider reply: " + finish)
                                    self.wfile.write(line); self.wfile.flush()
                                if not complete or not finished or not meaningful:
                                    raise ValueError("Provider stream ended without completion")
                            else:
                                raw = upstream.read()
                                result = json.loads(raw)
                                usage = result.get("usage")
                                if result.get("error"):
                                    raise ValueError("Provider returned an error")
                                for choice in result.get("choices", []):
                                    message = choice.get("message", {})
                                    if choice.get("finish_reason") not in ("stop", "tool_calls") or not (message.get("content") or message.get("tool_calls")):
                                        raise ValueError("Incomplete or empty provider reply")
                                if not result.get("choices"):
                                    raise ValueError("Provider returned no choices")
                                self.wfile.write(raw)
                            status = "received"
                    except Exception as error:
                        # Do not log HTTP bodies or request headers containing credentials.
                        detail = type(error).__name__ + (": " + str(error) if isinstance(error, ValueError) else "")
                        if isinstance(error, urllib.error.HTTPError):
                            detail += f": HTTP {error.code}"
                        bridge.errors.append(detail)
                        bridge.session.append("failure", attempt=attempt, worker=bridge.worker, task=bridge.task, detail=detail)
                        if not sent:
                            self.send_error(400, detail)
                    finally:
                        if sent:
                            bridge.record_usage(attempt, usage, started, status, detail)
                        self.close_connection = True
        return Handler


def configuration(model, tag, catalogue, url, token):
    endpoints = [e for e in catalogue["data"]["endpoints"] if e.get("tag") == tag]
    context = min(e["context_length"] for e in endpoints)
    output = min(e["max_completion_tokens"] for e in endpoints)
    # Only this provider exists in the isolated configuration. The real key never
    # enters the coding harness's environment or configuration.
    return {
        "$schema": "https://opencode.ai/config.json", "model": "openrouter/"+model,
        "small_model": "openrouter/"+model, "enabled_providers": ["openrouter"],
        "share": "disabled", "autoupdate": False, "snapshot": False,
        "provider": {"openrouter": {"options": {"baseURL": url, "apiKey": token}, "models": {
            model: {"name": model, "limit": {"context": context, "output": output},
                    "reasoning": True, "tool_call": True, "options": {"reasoning": {"effort": MODELS[model]["effort"]}}}}}},
        "agent": {"title": {"disable": True}, "summary": {"disable": True}},
        "permission": {
            "*": "allow", "external_directory": "deny", "task": "deny", "skill": "deny",
            "webfetch": "deny", "websearch": "deny", "question": "deny", "doom_loop": "deny",
            "read": {"*": "allow", "*.env": "deny", "*.env.*": "deny", "*credentials*": "deny"},
            "bash": {"*": "allow", "git push*": "deny", "git reset*": "deny", "git clean*": "deny",
                     "git checkout --*": "deny", "git restore*": "deny", "git stash*": "deny",
                     "gh *": "deny", "vercel *": "deny", "ssh *": "deny", "curl *": "deny",
                     "wget *": "deny", "printenv*": "deny", "env": "deny"}},
    }


def child_environment(path, config):
    # Allow tooling locations, not inherited API keys, cloud credentials or flags.
    env = {k: os.environ[k] for k in ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TMPDIR", "SHELL") if k in os.environ}
    env.update(XDG_DATA_HOME=str(path/"data"), XDG_CONFIG_HOME=str(path/"config"),
               XDG_CACHE_HOME=str(path/"cache"), XDG_STATE_HOME=str(path/"state"),
               OPENCODE_CONFIG_CONTENT=json.dumps(config), OPENCODE_DISABLE_PROJECT_CONFIG="true",
               OPENCODE_DISABLE_CLAUDE_CODE="true", OPENCODE_DISABLE_DEFAULT_PLUGINS="true",
               TMPDIR=str(path/"tmp"))
    return env


def terminate_group(proc, grace=10):
    """Stop only this run's process group, including descendants after leader exit."""
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        proc.wait()
        return
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        proc.poll()  # reap an exited leader without losing the group identity
        try:
            os.killpg(proc.pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    proc.wait()


def run(args):
    session = Session(args.session)
    worker = args.worker
    model = "deepseek/deepseek-v4-pro" if worker == "pro" else "deepseek/deepseek-v4.1-flash"
    session.check_worker(worker, model)
    executable = str(args.opencode or RUNTIME)
    installed = subprocess.check_output([executable, "--version"], text=True).strip()
    if installed != VERSION:
        raise ValueError(f"Use the tested OpenCode {VERSION} runtime, got {installed}.")
    config_file = os.environ.get("OPENROUTER_PROVIDER_CONFIG") or Path(__file__).resolve().parents[1]/"providers.json"
    provider = provider_config(config_file)
    tag = args.provider or MODELS[model]["provider"]
    with urllib.request.urlopen("https://openrouter.ai/api/v1/models/"+model+"/endpoints", timeout=30) as response:
        catalogue = json.load(response)
    output_route(model, provider, tag, [], catalogue)
    if any("tools" not in e.get("supported_parameters", []) for e in catalogue["data"]["endpoints"] if e.get("tag") == tag):
        raise ValueError("Selected endpoint does not advertise tool calling")
    bridge = Bridge(session, worker, args.task, model, provider, tag, args.reasoning, api_key(), catalogue, args.budget)
    runtime = session.path/"coding"
    runtime.mkdir(exist_ok=True, mode=0o700)
    run_id = str(uuid.uuid4())
    run_dir = runtime/run_id
    run_dir.mkdir(mode=0o700)
    repo_lock_dir = Path.home()/".cache/triple-escalator/locks"
    repo_lock_dir.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), bridge.handler())
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    (runtime/"tmp").mkdir(exist_ok=True)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        native_port = sock.getsockname()[1]
    sandbox = profile(session.meta["repo"], runtime, executable, [server.server_port, native_port], args.read_dir)
    sandbox_file = run_dir/"sandbox.sb"
    sandbox_file.write_text(sandbox)
    config = configuration(model, tag, catalogue, f"http://127.0.0.1:{server.server_port}", bridge.token)
    env = child_environment(runtime, config)
    command = ["/usr/bin/sandbox-exec", "-f", str(sandbox_file), executable, "run", "--pure", "--port", str(native_port), "--format", "json", "--model", "openrouter/"+model, "--agent", "build"]
    final, failures, native_id, proc = [], [], None, None
    watchdog = None
    progress = None
    started = time.monotonic()
    repo_key = hashlib.sha256(str(Path(session.meta["repo"]).resolve()).encode()).hexdigest()
    ownership = ExitStack()
    try:
        ownership.enter_context(lock(session.path, worker, blocking=False))
        ownership.enter_context(lock(repo_lock_dir, repo_key, blocking=False))
        session.check_worker(worker, model)
        events = session.events()
        binding = next((e for e in reversed(events) if e["type"] == "coding_session" and e["worker"] == worker), None)
        checkpoint = max((i for i,e in enumerate(events) if e["type"] == "brief" and e.get("fold_notes")), default=-1)
        brief = next(e["text"] for e in reversed(events) if e["type"] == "brief")
        notes = "\n".join(e["text"] for e in events[checkpoint+1:] if e["type"] == "note")
        prompt = POLICY+"\nCurrent parent plan (supersedes earlier decisions):\n"+brief+"\nCorrections:\n"+notes+"\nTask "+args.task+":\n"+args.prompt.read_text()
        if binding:
            command += ["--session", binding["native_id"]]
            native_id = binding["native_id"]
        command += [prompt]
        before = revision(session.meta["repo"])
        session.append("coding_start", worker=worker, task=args.task, run=run_id, revision=before, log=str(run_dir))
        with (run_dir/"stderr.log").open("w") as stderr, (run_dir/"events.jsonl").open("w") as output:
            proc = subprocess.Popen(command, cwd=session.meta["repo"], env=env, stdout=subprocess.PIPE,
                                    stderr=stderr, text=True, start_new_session=True)
            progress = Progress(run_dir/"status.json", bridge, run_id, proc.pid)
            progress.start()
            def expire():
                failures.append("Worker wall-time limit reached; inspect evidence and resume the same session.")
                terminate_group(proc)
            watchdog = threading.Timer(args.timeout, expire)
            watchdog.daemon = True
            watchdog.start()
            for line in proc.stdout:
                output.write(line); output.flush()
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                sid = event.get("sessionID")
                if sid and native_id and sid != native_id:
                    raise ValueError("Harness changed worker session unexpectedly")
                if sid and not native_id:
                    native_id = sid
                    session.append("coding_session", worker=worker, native_id=sid)
                kind, part = event.get("type"), event.get("part", {})
                if kind == "text":
                    final.append(part.get("text", ""))
                if kind == "error":
                    failures.append(event.get("error"))
                if kind == "tool_use":
                    state = part.get("state", {})
                    progress.activity = f"{part.get('tool', 'tool')} {state.get('status', 'unknown')}"
                    session.append("worker_tool", worker=worker, task=args.task, run=run_id,
                                   tool=part.get("tool"), status=state.get("status"),
                                   input=state.get("input"), output=state.get("output"), metadata=state.get("metadata"))
            code = proc.wait()
        status = "returned" if code == 0 and final and not failures and not bridge.errors else "blocked_or_failed"
        report = {"run": run_id, "worker": worker, "native_session": native_id, "task": args.task,
                  "status": status, "exit_code": code, "elapsed_seconds": time.monotonic()-started, "report": "\n".join(final), "errors": failures+bridge.errors,
                  "api_calls": bridge.calls, "known_cost_usd": bridge.cost, "unknown_cost": bridge.unknown,
                  "before": before, "after": revision(session.meta["repo"]), "logs": str(run_dir)}
        (run_dir/"report.json").write_text(json.dumps(report, indent=2)+"\n")
        session.append("coding_result", **report)
        progress.stop(status)
        print(json.dumps(report, indent=2))
        return 0 if status == "returned" else 2
    finally:
        if watchdog:
            watchdog.cancel()
        if proc:
            terminate_group(proc)
        if progress:
            progress.stop("interrupted")
        if watchdog and watchdog.is_alive():
            watchdog.join()
        server.shutdown(); server.server_close(); thread.join()
        ownership.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("worker", choices=["flash", "flash-2", "pro"])
    parser.add_argument("prompt", type=Path)
    parser.add_argument("--session", required=True, type=Path)
    parser.add_argument("--task", required=True)
    parser.add_argument("--opencode", type=Path)
    parser.add_argument("--provider")
    parser.add_argument("--read-dir", type=Path, action="append", default=[], help="Specific additional read-only dependency directory approved by the parent")
    parser.add_argument("--reasoning", help="Defaults to the model policy: Flash max; legacy Pro high")
    parser.add_argument("--timeout", type=int, default=3600, help="Wall-time stop in seconds, preserves session for resume")
    parser.add_argument("--budget", type=float, help="Optional known-dollar canary stop between requests; not a token cap")
    args = parser.parse_args()
    model = "deepseek/deepseek-v4-pro" if args.worker == "pro" else "deepseek/deepseek-v4.1-flash"
    if args.timeout <= 0 or (args.budget is not None and args.budget <= 0):
        parser.error("Timeout and optional budget must be positive")
    args.reasoning = args.reasoning or MODELS[model]["effort"]
    if args.reasoning not in MODELS[model]["efforts"]:
        parser.error("Unsupported reasoning effort for selected worker")
    try:
        return run(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
