import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from cascade_session import Session, lock, revision
import cascade_run as runner
import cascade_apply as applier

FLASH = "deepseek/deepseek-v4.1-flash"
PRO = "deepseek/deepseek-v4-pro"


def answer(before="SCHEMA=1", after="SCHEMA=2"):
    return 'REPORT:\n' + json.dumps({"attempted": "Use the approved schema", "changes": "Update schema", "remaining": []}) + f'\nEDITS:\nFILE: app.py\nFIND:\n{before}\nREPLACE WITH:\n{after}'


class Sessions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / "app.py").write_text("SCHEMA=1\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "-qm", "fixture"], check=True)
        self.session = Session.create(self.root / "session", self.repo, "original-chat-123", "inherit", "Use schema two. Parent owns the plan.")
        self.providers = self.root / "providers.json"
        self.providers.write_text('{"only":["morph","azure"],"ignore":["deepseek"]}')
        self.counter = 0

    def run_worker(self, model=FLASH, task="schema", content=None, finish="stop", usage=None, mutate=None, worker=None):
        self.counter += 1
        prompt, reply = self.root / f"prompt{self.counter}", self.root / f"reply{self.counter}"
        prompt.write_text("Continue the agreed task against the supplied current source.")
        tag = "morph/fp8" if model == FLASH else "azure/us"
        endpoint = {"tag": tag, "max_completion_tokens": 384000, "context_length": 1048576, "supported_parameters": ["max_tokens"]}
        body = {"provider": tag, "choices": [{"finish_reason": finish, "message": {"content": content if content is not None else answer()}}], "usage": usage}
        payloads = []
        def api(request, **kwargs):
            if isinstance(request, str):
                return io.StringIO(json.dumps({"data": {"endpoints": [endpoint]}}))
            payloads.append(json.loads(request.data))
            if mutate:
                mutate()
            return io.StringIO(json.dumps(body))
        argv = ["runner", model, str(prompt), str(reply), "--session", str(self.session.path), "--task", task]
        if worker:
            argv += ["--worker", worker]
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "fixture", "OPENROUTER_PROVIDER_CONFIG": str(self.providers)}), patch("sys.argv", argv), patch("urllib.request.urlopen", side_effect=api), patch("sys.stdout", io.StringIO()), patch("sys.stderr", io.StringIO()):
            result = runner.main()
        meta = json.loads(Path(str(reply) + ".meta.json").read_text()) if Path(str(reply) + ".meta.json").exists() else {}
        return result, payloads, reply, meta

    def test_flash_resumes_with_feedback_after_restart(self):
        code, _, reply, meta = self.run_worker()
        self.assertEqual(code, 0)
        applier.apply(self.repo, reply.read_text())
        self.session.record_check(meta["attempt_id"], "fail", "Schema changed but migration missing", "missing-migration")
        self.session = Session(self.session.path)
        code, payloads, _, _ = self.run_worker(content=answer("SCHEMA=2", "SCHEMA=2\nMIGRATION=True"))
        self.assertEqual(code, 0)
        messages = payloads[0]["messages"]
        self.assertTrue(any(m["role"] == "assistant" and "SCHEMA=2" in m["content"] for m in messages))
        self.assertIn("migration missing", json.dumps(messages))
        self.assertIn("schema two", json.dumps(messages))
        self.assertEqual(self.session.summary()["external_calls"], 2)

    def test_twenty_turn_old_decision_and_shared_correction_survive(self):
        for i in range(20):
            self.session.append("request", worker="flash", task="older", attempt=str(i), prompt=f"Earlier task {i}")
            self.session.append("response", worker="flash", task="older", attempt=str(i), content="Prior proposal", usage=None)
        self.session.append("note", text="Parent accepted schema two; never restore schema one.")
        code, payloads, _, _ = self.run_worker()
        self.assertEqual(code, 0)
        self.assertIn("never restore schema one", json.dumps(payloads))
        self.assertTrue(any(m["content"] == "Earlier task 0" for m in payloads[0]["messages"]))

    def test_pro_receives_handoff_and_reuses_own_history(self):
        _, _, reply, meta = self.run_worker()
        applier.apply(self.repo, reply.read_text())
        self.session.record_check(meta["attempt_id"], "fail", "Validation failed", "wrong-schema")
        handoff = self.session.handoff("schema")
        self.assertIn("SCHEMA=2", handoff["actual_diff"])
        self.assertEqual(handoff["parent"], "original-chat-123")
        self.session.append("note", text="Parent-reviewed handover: " + json.dumps(handoff))
        code, payloads, _, _ = self.run_worker(model=PRO, content=answer("SCHEMA=2", "SCHEMA=2\nVALID=True"))
        self.assertEqual(code, 0)
        self.assertIn("Validation failed", json.dumps(payloads))
        code, payloads, _, _ = self.run_worker(model=PRO, content=answer("SCHEMA=2", "SCHEMA=2\nVALID=True"))
        self.assertEqual(code, 0)
        self.assertTrue(any(m["role"] == "assistant" for m in payloads[0]["messages"]))

    def test_compaction_keeps_archive_and_current_decisions(self):
        self.run_worker()
        original = (self.session.path / "events.jsonl").read_text()
        self.session.append("compact", worker="flash", text="Schema two chosen. Migration still needed. Prior edits not applied.")
        _, payloads, _, _ = self.run_worker()
        self.assertTrue((self.session.path / "events.jsonl").read_text().startswith(original))
        self.assertIn("Migration still needed", json.dumps(payloads))
        self.assertFalse(any(m["role"] == "assistant" for m in payloads[0]["messages"]))

    def test_metrics_count_reported_usage_and_tagged_repeats_only(self):
        usage = {"prompt_tokens": 10, "completion_tokens": 20, "cost": 0.01, "completion_tokens_details": {"reasoning_tokens": 15}}
        for _ in range(2):
            _, _, _, meta = self.run_worker(usage=usage)
            self.session.record_check(meta["attempt_id"], "fail", "Wrong schema repeated", "schema-v1")
        _, _, _, meta = self.run_worker()
        self.session.record_check(meta["attempt_id"], "pass", "All required checks passed")
        summary = self.session.summary()
        self.assertEqual(summary["known_prompt_tokens"], 20)
        self.assertEqual(summary["known_completion_tokens"], 40)
        self.assertEqual(summary["known_cost_usd"], 0.02)
        self.assertEqual(summary["calls_with_unknown_cost"], 1)
        self.assertEqual(summary["calls_with_unknown_tokens"], 1)
        self.assertEqual(summary["repeated_failure_tags"], {"schema-v1": 1})
        self.assertGreaterEqual(summary["seconds_to_first_passing_check"]["schema"], 0)
        self.assertEqual(summary["parent_usage"], "not measured by this runner")

    def test_truncation_preserves_history_and_no_usable_patch(self):
        code, _, reply, meta = self.run_worker(finish="length", usage={"cost": 0.02})
        self.assertEqual(code, 2)
        self.assertFalse(reply.exists())
        self.assertTrue(Path(str(reply) + ".partial.txt").exists())
        self.assertEqual(self.session.summary()["known_cost_usd"], 0.02)
        self.assertTrue(any(e["type"] == "failure" for e in self.session.events()))

    def test_changed_tree_during_response_is_rejected(self):
        code, _, reply, _ = self.run_worker(mutate=lambda: (self.repo / "app.py").write_text("SCHEMA=3"))
        self.assertEqual(code, 2)
        self.assertFalse(reply.exists())
        self.assertEqual((self.repo / "app.py").read_text(), "SCHEMA=3")

    def test_changed_tree_before_apply_is_rejected(self):
        _, _, reply, _ = self.run_worker()
        (self.repo / "other.txt").write_text("New decision")
        with patch("sys.argv", ["apply", str(self.repo), str(reply)]):
            with self.assertRaises(SystemExit):
                applier.main()
        self.assertEqual((self.repo / "app.py").read_text(), "SCHEMA=1\n")

    def test_untracked_edits_change_revision(self):
        path = self.repo / "new.py"
        path.write_text("one")
        before = revision(self.repo)
        path.write_text("two")
        self.assertNotEqual(revision(self.repo), before)

    def test_worker_lock_and_second_worker_are_explicit(self):
        with lock(self.session.path, "flash", blocking=False):
            with self.assertRaises(ValueError):
                with lock(self.session.path, "flash", blocking=False):
                    pass
        code, payloads, _, _ = self.run_worker(worker="flash-2")
        self.assertEqual(code, 2)
        self.assertEqual(payloads, [])

    def test_closed_session_keeps_history_and_refuses_api(self):
        self.run_worker()
        original = (self.session.path / "events.jsonl").read_text()
        self.session.append("close", reason="PR merged")
        code, payloads, _, _ = self.run_worker()
        self.assertEqual(code, 2)
        self.assertEqual(payloads, [])
        self.assertTrue((self.session.path / "events.jsonl").read_text().startswith(original))

    def test_no_session_overwrite_or_repository_history(self):
        with self.assertRaises(FileExistsError):
            Session.create(self.session.path, self.repo, "other", "inherit", "other")
        with self.assertRaises(ValueError):
            Session.create(self.repo / "session", self.repo, "other", "inherit", "other")

    def test_worker_report_is_saved_but_not_confused_with_checks(self):
        _, _, _, meta = self.run_worker()
        self.assertEqual(meta["report"]["attempted"], "Use the approved schema")
        self.assertEqual(self.session.summary()["checks_passed"], 0)
        with self.assertRaises(ValueError):
            self.session.record_check("unknown", "pass", "not observed")

    def test_parent_pass_is_counted_without_inventing_parent_tokens(self):
        self.run_worker()
        self.session.append("check", task="schema", worker="parent", attempt="parent:one", result="pass", detail="Parent rescue verified")
        summary = self.session.summary()
        self.assertIn("schema", summary["seconds_to_first_passing_check"])
        self.assertEqual(summary["external_calls"], 1)
        self.assertEqual(summary["checks_passed"], 1)

    def test_folded_notes_stay_archived_but_stop_replaying(self):
        self.session.append("note", text="old correction")
        self.session.append("brief", text="Updated brief incorporates old correction", fold_notes=True)
        self.session.append("note", text="new correction")
        messages = self.session.messages("flash", "system", "task", {})
        self.assertEqual(json.dumps(messages).count("old correction"), 1)
        self.assertEqual(self.session.handoff("schema")["corrections"], ["new correction"])
        self.assertTrue(any(e.get("text") == "old correction" for e in self.session.events()))

    def test_reply_inside_repo_rejected_before_creating_artifacts(self):
        reply = self.repo / "artifacts" / "reply"
        with patch("sys.argv", ["runner", FLASH, "unused", str(reply), "--session", str(self.session.path), "--task", "schema"]), patch("urllib.request.urlopen") as api, patch("sys.stderr", io.StringIO()):
            self.assertEqual(runner.main(), 2)
        api.assert_not_called()
        self.assertFalse(reply.parent.exists())

    def test_application_without_session_is_rejected(self):
        with patch("sys.argv", ["runner", FLASH, "unused", str(self.root / "reply")]), patch("urllib.request.urlopen") as api, patch("sys.stderr", io.StringIO()):
            self.assertEqual(runner.main(), 2)
        api.assert_not_called()

    def test_blocked_report_retained_without_patch(self):
        content = 'REPORT:\n' + json.dumps({"attempted": "Reviewed supplied source", "changes": "None", "remaining": ["Need migration source"]}) + '\nEDITS:\n'
        code, _, reply, meta = self.run_worker(content=content)
        self.assertEqual(code, 2)
        self.assertFalse(reply.exists())
        self.assertEqual(meta["report"]["remaining"], ["Need migration source"])
        self.assertEqual(self.session.summary()["checks_passed"], 0)

    def test_http_failure_records_unknown_usage_and_resumes(self):
        import urllib.error
        prompt, reply = self.root / "prompt-http", self.root / "reply-http"
        prompt.write_text("Continue")
        argv = ["runner", FLASH, str(prompt), str(reply), "--session", str(self.session.path), "--task", "schema"]
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "fixture", "OPENROUTER_PROVIDER_CONFIG": str(self.providers)}), patch("sys.argv", argv), patch.object(runner, "output_route", return_value=({}, 100000)), patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError("fixture", 503, "unavailable", {}, None)), patch("sys.stdout", io.StringIO()), patch("sys.stderr", io.StringIO()):
            self.assertEqual(runner.main(), 2)
        self.assertEqual(self.session.summary()["calls_with_unknown_cost"], 1)
        self.assertEqual(self.session.summary()["calls_with_unknown_tokens"], 1)
        code, payloads, _, _ = self.run_worker()
        self.assertEqual(code, 0)
        self.assertIn("HTTP 503", json.dumps(payloads))

    def test_duplicate_checks_do_not_inflate_metrics(self):
        _, _, _, meta = self.run_worker()
        self.session.record_check(meta["attempt_id"], "pass", "Passed")
        with self.assertRaises(ValueError):
            self.session.record_check(meta["attempt_id"], "pass", "Passed again")
        self.assertEqual(self.session.summary()["checks_passed"], 1)


if __name__ == "__main__":
    unittest.main()
