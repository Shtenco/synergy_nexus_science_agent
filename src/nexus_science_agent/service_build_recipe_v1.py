from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile
from typing import Any


class ScienceBuildError(ValueError):
    pass


EXPECTED_RECIPE_DIGEST = "3b1f7a64a943a0a144a52ead894c1e0c2d454e67657992ebcb434a6fdcd18c78"
EXPECTED_SOURCE_COMMIT = "0607690c3036d2fdce2ac3e044094a8e4da0311b"
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def canonical_json(value: Any) -> bytes:
    def check(v: Any) -> None:
        if v is None or isinstance(v, (str, bool)):
            return
        if isinstance(v, int) and not isinstance(v, bool):
            if abs(v) > 2**53 - 1:
                raise ScienceBuildError("unsafe integer")
            return
        if isinstance(v, float):
            raise ScienceBuildError("floats forbidden")
        if isinstance(v, list):
            for item in v:
                check(item)
            return
        if isinstance(v, dict):
            if any(not isinstance(k, str) for k in v):
                raise ScienceBuildError("object keys must be strings")
            for item in v.values():
                check(item)
            return
        raise ScienceBuildError("unsupported canonical value")

    check(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest_without(payload: dict[str, Any], field: str) -> str:
    body = dict(payload)
    body.pop(field, None)
    return hashlib.sha256(canonical_json(body)).hexdigest()


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def _safe_relpath(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ScienceBuildError("empty path")
    path = PurePosixPath(value)
    if path.is_absolute() or "." in path.parts or ".." in path.parts:
        raise ScienceBuildError("unsafe build path")
    return path


def verify_recipe(payload: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "schema", "recipe_id", "source_repository", "source_commit",
        "service_descriptor_path", "include_files", "excluded_network_modules",
        "archive_profile", "dependency_contract", "dependency_lock_status",
        "artifact_semantics", "service_roles", "network_retrieval_capability",
        "scientific_truth_authority", "build_authority", "execution_authority",
        "recipe_digest",
    }
    if not isinstance(payload, dict) or set(payload) != expected:
        raise ScienceBuildError("unexpected recipe shape")
    if payload["schema"] != "nexus-science.service-build-recipe/v1":
        raise ScienceBuildError("unexpected recipe schema")
    if payload["source_repository"] != "Shtenco/nexus_science_agent" or payload["source_commit"] != EXPECTED_SOURCE_COMMIT:
        raise ScienceBuildError("source identity drift")
    if payload["service_descriptor_path"] != "config/science_service_descriptor_v1.json":
        raise ScienceBuildError("service descriptor drift")
    if payload["excluded_network_modules"] != ["src/nexus_science_agent/retrieval.py"]:
        raise ScienceBuildError("network-module exclusion drift")
    if payload["dependency_contract"] != "PYTHON_STDLIB_ONLY" or payload["dependency_lock_status"] != "STDLIB_ONLY_NO_THIRD_PARTY_RUNTIME_DEPENDENCIES":
        raise ScienceBuildError("unexpected dependency contract")
    if payload["artifact_semantics"] != "LOCAL_RESEARCH_SERVICE_SOURCE_PACKAGE_CANDIDATE":
        raise ScienceBuildError("artifact semantics drift")
    if payload["service_roles"] != ["SCIENCE_AGENT"]:
        raise ScienceBuildError("service role drift")
    if payload["network_retrieval_capability"] != "EXCLUDED_FROM_ARTIFACT_V1":
        raise ScienceBuildError("network retrieval must remain excluded")
    if payload["scientific_truth_authority"] != "NONE" or payload["build_authority"] != "SOURCE_REPOSITORY_ONLY" or payload["execution_authority"] != "NONE":
        raise ScienceBuildError("forbidden authority")
    if payload["archive_profile"] != {
        "format": "ZIP_STORED",
        "entry_order": "LEXICOGRAPHIC_PATH",
        "fixed_timestamp": "1980-01-01T00:00:00Z",
        "file_mode": "0644",
        "strip_extra_fields": True,
    }:
        raise ScienceBuildError("archive profile drift")
    files = payload["include_files"]
    if not isinstance(files, list) or not files:
        raise ScienceBuildError("include_files required")
    paths: list[str] = []
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "git_blob_sha"}:
            raise ScienceBuildError("unexpected include file shape")
        path = str(_safe_relpath(item["path"]))
        sha = item["git_blob_sha"]
        if not isinstance(sha, str) or len(sha) != 40 or sha.lower() != sha:
            raise ScienceBuildError("invalid git blob sha")
        try:
            int(sha, 16)
        except ValueError as exc:
            raise ScienceBuildError("git blob sha must be hex") from exc
        paths.append(path)
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ScienceBuildError("include files must be sorted and unique")
    if payload["service_descriptor_path"] not in set(paths):
        raise ScienceBuildError("service descriptor must be packaged")
    if any(path in set(paths) for path in payload["excluded_network_modules"]):
        raise ScienceBuildError("network retrieval module cannot be packaged")
    if _digest_without(payload, "recipe_digest") != payload["recipe_digest"] or payload["recipe_digest"] != EXPECTED_RECIPE_DIGEST:
        raise ScienceBuildError("recipe digest mismatch")
    canonical_json(payload)
    return payload


@dataclass(frozen=True)
class VerifiedFile:
    path: str
    size: int
    sha256: str
    git_blob_sha: str
    data: bytes


def verify_source_tree(root: Path, recipe: dict[str, Any]) -> tuple[VerifiedFile, ...]:
    verify_recipe(recipe)
    root = root.resolve()
    out: list[VerifiedFile] = []
    for item in recipe["include_files"]:
        rel = _safe_relpath(item["path"])
        candidate = root.joinpath(*rel.parts)
        if candidate.is_symlink() or not candidate.is_file():
            raise ScienceBuildError(f"missing or unsafe source file: {rel}")
        resolved = candidate.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ScienceBuildError(f"source path escapes root: {rel}") from exc
        data = resolved.read_bytes()
        blob = git_blob_sha(data)
        if blob != item["git_blob_sha"]:
            raise ScienceBuildError(f"source blob drift: {rel}")
        out.append(VerifiedFile(str(rel), len(data), hashlib.sha256(data).hexdigest(), blob, data))
    return tuple(out)


def build_local_science_archive(root: Path, recipe: dict[str, Any], output: Path) -> dict[str, Any]:
    files = verify_source_tree(root, recipe)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED, strict_timestamps=True) as zf:
        for item in files:
            info = zipfile.ZipInfo(item.path, date_time=FIXED_ZIP_TIME)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o100644 << 16
            info.extra = b""
            info.comment = b""
            zf.writestr(info, item.data)
    artifact = output.read_bytes()
    evidence = {
        "schema": "nexus-science.service-build-artifact/v1",
        "recipe_digest": recipe["recipe_digest"],
        "source_repository": recipe["source_repository"],
        "source_commit": recipe["source_commit"],
        "service_roles": recipe["service_roles"],
        "artifact_sha256": hashlib.sha256(artifact).hexdigest(),
        "artifact_bytes": len(artifact),
        "files": [
            {"path": f.path, "size": f.size, "sha256": f.sha256, "git_blob_sha": f.git_blob_sha}
            for f in files
        ],
        "network_retrieval_capability": recipe["network_retrieval_capability"],
        "dependency_lock_status": recipe["dependency_lock_status"],
        "test_evidence_status": "NOT_ATTESTED",
        "build_status": "ARTIFACT_BUILT_TEST_EVIDENCE_PENDING",
        "scientific_truth_authority": "NONE",
        "execution_authority": "NONE",
    }
    evidence["evidence_digest"] = hashlib.sha256(canonical_json(evidence)).hexdigest()
    return evidence
