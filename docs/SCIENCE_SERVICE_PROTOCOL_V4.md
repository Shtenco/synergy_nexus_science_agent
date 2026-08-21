# NEXUS Science Agent service protocol v4

This generation exposes the existing deterministic local search and evidence-graph core through a bounded read-only service surface.

Allowlisted operations:

- `SEARCH_LOCAL` over an already provisioned content-addressed corpus;
- `CLAIM_SUMMARY` over an already provisioned evidence graph.

Remote requests cannot provide URLs, hosts, filesystem paths, shell commands, retrieval policies or evidence-ingestion records. HTTP(S) retrieval remains a separate locally controlled ingestion boundary.

Every response is bound to the request digest and exact corpus/evidence graph digests. `scientific_truth_authority=NONE` and `execution_authority=NONE` are mandatory.

The service descriptor intentionally keeps `build_artifact_digest=null` and `SOURCE_SERVICE_CANDIDATE_NOT_BUILD_VERIFIED` until reproducible build/test evidence exists.
