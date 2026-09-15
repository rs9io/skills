#!/usr/bin/env python3
"""Apply FILE/FIND/REPLACE WITH edit blocks from a cascade rung's reply.

Strict on purpose: an edit applies only if its FIND text matches exactly once.
A miss is rung evidence, not something to fuzzy-match around, the judge
(the calling chat model) decides whether to retry, hand-apply, or escalate.

Usage: cascade_apply.py <repo-root> <reply-file>
Exit: 0 all edits applied, 1 any failed.
"""
import re
import sys
from pathlib import Path


def parse(text: str) -> list[dict]:
    # Models often wrap output in code fences; strip fence lines only.
    text = re.sub(r"^```[a-zA-Z]*\s*$", "", text, flags=re.M)
    blocks: list[dict] = []
    cur = None
    mode = None
    saw_replace = False
    for line in text.splitlines():
        if line.startswith("FILE:"):
            if cur:
                if not saw_replace:
                    raise ValueError("Incomplete edit block: missing REPLACE WITH marker")
                blocks.append(cur)
            cur = {"file": line[5:].strip(), "find": [], "replace": []}
            mode = None
            saw_replace = False
        elif cur is not None and line.startswith("FIND:"):
            if mode is not None:
                raise ValueError("Duplicate or misplaced FIND marker")
            mode = "find"
            rest = line[5:].strip()
            if rest:
                cur[mode].append(rest)
        elif cur is not None and line.startswith("REPLACE WITH:"):
            if mode != "find":
                raise ValueError("REPLACE WITH must follow FIND")
            saw_replace = True
            mode = "replace"
            rest = line[13:].strip()
            if rest:
                cur[mode].append(rest)
        elif cur is not None and mode:
            cur[mode].append(line)
    if cur:
        if not saw_replace:
            raise ValueError("Incomplete edit block: missing REPLACE WITH marker")
        blocks.append(cur)
    return blocks


def apply(root: Path, text: str) -> None:
    root = root.resolve()
    blocks = parse(text)
    if not blocks:
        raise ValueError("No edit blocks found")
    pending = {}
    originals = {}
    for block in blocks:
        relative = Path(block["file"])
        path = (root / relative).resolve()
        if relative.is_absolute() or not path.is_relative_to(root):
            raise ValueError("Edit path must stay inside the repository")
        if not path.is_file():
            raise ValueError(f"Missing target file: {block['file']}")
        if path not in pending:
            originals[path] = path.read_text()
            pending[path] = originals[path]
        find = "\n".join(block["find"]).strip("\n")
        replacement = "\n".join(block["replace"]).strip("\n")
        if not find or pending[path].count(find) != 1:
            raise ValueError(f"FIND must match exactly once: {block['file']}")
        pending[path] = pending[path].replace(find, replacement, 1)
    for path, original in originals.items():
        if path.read_text() != original:
            raise ValueError("A target changed during validation; retry against the current file")
    for path, content in pending.items():
        path.write_text(content)
        print(f"ok {path.relative_to(root)}")


def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: cascade_apply.py <repo-root> <reply-file>")
    try:
        apply(Path(sys.argv[1]), Path(sys.argv[2]).read_text())
    except (OSError, ValueError) as error:
        sys.exit(str(error))


if __name__ == "__main__":
    main()
