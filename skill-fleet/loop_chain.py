"""Safe-local proof that a governed product goal has one build engine and one subject."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


class ChainError(ValueError):
    pass


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(chain: dict[str, Any], root: Path) -> dict[str, Any]:
    goal = chain.get("goal")
    if not isinstance(goal, dict) or not isinstance(goal.get("id"), str) or not goal.get("criteria"):
        raise ChainError("goal requires id and criteria")
    engines = chain.get("delivery_engines")
    if not isinstance(engines, list) or len(engines) != 1:
        raise ChainError("exactly one selected delivery engine is required")
    stages = chain.get("stages")
    expected = ("vision", "build", "assurance", "release")
    if not isinstance(stages, list) or tuple(stage.get("kind") for stage in stages) != expected:
        raise ChainError("stages must be vision, build, assurance, release in order")
    for stage in stages:
        if stage.get("goal") != goal["id"]:
            raise ChainError(f"{stage.get('kind')}: parent goal mismatch")
        artifact = stage.get("artifact")
        if not isinstance(artifact, dict):
            raise ChainError(f"{stage.get('kind')}: artifact required")
        path = (root / artifact.get("path", "")).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ChainError(f"{stage.get('kind')}: artifact missing or escapes root")
        if artifact.get("sha256") != digest(path):
            raise ChainError(f"{stage.get('kind')}: artifact digest mismatch")
    if stages[1].get("engine") != engines[0]:
        raise ChainError("build stage engine does not match selected engine")
    if stages[2].get("result") != "GOAL_VERIFIED":
        raise ChainError("assurance has not independently verified the goal")
    if stages[3].get("decision") not in {"NO_GO", "ESCALATE"}:
        raise ChainError("safe-local release stage must remain fail-closed")
    return {"status": "CHAIN_VERIFIED", "goal": goal["id"], "engine": engines[0], "release": stages[3]["decision"]}
