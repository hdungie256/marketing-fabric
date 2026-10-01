import ast
import sys
from pathlib import Path

from fabric_control import load_registry

ROOT = Path(__file__).resolve().parent.parent


def declared_outputs(path: Path) -> list[str] | None:
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "OUTPUTS" for t in node.targets):
            return ast.literal_eval(node.value)
    return None


def main() -> int:
    registry = load_registry()
    errors = []
    for path in sorted((ROOT / "pipelines" / "jobs").rglob("job.py")):
        if "_templates" in path.parts:
            continue
        outputs = declared_outputs(path)
        if outputs is None:
            errors.append(f"{path.relative_to(ROOT)}: OUTPUTS not declared")
            continue
        errors += [f"{path.relative_to(ROOT)}: {o} not in registry" for o in outputs if o not in registry]
    print("\n".join(errors) or "registry ok")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
