# Source Identity and Quality Gate v3

V3 adds explicit source metadata without converting provenance into an automatic truth score.

## Canonical identifiers

Supported first-class source identities:

- DOI article → canonical `https://doi.org/<lowercase-doi>`;
- modern arXiv preprint → canonical `https://arxiv.org/abs/<id>`;
- GitHub/GitLab repository → canonical project root;
- HTTPS dataset/web-document locators.

Each assessment binds the exact retrieved document content hash and a separate metadata-evidence digest.

## Transparent classification

The deterministic gate returns only:

- `HIGH_CONFIDENCE_ELIGIBLE` for primary, peer-reviewed, non-retracted-at-check sources;
- `ELIGIBLE_WITH_CAVEATS` for valid primary/secondary sources with explicit caveats such as preprint status;
- `BLOCKED_RETRACTED` for known retractions;
- `UNKNOWN_METADATA` when peer-review/retraction metadata is unknown.

The gate does **not** produce an evidence score, does not assert a claim is true, and does not make a preprint false by definition.

`scientific_truth_authority=NONE`
`automatic_evidence_score_authority=NONE`

A future metadata resolver may query Crossref/OpenAlex/arXiv APIs, but the returned metadata must itself be snapshot/evidence-bound before it can change this classification.
