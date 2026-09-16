#!/usr/bin/env python3
"""Count coding requests with DeepSeek's native templates and tokenizers."""
from functools import lru_cache
import hashlib
from pathlib import Path
import urllib.request

ROOT = Path.home() / ".local/share/triple-escalator/tokenizers"
REVISION = "8cadfede7063c896b944e7bae05daa3549ae97ea"
FILES = {
    "v41": "81f64d1248a68ce3663e07ab3ee48b851e5df0e32d27cb98e4c9a268151e8d99",
    "v4": "97d2f31b020d18b5aee5c9b3d5b4efb10ea210f3fe3f7dffe3f1cd90542d6b19",
}
MODELS = {"deepseek/deepseek-v4.1-flash": "v41", "deepseek/deepseek-v4-pro": "v4"}


def verified_file(version):
    path = ROOT / (version + ".json")
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != FILES[version]:
        raise ValueError("Native tokenizer missing or invalid. Run cascade_tokens.py --setup; see references/sessions.md.")
    return path


@lru_cache(maxsize=2)
def encoding(model):
    try:
        from deepseek_recipe import DeepseekV4Encoding, DeepseekV41Encoding, Tokenizer
    except ImportError as error:
        raise ValueError("Activate the tokenizer Python environment with deepseek-recipe==0.1.1; see references/sessions.md.") from error
    if model not in MODELS:
        raise ValueError("No native tokenizer configured for this model.")
    kind = DeepseekV41Encoding if MODELS[model] == "v41" else DeepseekV4Encoding
    return kind().with_tokenizer(Tokenizer.from_file(str(verified_file(MODELS[model]))))


def input_tokens(model, request):
    """Count messages and tools, without JSON stringifying the request as a message.

    This is a local native-template count, not a claim about billed provider usage.
    Provider-specific framing can differ. Unsupported content fails before sending.
    """
    native = encoding(model)
    from deepseek_recipe import ChatCompletionRequest, ConversionOptions
    try:
        conversation = ChatCompletionRequest(normalized_request(request)).convert(ConversionOptions()).conversation
        rendered = native.render_conversation(conversation)
        if rendered.image_sources:
            raise ValueError("Image context accounting is not supported by the coding runner.")
        return len(native.encode(conversation))
    except Exception as error:
        # Conversion errors can include source content; keep it out of metadata.
        raise ValueError("Native token counting failed for this request; inspect the local worker transcript.") from error


def normalized_request(request):
    """Translate OpenRouter reasoning for counting only; never alter the wire body."""
    messages = []
    for original in request.get("messages", []):
        message = dict(original)
        if message.get("function_call") or message.get("refusal"):
            raise ValueError("Unsupported legacy call or refusal representation")
        candidates = [message[key] for key in ("reasoning_content", "reasoning") if message.get(key)]
        details = message.get("reasoning_details") or []
        if not isinstance(details, list):
            raise ValueError("Unsupported reasoning details")
        if details:
            if any(item.get("type") != "reasoning.text" or not isinstance(item.get("text"), str) for item in details):
                raise ValueError("Unsupported reasoning details")
            candidates.append("".join(item["text"] for item in details))
        if candidates:
            if any(not isinstance(value, str) or value != candidates[0] for value in candidates):
                raise ValueError("Ambiguous reasoning representations")
            message["reasoning_content"] = candidates[0]
        message.pop("reasoning", None)
        message.pop("reasoning_details", None)
        content = message.get("content")
        if isinstance(content, list) and any(part.get("type") != "text" for part in content):
            raise ValueError("Only text content is supported by the coding counter")
        messages.append(message)
    return {**request, "messages": messages}


def setup():
    """Explicit setup only. No network or downloads during token counting."""
    ROOT.mkdir(parents=True, exist_ok=True)
    for version, digest in FILES.items():
        try:
            verified_file(version)
            continue
        except ValueError:
            pass
        url = f"https://raw.githubusercontent.com/deepseek-ai/deepseek-recipe/{REVISION}/static/tokenizers/{version}/tokenizer.json"
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Downloaded tokenizer checksum does not match the pinned version.")
        path = ROOT / (version + ".json")
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(data)
        temporary.replace(path)
    print("Native Flash and Pro tokenizers are ready.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup", action="store_true", required=True)
    parser.parse_args()
    setup()
