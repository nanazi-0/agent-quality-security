from __future__ import annotations

import re
from typing import Any


class AssertionFailure(ValueError):
    pass


def get_path(value: Any, path: str) -> Any:
    if not path:
        return value
    current = value
    for raw_part in path.split("."):
        match = re.fullmatch(r"([^\[]+)(?:\[(\d+)\])?", raw_part)
        if not match:
            raise AssertionFailure(f"invalid path: {path}")
        key, index = match.groups()
        if not isinstance(current, dict) or key not in current:
            raise AssertionFailure(f"path not found: {path}")
        current = current[key]
        if index is not None:
            if not isinstance(current, list) or int(index) >= len(current):
                raise AssertionFailure(f"array index not found: {path}")
            current = current[int(index)]
    return current


def evaluate(actual: Any, operator: str, expected: Any = None) -> tuple[bool, str]:
    if operator == "equals":
        passed = actual == expected
    elif operator == "not_equals":
        passed = actual != expected
    elif operator == "contains":
        passed = expected in actual
    elif operator == "not_contains":
        passed = expected not in actual
    elif operator == "matches":
        passed = re.search(str(expected), str(actual)) is not None
    elif operator == "not_matches":
        passed = re.search(str(expected), str(actual)) is None
    elif operator == "less_than":
        passed = actual < expected
    elif operator == "less_than_or_equal":
        passed = actual <= expected
    elif operator == "greater_than_or_equal":
        passed = actual >= expected
    elif operator == "exists":
        passed = actual is not None
    else:
        raise AssertionFailure(f"unsupported operator: {operator}")
    detail = f"actual={actual!r} {operator} expected={expected!r}"
    return passed, detail


def run_assertions(document: dict[str, Any], specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for spec in specs:
        path = spec["path"]
        try:
            actual = get_path(document, path)
            passed, detail = evaluate(actual, spec["op"], spec.get("expected"))
        except (AssertionFailure, TypeError, KeyError) as exc:
            passed, detail = False, str(exc)
        results.append({"path": path, "passed": passed, "detail": detail})
    return results

