# NEXUS SCIENCE AGENT

**Scientific search, evidence, falsification and reproducible-research agent built on validated NEXUS cores.**

Architecture root: `Shtenco/synergy_system`  
Intelligence core: `Shtenco/agi_nexus`

## Role

This repository is not another copy of NEXUS. It is the **scientific workflow layer** that uses NEXUS models together with web search, a local search/index engine, evidence graphs, code execution and reproducibility controls to conduct large research programmes.

Target domains include physics, materials, energy, economics, AI, medicine/biology where legally and ethically appropriate, and other research areas represented by dedicated domain repositories.

Existing natural integration targets include:

- `Shtenco/info_graph_theory`;
- `Shtenco/cold_nuclear`;
- future SYNERGY scientific domain repositories.

## Scientific pipeline

```text
Research Question
        ↓
Question / Claim Decomposition
        ↓
Search Plan
        ↓
Internet / papers / datasets / repositories
        ↓
Own Search Index + Content-Addressed Cache
        ↓
Claim Extraction
        ↓
Evidence Graph
        ↓
Source Quality / Date / Provenance
        ↓
Contradiction Search
        ↓
Falsification Attempts
        ↓
Hypothesis Graph
        ↓
Calculations / Code / Simulations
        ↓
Independent Verification Attempts
        ↓
Reproducible Research Package
        ↓
Report + Citations + Uncertainty + Open Questions
```

## Search-engine target architecture

The agent should maintain its own research index rather than depending on one opaque search provider.

```text
Fetcher / Search Connectors
        ↓
Parser / Metadata Normalizer
        ↓
Content Hash
        ↓
Deduplicated Document Store
        ↓
Lexical Index + Vector Index + Citation Graph
        ↓
Temporal / Source / Domain Filters
        ↓
NEXUS Query Planner
```

Search connectors may use public web search, scholarly APIs, datasets and repositories, but every retained source should record URL/identifier, retrieval time, publication date where known, content digest and citation relationships.

## Evidence graph

Recommended node classes:

```text
QUESTION
CLAIM
SOURCE
QUOTE / EXTRACT
DATASET
EQUATION
COMPUTATION
EXPERIMENT
HYPOTHESIS
COUNTEREXAMPLE
REPLICATION
CONCLUSION
OPEN_QUESTION
```

Recommended edge classes:

```text
SUPPORTS
CONTRADICTS
DERIVES_FROM
CITES
REPLICATES
FAILS_TO_REPLICATE
ASSUMES
FALSIFIES
DEPENDS_ON
SUPERSEDES
```

## Scientific status vocabulary

Every important result should be labelled explicitly:

```text
MEASURED / EVALUATED
DERIVED
REPRODUCED
SIMULATION
STRESS_TEST
HYPOTHESIS
CONDITIONAL
NEGATIVE_CONTROL
EXPERIMENTALLY_CONFIRMED
FAILED / FALSIFIED
OPEN
```

## Non-negotiable scientific rule

```text
search result        != evidence
citation             != truth
model output          != discovery
simulation            != experiment
internal consistency  != external validation
high confidence       != proof
```

The system should actively search for reasons a favored hypothesis is wrong.

## Reproducibility package

A completed research run should be able to export:

- research question and frozen scope;
- search queries;
- source manifest and hashes;
- evidence/contradiction graph;
- datasets and data provenance;
- code and environment specification;
- random seeds where relevant;
- calculations and generated artifacts;
- failed approaches and negative results;
- confidence/uncertainty statement;
- citation-ready final report;
- unresolved questions.

## NEXUS boundary

`agi_nexus` owns model architecture/inference identity.

`nexus_science_agent` owns the research workflow and evidence package.

A Science Agent result must bind the exact NEXUS model/version used, but it must not modify or silently redefine that model.

## Initial architecture modules

```text
nexus_science_agent/
  planning/
  search/
  index/
  retrieval/
  evidence_graph/
  contradiction/
  hypotheses/
  computation/
  verification/
  report/
  provenance/
  benchmarks/
```

## Initial acceptance criteria

The first production-quality milestone should not be “write a beautiful literature review”. It should demonstrate one end-to-end research problem where the agent:

1. finds diverse sources;
2. identifies conflicting evidence;
3. constructs a claim/evidence graph;
4. performs at least one independent calculation or code reproduction;
5. attempts falsification;
6. produces a reproducible report whose claims can be traced back to exact sources/artifacts.

## Principle

**NEXUS Science Agent is a machine for disciplined research, not an oracle.**
