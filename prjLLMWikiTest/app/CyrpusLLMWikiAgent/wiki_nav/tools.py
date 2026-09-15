"""Read-only navigation over the OKF wiki bundle. pathlib only, no new dependencies.

Every path is resolved under WIKI_ROOT and anything that escapes is rejected, the
same approach as skills/fetcher.py. Failures return guidance text instead of
raising, so a wrong path costs the agent one turn, not the whole answer.
"""

import os
from pathlib import Path

from strands import tool

MAX_HITS = 20


def wiki_root() -> Path:
    """The bundle root. WIKI_ROOT env var, else `wiki/` next to main.py."""
    default = Path(__file__).resolve().parent.parent / "wiki"
    return Path(os.environ.get("WIKI_ROOT", default)).resolve()


def _resolve(path: str):
    """Resolve a bundle path under the root, or None if it escapes."""
    root = wiki_root()
    target = (root / path.strip().lstrip("/")).resolve()
    if target != root and not str(target).startswith(str(root) + os.sep):
        return None
    return target


def _listing(directory: Path) -> str:
    root = wiki_root()
    rel = "/" + directory.relative_to(root).as_posix() if directory != root else "/"
    entries = sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name))
    lines = [f"{p.name}/" if p.is_dir() else p.name for p in entries]
    return f"{rel}\n" + "\n".join(f"  {line}" for line in lines)


@tool
def list_wiki(path: str = "/") -> str:
    """List the directories and files of the Cyprus wiki at a bundle path.

    Args:
        path: Bundle path such as "/" or "/sites". Defaults to the bundle root.
    """
    root = wiki_root()
    target = _resolve(path)
    if target is None:
        return f"'{path}' is outside the wiki. Showing the root instead.\n\n{_listing(root)}"
    while not target.is_dir() and target != root:
        target = target.parent
    return _listing(target)


@tool
def read_wiki(path: str) -> str:
    """Read one Cyprus wiki document, YAML frontmatter included.

    The frontmatter carries type, tags, region and themes. Use them to decide
    which document to open next.

    Args:
        path: Bundle path to a markdown file, such as "/sites/kourion.md".
    """
    root = wiki_root()
    target = _resolve(path)
    if target is None:
        return f"'{path}' is outside the wiki. Showing the root instead.\n\n{_listing(root)}"
    if target.is_file():
        return target.read_text(encoding="utf-8")
    parent = target if target.is_dir() else target.parent
    while not parent.is_dir() and parent != root:
        parent = parent.parent
    return f"'{path}' not found. Here is what that directory holds:\n\n{_listing(parent)}"


@tool
def search_wiki(query: str) -> str:
    """Case-insensitive plain-text search over every Cyprus wiki document.

    Use this only when no link path to the answer is obvious.

    Args:
        query: Text to look for, for example "mosaic" or "Byzantine".
    """
    root = wiki_root()
    needle = query.strip().lower()
    hits = []
    for path in sorted(root.rglob("*.md")):
        rel = "/" + path.relative_to(root).as_posix()
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if needle in line.lower():
                hits.append(f"{rel}:{n}: {line.strip()}")
                if len(hits) >= MAX_HITS:
                    return "\n".join(hits) + f"\n\n(stopped at {MAX_HITS} hits)"
    if not hits:
        return f"no matches for '{query}'. Start from the root instead:\n\n{_listing(root)}"
    return "\n".join(hits)
