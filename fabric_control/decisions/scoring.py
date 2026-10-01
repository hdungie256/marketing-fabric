from fabric_control.models import DataQualityResult, Status

PASS_THRESHOLD = 90.0


def score(result: DataQualityResult) -> tuple[float, Status]:
    if not result.rules:
        return 100.0, "Green"
    passed = sum(r.passed for r in result.rules)
    pct = round(100.0 * passed / len(result.rules), 2)
    if any(r.severity == "critical" and not r.passed for r in result.rules):
        return pct, "Red"
    return pct, "Green" if pct >= PASS_THRESHOLD else "Amber"
