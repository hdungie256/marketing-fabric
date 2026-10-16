"""Guard: every term_id rendered by app code exists in the glossary.

Covers the 2.5 acceptance rule that the suite fails when a page uses an
unknown term_id. Static on purpose: it runs in CI without a live stack.
"""

import ast
from pathlib import Path

from fabric_control.glossary import load_terms

ROOT = Path(__file__).resolve().parents[2]


def used_term_ids() -> set[str]:
    found = set()
    for path in sorted((ROOT / "app").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id == "metric":
                if node.args and isinstance(node.args[0], ast.Constant):
                    found.add(node.args[0].value)
            if isinstance(func, ast.Name) and func.id == "table":
                for keyword in node.keywords:
                    if keyword.arg == "info_terms" and isinstance(keyword.value, ast.Dict):
                        found.update(v.value for v in keyword.value.values if isinstance(v, ast.Constant))
    return found


def test_all_rendered_term_ids_exist_in_glossary():
    used = used_term_ids()
    assert used, "no metric() calls found; scanner is stale"
    assert used <= set(load_terms()), f"unknown term ids: {sorted(used - set(load_terms()))}"
