"""Protected owner requirements and executable applicability/oracle evaluation."""
from __future__ import annotations

from .common import PACKAGE, read, require


def catalog():
    return read(PACKAGE / "catalog" / "owners.json")


def applicable(owner, subject):
    if owner in (4, 7):
        # Unknown frontier status takes the stricter path; G6 uses this same predicate.
        return subject["frontier"] != "OFF" or subject["autonomy"] >= 2
    return True


def requirements(subject):
    return [case for owner in catalog() if applicable(owner["owner"], subject) for case in owner["cases"]]


def evaluate(case, observation, limits):
    """A missing metric never means zero. Thresholds come from the pinned profile."""
    require(set(observation) == {metric["field"] for metric in case["metrics"]}, "missing or unexpected observation fields")
    failures = []
    for metric in case["metrics"]:
        value = observation[metric["field"]]
        expected = limits[metric["limit"]] if "limit" in metric else metric["expected"]
        if metric["op"] == "eq":
            good = type(value) is type(expected) and value == expected
        else:
            require(type(value) in (int, float), "numeric metric required")
            good = value <= expected if metric["op"] == "le" else value >= expected
        if not good:
            failures.append(metric["field"])
    return failures
