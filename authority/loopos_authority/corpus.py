from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


RISK_ORDER = {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4}


@dataclass(frozen=True)
class Corpus:
    state_machine: dict[str, Any]
    loop_descriptors: dict[str, dict[str, Any]]
    tool_contracts: dict[str, dict[str, Any]]
    probes: dict[str, dict[str, Any]]
    standard_hash: str

    @classmethod
    def load(cls, repo_root: Path) -> "Corpus":
        state_machine = _yaml(repo_root / "runtime" / "state_machine.yaml")
        contracts_document = _yaml(repo_root / "runtime" / "tool_contracts.yaml")
        probes_document = _yaml(repo_root / "probes" / "PROBE_REGISTRY.yaml")
        descriptors = {}
        for path in sorted((repo_root / "runtime" / "loop-descriptors").glob("*.yaml")):
            descriptor = _yaml(path)
            descriptors[descriptor["loop_id"]] = descriptor
        source = _yaml(repo_root / "standards" / "STANDARD_SOURCE.yaml")
        standard_hash = str(source.get("sha256") or source.get("hash") or "")
        vendored_path = repo_root / str(source.get("vendored_path") or "standards/production-grade-continuous-improvement-loop.md")
        if not vendored_path.is_file():
            raise ValueError(f"The vendored standard is missing: {vendored_path}")
        actual_standard_hash = hashlib.sha256(vendored_path.read_bytes()).hexdigest()
        if standard_hash != actual_standard_hash:
            raise ValueError("The vendored standard hash does not match STANDARD_SOURCE.yaml.")
        corpus = cls(
            state_machine=state_machine,
            loop_descriptors=descriptors,
            tool_contracts={item["tool"]: item for item in contracts_document.get("contracts", [])},
            probes={item["probe_id"]: item for item in probes_document.get("probes", [])},
            standard_hash=standard_hash,
        )
        corpus.validate()
        return corpus

    def validate(self) -> None:
        if len(self.loop_descriptors) != 108:
            raise ValueError(f"Expected 108 loop descriptors, found {len(self.loop_descriptors)}.")
        if not self.standard_hash:
            raise ValueError("The vendored standard hash is missing.")
        if self.state_machine.get("invariant") != "ACTION_APPLIED is never equivalent to EFFECTIVENESS_PROVEN":
            raise ValueError("The action/effectiveness invariant is missing.")

    def allows_transition(self, from_state: str, to_state: str) -> bool:
        return to_state in self.state_machine.get("allowed_transitions", {}).get(from_state, [])

    def is_terminal(self, state: str) -> bool:
        return state in set(self.state_machine.get("terminal_states", []))

    def baseline_risk(self, loop_id: str) -> str:
        descriptor = self.loop_descriptors.get(loop_id)
        if not descriptor:
            raise KeyError(loop_id)
        return str(descriptor["risk"]["baseline_tier"])

    def effective_risk(self, loop_id: str, requested: str) -> str:
        baseline = self.baseline_risk(loop_id)
        if requested not in RISK_ORDER:
            raise ValueError(f"Unknown risk tier: {requested}")
        return requested if RISK_ORDER[requested] >= RISK_ORDER[baseline] else baseline

    def descriptor_hash(self, loop_id: str) -> str:
        descriptor = self.loop_descriptors[loop_id]
        return hashlib.sha256(yaml.safe_dump(descriptor, sort_keys=True).encode("utf-8")).hexdigest()


def _yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected mapping in {path}")
    return value
