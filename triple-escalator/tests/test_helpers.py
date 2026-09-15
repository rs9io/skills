import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import io

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


applier = load('cascade_apply')
sys.modules['cascade_apply'] = applier
runner = load('cascade_run')


class Helpers(unittest.TestCase):
    def test_provider_list_is_required(self):
        with self.assertRaises(ValueError):
            runner.provider_config(ROOT / 'providers.example.json')

    def test_routing_controls_are_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'providers.json'
            p.write_text(json.dumps({'only': ['approved'], 'ignore': ['blocked'], 'zdr': False}))
            routing = runner.provider_config(p)
            self.assertEqual(routing['only'], ['approved'])
            self.assertEqual(routing['ignore'], ['blocked'])
            self.assertEqual(routing['data_collection'], 'deny')
            self.assertIs(routing['zdr'], True)

    def test_final_model_never_calls_api(self):
        with patch('sys.argv', ['runner', 'gpt-6-astra', 'prompt', 'reply']), patch('urllib.request.urlopen') as api, patch('sys.stderr', io.StringIO()):
            with self.assertRaises(SystemExit):
                runner.main()
            api.assert_not_called()

    def invoke_runner(self, finish="stop", content=None, usage=None, extra=()):
        valid = "FILE: example.txt\nFIND:\nbefore\nREPLACE WITH:\nafter"
        body = {"id": "fixture", "provider": "approved", "choices": [{
            "finish_reason": finish, "message": {"content": valid if content is None else content}
        }], "usage": usage}
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            prompt, reply, providers = root / "prompt", root / "reply", root / "providers.json"
            prompt.write_text("Fix the fixture.")
            providers.write_text('{"only":["approved"]}')
            with patch.dict("os.environ", {"OPENROUTER_API_KEY": "fixture-key", "OPENROUTER_PROVIDER_CONFIG": str(providers)}), patch("sys.argv", ["runner", "deepseek/deepseek-v4.1-flash", str(prompt), str(reply), *extra]), patch("urllib.request.urlopen") as api, patch("sys.stdout", io.StringIO()), patch("sys.stderr", io.StringIO()):
                api.return_value.__enter__.return_value = io.StringIO(json.dumps(body))
                result = runner.main()
                payload = json.loads(api.call_args.args[0].data)
            return result, payload, {p.name: p.read_text() for p in root.iterdir()}

    def test_complete_reply_has_no_runner_token_cap(self):
        result, payload, files = self.invoke_runner(usage={"completion_tokens_details": None})
        self.assertEqual(result, 0)
        self.assertNotIn("max_tokens", payload)
        self.assertNotIn("max_completion_tokens", payload)
        self.assertEqual(payload["reasoning"], {"effort": "low"})
        self.assertTrue(payload["provider"]["require_parameters"])
        self.assertIn("reply", files)
        self.assertEqual(json.loads(files["reply.meta.json"])["finish_reason"], "stop")

    def test_truncation_preserves_evidence_without_usable_reply(self):
        result, _, files = self.invoke_runner(finish="length", usage={"completion_tokens": 32000, "completion_tokens_details": {"reasoning_tokens": 20000}})
        self.assertEqual(result, 2)
        self.assertNotIn("reply", files)
        self.assertIn("reply.partial.txt", files)
        metadata = json.loads(files["reply.meta.json"])
        self.assertEqual(metadata["finish_reason"], "length")
        self.assertEqual(metadata["usage"]["completion_tokens_details"]["reasoning_tokens"], 20000)

    def test_empty_and_bad_format_are_not_usable(self):
        for content in ["", "I fixed it."]:
            result, _, files = self.invoke_runner(content=content)
            self.assertEqual(result, 2)
            self.assertNotIn("reply", files)

    def test_incomplete_second_edit_never_becomes_usable(self):
        result, _, files = self.invoke_runner(content="FILE: first.txt\nFIND:\nbefore\nREPLACE WITH:\nafter\nFILE: second.txt\nFIND:\nbefore")
        self.assertEqual(result, 2)
        self.assertNotIn("reply", files)
        self.assertIn("reply.partial.txt", files)

    def test_unsupported_pro_effort_never_calls_api(self):
        with patch("sys.argv", ["runner", "deepseek/deepseek-v4-pro", "prompt", "reply", "--reasoning-effort", "low"]), patch("urllib.request.urlopen") as api, patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit):
                runner.main()
            api.assert_not_called()

    def test_existing_reply_is_preserved_without_api_call(self):
        with tempfile.TemporaryDirectory() as d:
            reply = Path(d) / "reply"
            reply.write_text("previous evidence")
            with patch("sys.argv", ["runner", "deepseek/deepseek-v4.1-flash", "prompt", str(reply)]), patch("urllib.request.urlopen") as api, patch("sys.stderr", io.StringIO()):
                self.assertEqual(runner.main(), 2)
                api.assert_not_called()
            self.assertEqual(reply.read_text(), "previous evidence")

    def test_edit_and_failed_batch(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'example.txt'
            p.write_text('before\n')
            valid = 'FILE: example.txt\nFIND:\nbefore\nREPLACE WITH:\nafter'
            with self.assertRaises(ValueError):
                applier.apply(Path(d), valid + '\nFILE: missing.txt\nFIND:\nx\nREPLACE WITH:\ny')
            self.assertEqual(p.read_text(), 'before\n')
            applier.apply(Path(d), valid)
            self.assertEqual(p.read_text(), 'after\n')

    def test_incomplete_block_cannot_delete_content(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "example.txt"
            target.write_text("before")
            with self.assertRaises(ValueError):
                applier.apply(Path(d), "FILE: example.txt\nFIND:\nbefore")
            self.assertEqual(target.read_text(), "before")

    def test_paths_cannot_escape_repo(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'repo'
            root.mkdir()
            outside = Path(d) / 'outside.txt'
            outside.write_text('before')
            (root / 'link.txt').symlink_to(outside)
            for name in ['../outside.txt', str(outside), 'link.txt']:
                with self.assertRaises(ValueError):
                    applier.apply(root, f'FILE: {name}\nFIND:\nbefore\nREPLACE WITH:\nafter')
            self.assertEqual(outside.read_text(), 'before')


if __name__ == '__main__':
    unittest.main()
