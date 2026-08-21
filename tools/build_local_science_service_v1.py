from __future__ import annotations

import argparse
import json
from pathlib import Path

from nexus_science_agent.service_build_recipe_v1 import build_local_science_archive, canonical_json, verify_recipe


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--recipe", type=Path, default=Path("config/local_science_service_build_recipe_v1.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()

    recipe = json.loads(args.recipe.read_text(encoding="utf-8"))
    verify_recipe(recipe)
    evidence = build_local_science_archive(args.root, recipe, args.output)
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_bytes(canonical_json(evidence) + b"\n")
    print(evidence["artifact_sha256"])
    print(evidence["evidence_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
