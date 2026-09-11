from __future__ import annotations

"""Full-content fetchers for R8.3.

A SearchHit/snippet is discovery metadata only. These fetchers create the
SourceRecord that may later be used by claim extraction/evidence logic.
"""

import hashlib
import io
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlparse
import urllib.request
from typing import Optional

from .contracts import SearchHit, SourceRecord
from .providers import DEFAULT_UA


class _TextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript", "svg", "canvas"}:
            self.skip_depth += 1
        if tag.lower() in {"p", "br", "li", "div", "section", "article", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript", "svg", "canvas"} and self.skip_depth:
            self.skip_depth -= 1
        if tag.lower() in {"p", "li", "div", "section", "article", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip_depth == 0:
            self.parts.append(data)

    def text(self) -> str:
        raw = " ".join(self.parts)
        raw = re.sub(r"[ \t\r\f\v]+", " ", raw)
        raw = re.sub(r"\n\s*\n+", "\n", raw)
        return raw.strip()


def _quality_for_url(url: str, provider: str) -> tuple[float, bool, str]:
    host = (urlparse(url).hostname or "").lower()
    provider = provider.lower()
    if host in {"doi.org", "dx.doi.org"} or provider == "crossref":
        return 0.72, True, "scholarly"
    if host.endswith(".gov") or ".gov." in host:
        return 0.82, True, "official"
    if host.endswith(".edu") or ".edu." in host:
        return 0.74, False, "academic"
    if host in {"arxiv.org", "export.arxiv.org"}:
        return 0.76, True, "preprint"
    if host in {"github.com", "raw.githubusercontent.com"} or provider.startswith("github"):
        return 0.68, True, "repository"
    return 0.50, False, "web"


def _source_id(url: str, content_sha: str) -> str:
    return hashlib.blake2s(f"{url}|{content_sha}".encode("utf-8"), digest_size=10).hexdigest()


class HTTPContentFetcher:
    def __init__(self, *, timeout: float = 25.0, max_bytes: int = 12_000_000) -> None:
        self.timeout = float(timeout)
        self.max_bytes = int(max_bytes)

    def fetch(self, hit: SearchHit) -> Optional[SourceRecord]:
        req = urllib.request.Request(
            hit.url,
            headers={
                "User-Agent": DEFAULT_UA,
                "Accept": "text/html,application/xhtml+xml,application/pdf,text/plain,application/json;q=0.8,*/*;q=0.5",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                content_type = str(response.headers.get("Content-Type") or "").lower()
                raw = response.read(self.max_bytes + 1)
                final_url = response.geturl()
        except Exception:
            return None
        if len(raw) > self.max_bytes:
            return None

        text = self._decode(raw, content_type)
        if not text or len(text) < 80:
            return None
        sha = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
        quality, primary, source_type = _quality_for_url(final_url, hit.provider)
        return SourceRecord(
            source_id=_source_id(final_url, sha),
            url=final_url,
            title=hit.title,
            text=text,
            content_sha256=sha,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            published_at=hit.published_at,
            source_type=source_type,
            domain=(urlparse(final_url).hostname or ""),
            lineage_id="",  # normalized by SourceRegistry / later citation-lineage logic
            is_primary=primary,
            quality_score=quality,
        )

    @staticmethod
    def _decode(raw: bytes, content_type: str) -> str:
        if "pdf" in content_type or raw.startswith(b"%PDF-"):
            try:
                from pypdf import PdfReader  # optional dependency
                reader = PdfReader(io.BytesIO(raw))
                return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
            except Exception:
                return ""
        if "html" in content_type or b"<html" in raw[:4096].lower():
            decoded = raw.decode("utf-8", errors="replace")
            parser = _TextHTMLParser()
            try:
                parser.feed(decoded)
                return parser.text()
            except Exception:
                return re.sub(r"<[^>]+>", " ", decoded)
        # text/plain, JSON, XML and unknown textual formats. Binary garbage is
        # naturally rejected by the minimum useful text gate above.
        return raw.decode("utf-8", errors="replace").strip()
