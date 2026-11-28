"""Click public API and extension-point surface map. Owner: Akshat."""
from __future__ import annotations

import ast
from pathlib import Path

from factory import adapter_click
from factory.llm import llm, load_prompt
from factory.schema import RepoPin


def extract_public_names(init_path: Path) -> list[str]:
    """Return sorted public names imported in click's __init__.py via AST."""
    tree = ast.parse(init_path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module != "__future__":
            for alias in node.names:
                exported = alias.asname or alias.name
                if not exported.startswith("_"):
                    names.append(exported)
    return sorted(set(names))


def _core_excerpts(repo: Path) -> str:
    core = (repo / "src" / "click" / "core.py").read_text(encoding="utf-8").splitlines()
    markers = ("class ParameterSource", "class Context", "class Command", "class Group", "class Parameter(", "class Option(")
    snippets: list[str] = []
    for idx, line in enumerate(core):
        if any(line.startswith(m) for m in markers):
            snippets.append(f"# line {idx + 1}\n" + "\n".join(core[idx : idx + 25]))
    return "\n\n".join(snippets)


def discover_surface(pin: RepoPin) -> str:
    """Return a concise summary of click's public API and extension points."""
    cache_path = adapter_click._runs() / f"surface_{pin.sha}.md"
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    repo = adapter_click.repo_dir(pin)
    public_names = extract_public_names(repo / "src" / "click" / "__init__.py")
    excerpts = _core_excerpts(repo)
    prompt = load_prompt(
        "propose",
        "surface",
        tag=pin.tag,
        sha=pin.sha,
        public_names=", ".join(public_names),
        excerpts=excerpts,
    )
    summary = llm(prompt, role="surface")
    result = (
        f"# Click Surface Map ({pin.tag} @ {pin.sha[:12]})\n\n"
        f"## Public API (`click/__init__.py`)\n\n"
        + ", ".join(public_names)
        + "\n\n## Extension Points\n\n"
        + summary.strip()
        + "\n"
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(result, encoding="utf-8")
    return result
