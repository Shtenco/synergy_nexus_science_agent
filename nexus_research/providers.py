from __future__ import annotations

"""Real search-provider adapters for R8.3.

Providers return SearchHit candidates only. They do NOT create EvidenceItem
objects. Evidence requires a subsequent full fetch + content hash + claim
extraction gate in ResearchCortex.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from .contracts import SearchHit, SearchQuery


DEFAULT_UA = "NEXUS-R8.3-Research-Cortex/0.1 (+https://github.com/Shtenco/nexus_science_agent)"


def _json_get(
    url: str,
    *,
    params: Mapping[str, object] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = 20.0,
) -> dict:
    if params:
        encoded = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{url}{'&' if '?' in url else '?'}{encoded}"
    hdr = {"User-Agent": DEFAULT_UA, "Accept": "application/json"}
    if headers:
        hdr.update(headers)
    request = urllib.request.Request(url, headers=hdr, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("provider response is not a JSON object")
    return value


@dataclass
class BraveSearchProvider:
    """General live-web search via Brave Search API.

    Requires BRAVE_SEARCH_API_KEY unless ``api_key`` is supplied explicitly.
    """

    api_key: str = ""
    count: int = 10
    country: str = "US"
    search_lang: str = "en"
    timeout: float = 20.0
    name: str = "brave-web"

    def __post_init__(self) -> None:
        if not self.api_key:
            self.api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "")
        if not self.api_key:
            raise ValueError("BRAVE_SEARCH_API_KEY is required for BraveSearchProvider")

    def search(self, queries: Sequence[SearchQuery]) -> List[SearchHit]:
        hits: List[SearchHit] = []
        for q in queries:
            payload = _json_get(
                "https://api.search.brave.com/res/v1/web/search",
                params={
                    "q": q.text,
                    "count": max(1, min(int(self.count), 20)),
                    "country": self.country,
                    "search_lang": self.search_lang,
                },
                headers={"X-Subscription-Token": self.api_key},
                timeout=self.timeout,
            )
            results = ((payload.get("web") or {}).get("results") or [])
            for row in results:
                if not isinstance(row, dict) or not row.get("url"):
                    continue
                hits.append(
                    SearchHit(
                        query_id=q.query_id,
                        url=str(row["url"]),
                        title=str(row.get("title") or row["url"]),
                        snippet=str(row.get("description") or ""),
                        published_at=(str(row["age"]) if row.get("age") else None),
                        provider=self.name,
                    )
                )
        return hits


@dataclass
class CrossrefSearchProvider:
    """Scholarly metadata discovery through the public Crossref REST API."""

    rows: int = 8
    mailto: str = ""
    timeout: float = 20.0
    name: str = "crossref"

    @staticmethod
    def _date(row: dict) -> Optional[str]:
        for key in ("published-print", "published-online", "published", "issued", "created"):
            part = row.get(key)
            if not isinstance(part, dict):
                continue
            pieces = part.get("date-parts")
            if pieces and isinstance(pieces, list) and pieces[0]:
                vals = list(pieces[0]) + [1, 1]
                try:
                    return f"{int(vals[0]):04d}-{int(vals[1]):02d}-{int(vals[2]):02d}"
                except Exception:
                    pass
        return None

    def search(self, queries: Sequence[SearchQuery]) -> List[SearchHit]:
        hits: List[SearchHit] = []
        for q in queries:
            params: Dict[str, object] = {
                "query.bibliographic": q.text,
                "rows": max(1, min(int(self.rows), 50)),
                "select": "DOI,title,URL,abstract,published,published-online,published-print,issued,created,publisher,type,author",
            }
            if self.mailto:
                params["mailto"] = self.mailto
            payload = _json_get(
                "https://api.crossref.org/works",
                params=params,
                timeout=self.timeout,
            )
            for row in ((payload.get("message") or {}).get("items") or []):
                if not isinstance(row, dict):
                    continue
                doi = row.get("DOI")
                url = row.get("URL") or (f"https://doi.org/{doi}" if doi else "")
                if not url:
                    continue
                titles = row.get("title") or []
                title = titles[0] if isinstance(titles, list) and titles else str(doi or url)
                abstract = str(row.get("abstract") or "")
                publisher = str(row.get("publisher") or "")
                snippet = " | ".join(x for x in (publisher, abstract) if x)
                hits.append(
                    SearchHit(
                        query_id=q.query_id,
                        url=str(url),
                        title=str(title),
                        snippet=snippet,
                        published_at=self._date(row),
                        provider=self.name,
                    )
                )
        return hits


@dataclass
class GitHubRepositorySearchProvider:
    """Repository discovery through GitHub REST search.

    GITHUB_TOKEN is optional for public repositories but recommended for rate
    limits. This provider is intentionally repository-level; code/file search
    can be added as a separate provider without changing ResearchCortex.
    """

    token: str = ""
    per_page: int = 8
    timeout: float = 20.0
    name: str = "github-repositories"

    def __post_init__(self) -> None:
        if not self.token:
            self.token = os.environ.get("GITHUB_TOKEN", "")

    def search(self, queries: Sequence[SearchQuery]) -> List[SearchHit]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        hits: List[SearchHit] = []
        for q in queries:
            payload = _json_get(
                "https://api.github.com/search/repositories",
                params={"q": q.text, "per_page": max(1, min(int(self.per_page), 50))},
                headers=headers,
                timeout=self.timeout,
            )
            for row in payload.get("items") or []:
                if not isinstance(row, dict) or not row.get("html_url"):
                    continue
                description = str(row.get("description") or "")
                extra = f"stars={row.get('stargazers_count', 0)}; updated={row.get('updated_at', '')}"
                hits.append(
                    SearchHit(
                        query_id=q.query_id,
                        url=str(row["html_url"]),
                        title=str(row.get("full_name") or row.get("name") or row["html_url"]),
                        snippet=f"{description} | {extra}",
                        published_at=(str(row.get("updated_at")) if row.get("updated_at") else None),
                        provider=self.name,
                    )
                )
        return hits


class CompositeSearchProvider:
    """Run several provider adapters under one SearchProvider contract."""

    name = "composite"

    def __init__(self, providers: Sequence[object]) -> None:
        if not providers:
            raise ValueError("providers must not be empty")
        self.providers = list(providers)

    def search(self, queries: Sequence[SearchQuery]) -> List[SearchHit]:
        out: List[SearchHit] = []
        for provider in self.providers:
            out.extend(provider.search(queries))
        return out
