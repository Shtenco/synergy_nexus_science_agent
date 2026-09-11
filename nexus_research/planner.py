from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from typing import Iterable, List, Sequence

from .contracts import QueryIntent, ResearchQuestion, SearchQuery, SemanticObligation


def _id(prefix: str, text: str) -> str:
    return f"{prefix}-{hashlib.blake2s(text.encode('utf-8'), digest_size=6).hexdigest()}"


class ObligationPlanner:
    """Decompose a question into explicit research obligations.

    This is intentionally conservative. A production R8.2/R8.3 semantic brain
    may replace it, but the orchestration contract stays identical.
    """

    def decompose(self, question: ResearchQuestion) -> List[SemanticObligation]:
        text = " ".join(question.text.split())
        obligations: List[SemanticObligation] = []

        # Always require direct answer + evidence + counterevidence.
        obligations.append(SemanticObligation(_id("obl", text + ":answer"), f"Ответить на основной вопрос: {text}"))
        obligations.append(SemanticObligation(_id("obl", text + ":sources"), "Найти первичные или наиболее авторитетные источники"))
        obligations.append(SemanticObligation(_id("obl", text + ":counter"), "Найти данные, противоречащие ведущей гипотезе"))

        lower = text.lower()
        if any(w in lower for w in ("сравни", "лучше", "хуже", "против", "vs", "или")):
            obligations.append(SemanticObligation(_id("obl", text + ":compare"), "Сравнить альтернативы по одинаковым критериям"))
        if any(w in lower for w in ("почему", "причин", "влияет", "эффект")):
            obligations.append(SemanticObligation(_id("obl", text + ":causal"), "Отделить причинность от корреляции и перечислить альтернативные объяснения"))
        if any(w in lower for w in ("сколько", "%", "процент", "цена", "доход", "риск", "вероятност")):
            obligations.append(SemanticObligation(_id("obl", text + ":quant"), "Проверить ключевые числа и единицы измерения по исходным данным"))
        if question.freshness_days is not None or any(w in lower for w in ("сейчас", "сегодня", "последн", "новейш", "актуаль")):
            obligations.append(SemanticObligation(_id("obl", text + ":fresh"), "Проверить актуальность и дату каждого ключевого утверждения"))
        for constraint in question.user_constraints:
            obligations.append(SemanticObligation(_id("obl", text + constraint), f"Соблюсти ограничение пользователя: {constraint}"))
        return obligations


class QueryPortfolioPlanner:
    """R7.7/R7.16 inspired portfolio: confirmation is never enough."""

    def initial_queries(
        self,
        question: ResearchQuestion,
        obligations: Sequence[SemanticObligation],
    ) -> List[SearchQuery]:
        q = " ".join(question.text.split())
        required = tuple(o.obligation_id for o in obligations)
        items = [
            (QueryIntent.PRIMARY, f"{q} primary source official paper dataset", 1.00),
            (QueryIntent.CONFIRM, q, 0.90),
            (QueryIntent.CONTRADICT, f"{q} criticism contradictory evidence limitations failure", 1.00),
            (QueryIntent.REPLICATION, f"{q} replication independent study reproduction benchmark", 0.85),
            (QueryIntent.DATA, f"{q} dataset raw data statistics methodology", 0.80),
        ]
        if question.freshness_days is not None:
            items.append((QueryIntent.RECENCY, f"{q} latest update current", 0.95))
        out: List[SearchQuery] = []
        for idx, (intent, text, priority) in enumerate(items):
            out.append(
                SearchQuery(
                    query_id=_id("q", f"{idx}:{intent}:{text}"),
                    text=text,
                    intent=intent,
                    obligation_ids=required,
                    priority=priority,
                )
            )
        return out

    def followup_queries(
        self,
        question: ResearchQuestion,
        unresolved: Sequence[SemanticObligation],
        leading_claims: Iterable[str],
    ) -> List[SearchQuery]:
        claims = list(leading_claims)
        out: List[SearchQuery] = []
        for index, obligation in enumerate(unresolved):
            seed = claims[index % len(claims)] if claims else question.text
            for intent, suffix in (
                (QueryIntent.PRIMARY, "official primary source methodology"),
                (QueryIntent.CONTRADICT, "counterexample criticism contradictory evidence"),
            ):
                text = f"{seed} {obligation.description} {suffix}"
                out.append(
                    SearchQuery(
                        query_id=_id("qf", text),
                        text=text,
                        intent=intent,
                        obligation_ids=(obligation.obligation_id,),
                        priority=1.0,
                    )
                )
        return out
