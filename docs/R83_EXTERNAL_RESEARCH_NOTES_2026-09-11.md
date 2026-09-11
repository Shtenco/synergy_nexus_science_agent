# R8.3 external research notes — 2026-09-11

These notes are design evidence, not NEXUS benchmark results.

## 1. BrowseComp (OpenAI, 2025)

Source: https://openai.com/index/browsecomp/
Paper: https://cdn.openai.com/pdf/5e10f4ab-d6f7-442e-9508-59515c65e35d/browsecomp.pdf

Key lessons for R8.3:

- difficult web research requires persistence and creative reformulation, not merely browser access;
- performance improves as browsing/test-time compute increases;
- multiple independent attempts can improve results substantially;
- best-of-N was stronger than simple majority/weighted voting in the reported aggregation experiment;
- browsing tasks can be easier to verify than to discover, so verification and discovery should have separate budgets.

R8.3 consequence: explicit search-budget curve + evidence-best-of-N trajectory selector.

## 2. DeepResearch Bench (Du et al., 2025)

Source: https://arxiv.org/abs/2506.11763

100 expert research tasks / 22 fields. The evaluation separates report quality from information-retrieval/citation quality and explicitly measures effective citations and citation accuracy.

R8.3 consequence: do not collapse report quality into one score. Track claim coverage, effective citation count, citation correctness, source independence and unsupported-claim rate separately.

## 3. Deep Research Bench / RetroSearch (FutureSearch, 2025)

Source: https://arxiv.org/abs/2506.06287

The work introduces an 89-task multi-step research benchmark and a frozen scraped-web environment (RetroSearch) so agents can be compared reproducibly while live web keeps changing. It also analyses agent traces for hallucination/tool-use/forgetting behavior.

R8.3 consequence: every release should have both a live-web evaluation and a frozen replay benchmark with hash-locked content.

## 4. LiveResearchBench (2025)

Source: https://arxiv.org/abs/2510.14240

100 expert-curated live research tasks designed to be user-centric, dynamic, unambiguous and multi-faceted/search-intensive. Evaluation includes content quality, coverage, presentation, citation accuracy/association, consistency and depth.

R8.3 consequence: a fresh post-freeze live benchmark must contain dynamic and multi-faceted user tasks, not only obscure single-fact retrieval.

## Design synthesis

```text
R8.3 Research Cortex
  = persistent browsing
  + adaptive query reformulation
  + semantic-obligation coverage
  + primary-source preference
  + contradiction/falsification search
  + publisher/citation lineage control
  + evidence-best-of-N research trajectories
  + independent verification
  + citation-grounded report
  + live benchmark
  + frozen replay benchmark
```

Scientific boundary: these external benchmark results motivate architecture and evaluation. They do not establish any R8.3 performance until R8.3 itself is frozen and tested.
