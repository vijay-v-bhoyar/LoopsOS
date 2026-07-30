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
INDEX_MEDIA_TYPES = {
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.index.v1+json",
}


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


def _blob_content(archive: tarfile.TarFile, digest: str) -> bytes:
    match = DIGEST_PATTERN.fullmatch(digest)
    if not match:
        raise EvidenceError(f"OCI descriptor has an invalid digest: {digest}.")
    content = _archive_member(archive, f"blobs/sha256/{match.group(1)}")
    actual = hashlib.sha256(content).hexdigest()
    if actual != match.group(1):
        raise EvidenceError(f"OCI blob digest mismatch for {digest}.")
    return content


def _blob(archive: tarfile.TarFile, digest: str) -> dict[str, Any]:
    return _json_bytes(_blob_content(archive, digest), digest)


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


def _leaf_descriptors(
    archive: tarfile.TarFile,
    descriptors: list[Any],
    *,
    visited: set[str] | None = None,
) -> list[dict[str, Any]]:
    if visited is None:
        visited = set()
    leaves: list[dict[str, Any]] = []
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            raise EvidenceError("OCI index descriptors must be JSON objects.")
        digest = descriptor.get("digest")
        if not isinstance(digest, str):
            raise EvidenceError("OCI descriptor is missing its digest.")
        if digest in visited:
            raise EvidenceError(f"OCI descriptor graph contains a cycle at {digest}.")
        content = _blob(archive, digest)
        media_type = descriptor.get("mediaType")
        nested = content.get("manifests")
        if media_type in INDEX_MEDIA_TYPES or isinstance(nested, list):
            if not isinstance(nested, list):
                raise EvidenceError(f"OCI index {digest} must contain a manifests array.")
            visited.add(digest)
            leaves.extend(_leaf_descriptors(archive, nested, visited=visited))
            visited.remove(digest)
        else:
            leaves.append(descriptor)
    return leaves


def verify_oci_archive(path: Path, *, sbom_output: Path | None = None) -> dict[str, Any]:
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
        leaf_descriptors = _leaf_descriptors(archive, manifests)
        image_descriptors = [
            descriptor
            for descriptor in leaf_descriptors
            if not _is_attestation(descriptor)
        ]
        attestation_descriptors = [
            descriptor
            for descriptor in leaf_descriptors
            if _is_attestation(descriptor)
        ]
        if len(image_descriptors) != 1:
            raise EvidenceError(f"Expected one image manifest, found {len(image_descriptors)}.")
        image_digest = image_descriptors[0].get("digest")
        if not isinstance(image_digest, str):
            raise EvidenceError("Image manifest descriptor is missing its digest.")
        image_manifest = _blob(archive, image_digest)
        config_descriptor = image_manifest.get("config")
        if not isinstance(config_descriptor, dict) or not isinstance(config_descriptor.get("digest"), str):
            raise EvidenceError("Image manifest is missing its config digest.")
        config_digest = config_descriptor["digest"]
        _blob(archive, config_digest)
        image_layers = image_manifest.get("layers")
        if not isinstance(image_layers, list):
            raise EvidenceError("Image manifest must contain a layers array.")
        for layer in image_layers:
            if not isinstance(layer, dict) or not isinstance(layer.get("digest"), str):
                raise EvidenceError("Image manifest contains a layer without a digest.")
            _blob_content(archive, layer["digest"])
        if not attestation_descriptors:
            raise EvidenceError("OCI archive does not contain an attestation manifest.")

        predicate_types: set[str] = set()
        sbom_documents: list[tuple[str, dict[str, Any]]] = []
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
                    if "spdx" in predicate_type.lower() or "cyclonedx" in predicate_type.lower():
                        predicate = statement.get("predicate")
                        if not isinstance(predicate, dict):
                            raise EvidenceError(f"SBOM attestation {layer_digest} has no JSON object predicate.")
                        sbom_documents.append((predicate_type, predicate))

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
        if sbom_output is not None:
            sbom_output.parent.mkdir(parents=True, exist_ok=True)
            sbom_output.write_text(
                json.dumps(sbom_documents[0][1], indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    return {
        "archive": path.name,
        "archive_sha256": archive_sha256,
        "config_digest": config_digest,
        "image_digest": image_digest,
        "sbom_file": sbom_output.name if sbom_output is not None else None,
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
        artifacts = []
        for path in args.archives:
            archive_name = path.name.removesuffix(".oci.tar")
            sbom_output = args.output.parent / f"{archive_name}.sbom.spdx.json"
            artifacts.append(verify_oci_archive(path, sbom_output=sbom_output))
        report["artifacts"] = artifacts
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
