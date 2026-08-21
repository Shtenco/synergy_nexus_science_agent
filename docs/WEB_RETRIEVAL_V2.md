# NEXUS Science Agent Web Retrieval v2

V2 adds an Internet-facing evidence input boundary without changing the v1 search/evidence graph semantics.

## Snapshot pipeline

`URL → policy validation → bounded HTTP(S) GET → redirect validation → raw SHA-256 → text extraction → text SHA-256 → Document → SearchIndex/EvidenceGraph`

The resulting `nexus.web-snapshot/v2` preserves:

- requested URL;
- final URL after redirects;
- retrieval timestamp;
- content type;
- raw byte count and SHA-256;
- extracted text SHA-256;
- existing `Document` identity;
- `scientific_truth_authority = NONE`.

## Network safety

Default policy:

- HTTPS only;
- no embedded URL credentials;
- bounded response size (2 MiB default, 16 MiB hard maximum);
- bounded timeout;
- only text/plain, text/html, JSON and XML in v2;
- DNS preflight rejects any non-global address;
- each redirect target is validated before following.

The current status is deliberately `PUBLIC_ADDRESS_PREFLIGHT_ONLY`. DNS rebinding and hostile parser isolation require a later network sandbox/egress proxy with resolved-IP pinning. `allow_private_networks_for_tests` exists only so local HTTP fixtures can exercise the transport in CI.

## Scientific boundary

Retrieval proves what bytes were observed at a URL at a time. It does not prove that the publisher is correct, that a paper is peer reviewed, or that a scientific claim is true.

Next generation should add source-quality metadata, DOI/arXiv/repository adapters, immutable raw snapshot storage and a sandboxed egress service.
