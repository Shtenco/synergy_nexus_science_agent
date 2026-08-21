# Local Science Agent service build recipe v1

This generation packages only the bounded local Science Agent service candidate frozen at commit `0607690c3036d2fdce2ac3e044094a8e4da0311b`.

Included functionality is limited to local search over a pre-provisioned content-addressed corpus and claim summaries over a pre-provisioned evidence graph. The network retrieval module `src/nexus_science_agent/retrieval.py` is explicitly excluded from the artifact allowlist and the recipe verifier rejects attempts to add it.

All included files are verified from raw bytes against frozen Git blob identities, then packed with deterministic ZIP ordering/timestamp/mode. Runtime dependencies are Python stdlib only.

The artifact has no scientific-truth or execution authority. A successful deterministic build still requires real service tests before any federation build lock can move beyond tests-pending status.

Future network-enabled research workers must use a different artifact generation and capability/profile contract; they must not silently expand this local-only artifact.
