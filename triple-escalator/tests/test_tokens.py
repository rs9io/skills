import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from cascade_tokens import input_tokens
from cascade_run import output_route

FLASH = "deepseek/deepseek-v4.1-flash"
PRO = "deepseek/deepseek-v4-pro"


class NativeTokenTests(unittest.TestCase):
    def test_megabyte_history_fits_actual_context(self):
        request = {"model": FLASH, "messages": [{"role": "user", "content":
                   "Read the source, fix the price, and run the tests.\n" * 24000}]}
        self.assertGreater(len(json.dumps(request).encode()), 1048576)
        tokens = input_tokens(FLASH, request)
        self.assertLess(tokens, 400000)
        routing = {"only": ["fireworks"], "ignore": []}
        catalogue = {"data": {"endpoints": [{"tag": "fireworks", "context_length": 1048576,
                     "max_completion_tokens": 943718, "supported_parameters": ["max_tokens"]}]}}
        _, allowance = output_route(FLASH, routing, "fireworks", [], catalogue, request=request)
        self.assertEqual(allowance, 1048576 - tokens)
        catalogue["data"]["endpoints"][0]["context_length"] = tokens
        with self.assertRaisesRegex(ValueError, "context capacity"):
            output_route(FLASH, routing, "fireworks", [], catalogue, request=request)

    def test_native_multilingual_tools_and_results_for_both_models(self):
        request = {"messages": [{"role": "user", "content": "检查价格 🍷 café"},
                   {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function",
                    "function": {"name": "read", "arguments": '{"file":"商品.ts"}'}}]},
                   {"role": "tool", "tool_call_id": "call_1", "content": "价格 $24.99"}],
                   "tools": [{"type": "function", "function": {"name": "read", "description": "读取源代码",
                             "parameters": {"type": "object", "properties": {"file": {"type": "string"}}}}}]}
        for model in [FLASH, PRO]:
            request["model"] = model
            count = input_tokens(model, request)
            plain = input_tokens(model, {"model": model, "messages": request["messages"][:1]})
            self.assertGreater(count, plain)
            self.assertEqual(count, input_tokens(model, request))

    def test_no_silent_image_or_unknown_model_accounting(self):
        request = {"model": FLASH, "messages": [{"role": "user", "content": [
                   {"type": "image_url", "image_url": {"url": "https://example.test/image.png"}}]}]}
        with self.assertRaises(ValueError):
            input_tokens(FLASH, request)
        with self.assertRaisesRegex(ValueError, "No native tokenizer"):
            input_tokens("unknown", request)

    def test_openrouter_reasoning_counted_once_without_changing_wire_request(self):
        import copy
        thought = "Inspect the failing test first. " * 1000
        messages = [{"role": "user", "content": "fix it"},
                    {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function",
                     "function": {"name": "read", "arguments": "{}"}}]},
                    {"role": "tool", "tool_call_id": "call_1", "content": "source"}]
        request = {"model": FLASH, "messages": messages}
        plain = input_tokens(FLASH, request)
        messages[1]["reasoning_content"] = thought
        native = input_tokens(FLASH, request)
        self.assertGreater(native, plain + 1000)
        del messages[1]["reasoning_content"]
        messages[1]["reasoning"] = thought
        self.assertEqual(input_tokens(FLASH, request), native)
        messages[1]["reasoning_details"] = [{"type": "reasoning.text", "text": thought}]
        before = copy.deepcopy(request)
        self.assertEqual(input_tokens(FLASH, request), native)
        self.assertEqual(request, before)
        messages[1]["reasoning_details"] = [{"type": "reasoning.encrypted", "data": "opaque"}]
        with self.assertRaises(ValueError):
            input_tokens(FLASH, request)


if __name__ == "__main__":
    unittest.main()
