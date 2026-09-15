"""Check an OKF v0.2 bundle for conformance.

Run from prjLLMWikiTest/:
    uv run --with pyyaml tools/lint_okf.py [bundle-path]
"""

import re
import sys
from pathlib import Path

import yaml

RESERVED = {"index.md", "log.md"}
LINK = re.compile(r"\[[^\]]*\]\((/[^)\s]+)\)")
DEFAULT_BUNDLE = Path("app/CyrpusLLMWikiAgent/wiki")


def split_frontmatter(text: str):
    """Return (frontmatter dict, body) or (None, text) if there is no valid block."""
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None, text
    if not isinstance(data, dict):
        return None, text
    return data, parts[2]


def lint(bundle: Path):
    errors, warnings = [], []
    root_index = bundle / "index.md"
    if not root_index.exists():
        errors.append("index.md: bundle root index.md is missing")
    else:
        fm, _ = split_frontmatter(root_index.read_text(encoding="utf-8"))
        if not fm or str(fm.get("okf_version", "")) != "0.2":
            errors.append('index.md: bundle root must declare okf_version: "0.2"')

    for path in sorted(bundle.rglob("*.md")):
        rel = "/" + path.relative_to(bundle).as_posix()
        text = path.read_text(encoding="utf-8")
        fm, body = split_frontmatter(text)
        if path.name not in RESERVED:
            if fm is None:
                errors.append(f"{rel}: no parseable YAML frontmatter")
                body = text
            elif not str(fm.get("type", "")).strip():
                errors.append(f"{rel}: missing or empty `type`")
        for target in LINK.findall(body or ""):
            if not (bundle / target.lstrip("/")).exists():
                warnings.append(f"{rel}: broken link -> {target}")
    return errors, warnings


def main() -> int:
    bundle = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_BUNDLE
    errors, warnings = lint(bundle)
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s) in {bundle}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
