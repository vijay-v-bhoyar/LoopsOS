from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tarfile
from pathlib import Path
from typing import Any


DIGEST_PATTERN = re.compile(r"^sha256:([0-9a-f]{64})$")
ATTESTATION_TYPE = "attestation-manifest"


class EvidenceError(RuntimeError):
    pass


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_member(archive: tarfile.TarFile, name: str) -> bytes:
    candidates = (name, f"./{name}")
    for candidate in candidates:
        try:
            member = archive.getmember(candidate)
        except KeyError:
            continue
        if not member.isfile():
            raise EvidenceError(f"OCI member is not a regular file: {name}.")
        extracted = archive.extractfile(member)
        if extracted is None:
            raise EvidenceError(f"OCI member could not be read: {name}.")
        return extracted.read()
    raise EvidenceError(f"OCI archive is missing {name}.")


def _json_bytes(content: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvidenceError(f"{label} is not valid JSON.") from error
    if not isinstance(value, dict):
        raise EvidenceError(f"{label} must be a JSON object.")
    return value


def _blob(archive: tarfile.TarFile, digest: str) -> dict[str, Any]:
    match = DIGEST_PATTERN.fullmatch(digest)
    if not match:
        raise EvidenceError(f"OCI descriptor has an invalid digest: {digest}.")
    content = _archive_member(archive, f"blobs/sha256/{match.group(1)}")
    actual = hashlib.sha256(content).hexdigest()
    if actual != match.group(1):
        raise EvidenceError(f"OCI blob digest mismatch for {digest}.")
    return _json_bytes(content, digest)


def _is_attestation(descriptor: dict[str, Any]) -> bool:
    annotations = descriptor.get("annotations")
    platform = descriptor.get("platform")
    return bool(
        isinstance(annotations, dict)
        and annotations.get("vnd.docker.reference.type") == ATTESTATION_TYPE
    ) or bool(
        isinstance(platform, dict)
        and platform.get("architecture") == "unknown"
        and platform.get("os") == "unknown"
    )


def verify_oci_archive(path: Path) -> dict[str, Any]:
    archive_sha256 = _file_sha256(path)
    try:
        archive = tarfile.open(path, "r:*")
    except (OSError, tarfile.TarError) as error:
        raise EvidenceError(f"{path.name} is not a readable OCI archive.") from error
    with archive:
        layout = _json_bytes(_archive_member(archive, "oci-layout"), "oci-layout")
        if layout.get("imageLayoutVersion") != "1.0.0":
            raise EvidenceError("OCI layout version must be 1.0.0.")
        index = _json_bytes(_archive_member(archive, "index.json"), "index.json")
        manifests = index.get("manifests")
        if not isinstance(manifests, list):
            raise EvidenceError("OCI index must contain a manifests array.")
        image_descriptors = [
            descriptor
            for descriptor in manifests
            if isinstance(descriptor, dict) and not _is_attestation(descriptor)
        ]
        attestation_descriptors = [
            descriptor
            for descriptor in manifests
            if isinstance(descriptor, dict) and _is_attestation(descriptor)
        ]
        if len(image_descriptors) != 1:
            raise EvidenceError(f"Expected one image manifest, found {len(image_descriptors)}.")
        image_digest = image_descriptors[0].get("digest")
        if not isinstance(image_digest, str):
            raise EvidenceError("Image manifest descriptor is missing its digest.")
        _blob(archive, image_digest)
        if not attestation_descriptors:
            raise EvidenceError("OCI archive does not contain an attestation manifest.")

        predicate_types: set[str] = set()
        bound_attestations = 0
        for descriptor in attestation_descriptors:
            annotations = descriptor.get("annotations")
            reference_digest = annotations.get("vnd.docker.reference.digest") if isinstance(annotations, dict) else None
            if reference_digest != image_digest:
                continue
            digest = descriptor.get("digest")
            if not isinstance(digest, str):
                raise EvidenceError("Attestation manifest descriptor is missing its digest.")
            manifest = _blob(archive, digest)
            layers = manifest.get("layers")
            if not isinstance(layers, list):
                raise EvidenceError("Attestation manifest must contain layers.")
            bound_attestations += 1
            for layer in layers:
                if not isinstance(layer, dict):
                    continue
                layer_digest = layer.get("digest")
                if not isinstance(layer_digest, str):
                    continue
                statement = _blob(archive, layer_digest)
                predicate_type = statement.get("predicateType")
                if isinstance(predicate_type, str):
                    predicate_types.add(predicate_type)

        if not bound_attestations:
            raise EvidenceError("No attestation manifest is bound to the image digest.")
        sbom_predicates = sorted(
            predicate for predicate in predicate_types
            if "spdx" in predicate.lower() or "cyclonedx" in predicate.lower()
        )
        provenance_predicates = sorted(
            predicate for predicate in predicate_types
            if "slsa.dev/provenance" in predicate.lower()
        )
        if not sbom_predicates:
            raise EvidenceError("OCI archive is missing an embedded SBOM attestation.")
        if not provenance_predicates:
            raise EvidenceError("OCI archive is missing an embedded provenance attestation.")

    return {
        "archive": path.name,
        "archive_sha256": archive_sha256,
        "image_digest": image_digest,
        "sbom_predicate": sbom_predicates[0],
        "provenance_predicate": provenance_predicates[0],
        "verified": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify SBOM and provenance attestations in OCI image archives.")
    parser.add_argument("archives", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    report: dict[str, Any] = {"schema_version": 1, "verified": False, "artifacts": []}
    try:
        report["artifacts"] = [verify_oci_archive(path) for path in args.archives]
        report["verified"] = True
    except EvidenceError as error:
        report["error"] = str(error)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
