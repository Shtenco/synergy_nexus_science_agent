from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from nexus_science_agent.service_build_recipe_v1 import (
    EXPECTED_RECIPE_DIGEST,
    ScienceBuildError,
    build_local_science_archive,
    verify_recipe,
    verify_source_tree,
)


ROOT = Path(__file__).resolve().parents[1]
RECIPE_PATH = ROOT / "config" / "local_science_service_build_recipe_v1.json"


def _recipe() -> dict:
    return json.loads(RECIPE_PATH.read_text(encoding="utf-8"))


def test_recipe_is_exact_local_only_and_stdlib_only() -> None:
    recipe = verify_recipe(_recipe())
    assert recipe["recipe_digest"] == EXPECTED_RECIPE_DIGEST
    assert recipe["dependency_contract"] == "PYTHON_STDLIB_ONLY"
    assert recipe["network_retrieval_capability"] == "EXCLUDED_FROM_ARTIFACT_V1"
    assert recipe["scientific_truth_authority"] == "NONE"
    assert recipe["execution_authority"] == "NONE"


def test_retrieval_module_is_physically_excluded() -> None:
    recipe = verify_recipe(_recipe())
    paths = {item["path"] for item in recipe["include_files"]}
    assert "src/nexus_science_agent/retrieval.py" not in paths
    assert recipe["excluded_network_modules"] == ["src/nexus_science_agent/retrieval.py"]


def test_current_local_service_source_matches_frozen_blobs() -> None:
    files = verify_source_tree(ROOT, _recipe())
    assert [f.path for f in files] == [item["path"] for item in _recipe()["include_files"]]


def test_repeated_builds_are_byte_identical(tmp_path: Path) -> None:
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    e1 = build_local_science_archive(ROOT, _recipe(), first)
    e2 = build_local_science_archive(ROOT, _recipe(), second)
    assert first.read_bytes() == second.read_bytes()
    assert e1 == e2
    assert e1["network_retrieval_capability"] == "EXCLUDED_FROM_ARTIFACT_V1"
    assert e1["build_status"] == "ARTIFACT_BUILT_TEST_EVIDENCE_PENDING"


def test_runtime_tamper_is_rejected(tmp_path: Path) -> None:
    shadow = tmp_path / "repo"
    for item in _recipe()["include_files"]:
        src = ROOT / item["path"]
        dst = shadow / item["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    target = shadow / "src" / "nexus_science_agent" / "service_v4.py"
    target.write_bytes(target.read_bytes() + b"\n# tamper\n")
    with pytest.raises(ScienceBuildError, match="source blob drift"):
        verify_source_tree(shadow, _recipe())


def test_fresh_hash_cannot_smuggle_network_retrieval_into_artifact() -> None:
    recipe = _recipe()
    recipe["include_files"].append({"path": "src/nexus_science_agent/retrieval.py", "git_blob_sha": "8797858dba834e9b3966f0752958ceda1e0e8060"})
    recipe["include_files"] = sorted(recipe["include_files"], key=lambda item: item["path"])
    recipe["recipe_digest"] = "0" * 64
    with pytest.raises(ScienceBuildError):
        verify_recipe(recipe)
