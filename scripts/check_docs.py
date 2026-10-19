"""Check Markdown headings and local links without network access.

Run: python scripts/check_docs.py
Generated results and local research caches are outside this documentation check.
"""

from collections import Counter
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def markdown_lines(path):
    """Yield text outside fenced code blocks with its original line number."""
    fence = None
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            continue
        if fence is None:
            yield number, line


def anchors(path):
    """Generate GitHub-style anchors for ordinary headings used in this repo."""
    counts = Counter()
    result = set()
    for _, line in markdown_lines(path):
        heading = HEADING.match(line)
        if heading:
            label = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", heading[2])
            slug = re.sub(r"[^\w\- ]", "", label.lower()).replace(" ", "-")
            occurrence = counts[slug]
            result.add(f"{slug}-{occurrence}" if occurrence else slug)
            counts[slug] += 1
    return result


def main():
    documents = sorted([*ROOT.glob("*.md"), *(ROOT / "docs").rglob("*.md")])
    errors = []
    for document in documents:
        lines = list(markdown_lines(document))
        headings = [HEADING.match(line) for _, line in lines]
        if sum(bool(heading and len(heading[1]) == 1) for heading in headings) != 1:
            errors.append(f"{document.relative_to(ROOT)}: expected one top-level heading")
        for number, line in lines:
            for match in LINK.finditer(line):
                target = match[1].strip().strip("<>")
                parts = urlsplit(target)
                if parts.scheme or parts.netloc:
                    continue
                path = (document.parent / unquote(parts.path)).resolve() if parts.path else document
                prefix = f"{document.relative_to(ROOT)}:{number}: {target}"
                if not path.exists():
                    errors.append(f"{prefix}: missing local target")
                elif parts.fragment and path.suffix.lower() == ".md":
                    if unquote(parts.fragment) not in anchors(path):
                        errors.append(f"{prefix}: missing heading anchor")
    for error in errors:
        print(error)
    print(f"Checked {len(documents)} Markdown files; {len(errors)} errors")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
