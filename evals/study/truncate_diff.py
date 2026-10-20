#!/usr/bin/env python3
"""Truncation rule for large diffs shown to the judge (STUDY_PLAN, to be fixed before freezing).

Rule, applied to a unified diff:
1. A summary first: one line per file with its added and deleted line counts, like
   `git diff --stat`, computed from the full diff; so the judge always sees every file.
2. Every `diff --git` header line and every hunk header (`@@ ... @@`) is kept.
3. Each line is cut at --max-line characters, with ` …[+N chars]` appended.
4. Within one file, body lines (context, +, −) are kept up to --max-file-lines; after that
   the hunk headers are still kept and the body is replaced by one line
   `… [N more lines of this file omitted]`.
5. The whole output is capped at --max-total characters as a safety net; if reached, the
   remaining files are listed by name only.

Usage: truncate_diff.py DIFF_FILE [--max-line 300] [--max-file-lines 120] [--max-total 120000]
Prints the truncated diff; --stats prints sizes only.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

HUNK = re.compile(r"^@@ .* @@")


def truncate(text: str, max_line: int, max_file_lines: int, max_total: int) -> str:
    files: list[list[str]] = []
    for line in text.split("\n"):
        if line.startswith("diff --git "):
            files.append([line])
        elif files:
            files[-1].append(line)
        else:
            files.append([line])
    stat = []
    for f in files:
        name = f[0][len("diff --git "):].split(" b/")[-1] if f[0].startswith("diff --git ") else "(preamble)"
        add = sum(1 for l in f[1:] if l.startswith("+") and not l.startswith("+++"))
        dele = sum(1 for l in f[1:] if l.startswith("-") and not l.startswith("---"))
        stat.append(f"{name}: +{add} -{dele}")
    out = [f"# {len(files)} files changed. Summary (added/deleted lines per file):"] + [f"#   {s}" for s in stat] + [
        f"# Below, lines longer than {max_line} characters are cut and each file shows at most "
        f"{max_file_lines} body lines; hunk headers are kept.", ""]
    total = sum(len(l) + 1 for l in out)
    for f in files:
        body = 0
        omitted = 0
        kept: list[str] = []
        for i, line in enumerate(f):
            header = i == 0 or line.startswith(("---", "+++", "index ", "new file", "deleted file", "similarity",
                                                "rename ", "old mode", "new mode", "Binary files")) or HUNK.match(line)
            if not header:
                body += 1
                if body > max_file_lines:
                    omitted += 1
                    continue
            if len(line) > max_line:
                line = line[:max_line] + f" …[+{len(line) - max_line} chars]"
            kept.append(line)
        if omitted:
            kept.append(f"… [{omitted} more lines of this file omitted]")
        chunk = sum(len(l) + 1 for l in kept)
        if total + chunk > max_total:
            out.append(f"{f[0]}\n… [file omitted: output cap reached]")
            total += len(out[-1]) + 1
            continue
        out += kept
        total += chunk
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("diff")
    ap.add_argument("--max-line", type=int, default=300)
    ap.add_argument("--max-file-lines", type=int, default=120)
    ap.add_argument("--max-total", type=int, default=120_000)
    ap.add_argument("--stats", action="store_true")
    o = ap.parse_args()
    text = Path(o.diff).read_text()
    out = truncate(text, o.max_line, o.max_file_lines, o.max_total)
    if o.stats:
        print(f"{o.diff}: {len(text):,} chars / {text.count(chr(10)):,} lines -> {len(out):,} chars / "
              f"{out.count(chr(10)):,} lines (about {len(out) // 4:,} tokens)")
    else:
        print(out)


if __name__ == "__main__":
    main()
