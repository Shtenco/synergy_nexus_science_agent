# NEXUS R8.3 — RESEARCH CORTEX

Статус: **DEVELOPMENT / NOT FROZEN**.

## Зачем

R8.2 усиливает мышление и русский диалог. R8.3 возвращает и усиливает отдельную способность NEXUS: проводить дисциплинированный интернет/научный ресерч по собственным под-вопросам.

Research Cortex не является поисковиком и не является источником истины. Это кибернетический слой, который планирует поиск, связывает найденные материалы с semantic obligations, ищет противоречия и решает, какой следующий запрос даст максимальный прирост информации.

## Генетическая линия

В R8.3 сведены механизмы:

- `nexus_science_agent` initial design: Search Plan → Internet/papers/datasets/repos → Evidence Graph → contradiction/falsification → reproducible report;
- R7.5–R7.7: multi-teacher evidence collection и meta-routing;
- R7.10: Proof-First, найденный ответ не равен доказанному;
- R7.13: Hypothesis → Test → Evidence → Hypothesis;
- R7.16: adaptive query / Value of Information;
- R7.18: evidence credit;
- R7.19: deterministic computation/reproduction path;
- R7.22–R7.28: completeness, applicability и semantic obligation gates;
- R7.33: ClaimGraph + correlation/lineage discount;
- R7.36: UNKNOWN/DERIVED/LEARNED/KNOWN boundary;
- R8.2: Russian semantic decomposition + sovereign answer plan.

## Главный цикл

```text
USER QUESTION
    ↓
R8.2 semantic understanding
    ↓
RESEARCH QUESTION + FROZEN SCOPE
    ↓
SEMANTIC OBLIGATIONS
    ↓
QUERY PORTFOLIO
  ├─ primary-source query
  ├─ direct confirmation
  ├─ contradiction / criticism
  ├─ replication
  ├─ raw data / methodology
  └─ recency query when required
    ↓
SEARCH PROVIDERS
    ↓
FETCH FULL CONTENT
    ↓
CONTENT HASH + URL DEDUP
    ↓
SOURCE / PUBLISHER / CITATION LINEAGE
    ↓
CLAIM EXTRACTION
    ↓
CLAIM ↔ EVIDENCE GRAPH
    ↓
SUPPORT / CONTRADICT / FALSIFY / REPLICATE
    ↓
EVIDENCE CREDIT + CORRELATION DISCOUNT
    ↓
COMPLETENESS / UNCERTAINTY
    ↓
VALUE OF INFORMATION
    ├─ enough evidence -> report
    └─ unresolved -> targeted follow-up queries
```

## Жёсткие правила

```text
search result       != evidence
snippet             != source
citation            != truth
three mirrors       != three witnesses
model confidence    != proof
absence of conflict != falsification
simulation          != experiment
freshness unknown   != current
```

### Search result → evidence gate

SearchHit не может попасть в EvidenceGraph напрямую. Требуется:

1. fetch полного материала;
2. нормализованный source record;
3. content hash;
4. provenance/lineage;
5. claim extraction;
6. typed relation к claim.

### Correlation gate

Источники, принадлежащие одной lineage, дают diminishing marginal evidence. Это защищает от ситуации, когда десятки сайтов перепечатали одну исходную ошибку.

### Contradiction obligation

Первый query portfolio всегда содержит отдельный `CONTRADICT` запрос. Research Cortex должен искать не только подтверждение ведущей гипотезы, но и наиболее сильный контраргумент/контрпример.

### VOI loop

Если semantic obligation не покрыт или claim остаётся конфликтным, planner формирует follow-up запрос специально для этого пробела. Цель — не число страниц, а expected information gain.

## Completeness Certificate

Финализация проверяет:

- semantic obligation coverage;
- primary-source coverage;
- выполнен ли contradiction search;
- выполнена ли попытка falsification;
- число независимых lineages;
- unresolved high-value claims;
- freshness для актуальных вопросов;
- traceability всех evidence к source hashes.

Если certificate не проходит, система должна возвращать bounded report + OPEN/UNKNOWN, а не имитировать завершённое знание.

## Интеграция с R8.2

Предлагаемый интерфейс:

```text
R8.2 Cognitive Graph
    ↓
ResearchNeed(question, obligations, claims, unknowns)
    ↓
R8.3 Research Cortex
    ↓
ResearchReport(
    claims,
    evidence,
    sources,
    contradiction_graph,
    completeness,
    open_questions
)
    ↓
R8.2 Epistemic Governor
    ↓
Russian AnswerPlan
    ↓
Surface Cortex
```

Ключевой принцип: R8.3 не может напрямую писать финальный ответ пользователю и не может присваивать `VERIFIED_NATIVE`. Он поставляет evidence. Финальный epistemic commit остаётся у NEXUS.

## Следующие этапы

1. Подключить реальные web/scholarly/repository adapters.
2. Добавить собственный persistent content-addressed cache.
3. Lexical + vector + citation index.
4. Source-quality classifier с domain-specific policy.
5. Citation lineage / syndication detection.
6. R8.2 semantic-obligation adapter.
7. Computation/reproduction sandbox.
8. Fresh Research Blind: заранее замороженные вопросы после freeze, с ручной проверкой source traceability, contradiction recall и factual precision.

Никакие старые disclosed research questions не должны использоваться как новый blind.
