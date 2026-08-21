# NEXUS Science Agent research pipeline v1

## Principle

The agent must preserve the distinction between retrieval, evidence, inference and scientific truth.

```text
question
→ search/query plan
→ retrieved documents
→ content-addressed local index
→ ranked retrieval
→ explicit claims
→ SUPPORTS / CONTRADICTS evidence edges
→ current-evidence summary
→ reproducible artifact
```

A summary such as `SUPPORTED_BY_CURRENT_EVIDENCE` is not equivalent to `TRUE`.

## Document identity

Every research input needs:

- stable document id;
- source URI;
- source kind;
- retrieval timestamp;
- exact SHA-256 of retrieved content.

If source content changes, the index digest changes.

## Internet adapter boundary

V1 provides the deterministic local core only. A future web/paper adapter must produce `Document` objects and retain:

- final resolved URL / DOI / repository identity;
- retrieval date;
- publication date when available;
- content digest;
- source-quality metadata;
- raw snapshot or lawful reference sufficient for reproduction.

The search adapter must not silently overwrite a previously indexed document under the same evidence identity.

## NEXUS boundary

A future NEXUS model may propose queries, extract candidate claims, rank contradictions and plan experiments. The research artifact must also record the exact NEXUS model/inference-bundle digest used for those actions.

NEXUS does not become scientific truth authority. Calculations, datasets, primary literature and experimental evidence remain independently inspectable.

## First run

`tools/run_demo_research.py` executes a small built-in `DEMO_METHOD_VALIDATION_NOT_SCIENTIFIC_RESULT` corpus. It validates the pipeline only; it is not presented as a scientific finding.
