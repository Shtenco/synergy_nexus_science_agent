# R8.3 Research Benchmark Protocol

Status: development protocol. No R8.3 score is claimed yet.

## Why two benchmarks

A live web benchmark measures usefulness on today's internet but is difficult to reproduce because pages, rankings and availability change. A frozen-web benchmark is reproducible but cannot measure freshness. R8.3 therefore requires both.

## A. Frozen Research Replay

Freeze before the agent sees the questions:

- a dated corpus/snapshot of pages, papers, datasets and repository metadata;
- content hashes;
- permitted search/index API;
- benchmark questions;
- reference claim graph / accepted evidence where feasible;
- evaluation scripts.

Measure:

1. answer/claim factual precision;
2. semantic obligation coverage;
3. source recall;
4. citation correctness / entailment;
5. citation completeness;
6. independent-lineage recall;
7. contradiction recall;
8. falsification-attempt rate;
9. unsupported-claim rate;
10. search/query cost;
11. pages fetched;
12. rounds / test-time compute;
13. reproducibility from source hashes.

## B. Live Research Blind

Created only after R8.3 freeze. Questions must require information that can change or that is genuinely distributed across the live web.

Each question should have multiple semantic obligations and should not be solvable reliably from one search result. Include:

- current scientific/technical state;
- comparisons with primary sources;
- disputed or conflicting claims;
- time-sensitive facts;
- multi-hop entity research;
- research requiring a paper + dataset/repository + independent source;
- at least some negative-result/falsification questions.

Human adjudication records exact URLs and retrieval timestamps.

## Test-time compute curve

Every benchmark is evaluated at multiple fixed budgets, for example:

- B1: 5 queries / 10 fetched sources;
- B2: 15 queries / 30 sources;
- B3: 40 queries / 100 sources;
- B4: adaptive VOI budget.

The goal is to measure whether more research effort produces monotonic or at least useful gains rather than just more text.

## Multi-trajectory research

For selected difficult questions run independent research trajectories with different query seeds. Compare:

- single trajectory;
- majority conclusion;
- confidence-weighted conclusion;
- **evidence-best-of-N** using obligation coverage, citation traceability, source independence, contradiction/falsification coverage and unresolved-claim penalties.

The selection rule must be frozen before confirmatory evaluation.

## Leakage boundary

Disclosed development questions cannot become a fresh blind. Any policy tuned after seeing a question/result requires a new post-freeze set.

## Primary acceptance gate

A report is not accepted merely because its final prose sounds convincing. For acceptance it must be possible to traverse:

```text
final sentence / claim
      ↓
claim_id
      ↓
evidence edge
      ↓
source_id
      ↓
URL / identifier + retrieval timestamp + content hash
```

High-confidence prose without this trace is a failure, not a partial success.
