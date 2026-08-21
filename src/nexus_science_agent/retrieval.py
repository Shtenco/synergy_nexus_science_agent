from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import ipaddress
import json
import socket
import urllib.parse
import urllib.request
from typing import Callable

from .core import Document, ResearchInvariantError


_ALLOWED_CONTENT_TYPES = {
    "text/plain",
    "text/html",
    "application/json",
    "application/xml",
    "text/xml",
}


@dataclass(frozen=True)
class RetrievalPolicy:
    max_response_bytes: int = 2 * 1024 * 1024
    timeout_seconds: int = 10
    allow_http: bool = False
    allow_private_networks_for_tests: bool = False

    def validate(self) -> None:
        if isinstance(self.max_response_bytes, bool) or not isinstance(self.max_response_bytes, int) or not (1 <= self.max_response_bytes <= 16 * 1024 * 1024):
            raise ResearchInvariantError("max_response_bytes out of range")
        if isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, int) or not (1 <= self.timeout_seconds <= 60):
            raise ResearchInvariantError("timeout_seconds out of range")


@dataclass(frozen=True)
class WebSnapshot:
    schema: str
    requested_url: str
    final_url: str
    retrieved_at: str
    content_type: str
    raw_bytes: int
    raw_sha256: str
    text_sha256: str
    document: Document
    network_security_status: str = "PUBLIC_ADDRESS_PREFLIGHT_ONLY"
    scientific_truth_authority: str = "NONE"

    def artifact(self) -> dict[str, object]:
        payload = {
            "schema": self.schema,
            "requested_url": self.requested_url,
            "final_url": self.final_url,
            "retrieved_at": self.retrieved_at,
            "content_type": self.content_type,
            "raw_bytes": self.raw_bytes,
            "raw_sha256": self.raw_sha256,
            "text_sha256": self.text_sha256,
            "document": self.document.identity(),
            "network_security_status": self.network_security_status,
            "scientific_truth_authority": self.scientific_truth_authority,
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        return payload | {"digest": digest}


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, validator: Callable[[str], None]):
        super().__init__()
        self._validator = validator

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self._validator(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript"}:
            self._suppressed += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript"} and self._suppressed:
            self._suppressed -= 1

    def handle_data(self, data):
        if not self._suppressed:
            stripped = " ".join(data.split())
            if stripped:
                self.parts.append(stripped)

    def text(self) -> str:
        return "\n".join(self.parts)


def fetch_web_document(
    url: str,
    *,
    document_id: str,
    policy: RetrievalPolicy = RetrievalPolicy(),
    retrieved_at: str | None = None,
) -> WebSnapshot:
    policy.validate()

    def validate(candidate: str) -> None:
        _validate_public_url(candidate, policy)

    validate(url)
    opener = urllib.request.build_opener(_SafeRedirectHandler(validate))
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "NEXUS-Science-Agent/0.2 (+provenance-research)"},
        method="GET",
    )
    try:
        with opener.open(request, timeout=policy.timeout_seconds) as response:
            final_url = response.geturl()
            validate(final_url)
            content_type = response.headers.get_content_type().lower()
            if content_type not in _ALLOWED_CONTENT_TYPES:
                raise ResearchInvariantError(f"unsupported web content type: {content_type}")
            raw = response.read(policy.max_response_bytes + 1)
    except ResearchInvariantError:
        raise
    except Exception as exc:
        raise ResearchInvariantError(f"web retrieval failed: {type(exc).__name__}") from exc

    if len(raw) > policy.max_response_bytes:
        raise ResearchInvariantError("web response exceeds configured byte limit")
    if not raw:
        raise ResearchInvariantError("web response is empty")

    charset = "utf-8"
    try:
        declared = response.headers.get_content_charset()  # type: ignore[name-defined]
        if declared:
            charset = declared
    except Exception:
        pass
    try:
        decoded = raw.decode(charset, errors="strict")
    except (LookupError, UnicodeDecodeError):
        decoded = raw.decode("utf-8", errors="replace")

    if content_type == "text/html":
        parser = _TextExtractor()
        parser.feed(decoded)
        text = parser.text()
    else:
        text = decoded.strip()
    if not text:
        raise ResearchInvariantError("retrieved document has no indexable text")

    stamp = retrieved_at or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    document = Document(document_id=document_id, uri=final_url, source_kind="WEB_SNAPSHOT", retrieved_at=stamp, content=text)
    return WebSnapshot(
        schema="nexus.web-snapshot/v2",
        requested_url=url,
        final_url=final_url,
        retrieved_at=stamp,
        content_type=content_type,
        raw_bytes=len(raw),
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        text_sha256=document.content_sha256,
        document=document,
        network_security_status=(
            "PRIVATE_NETWORKS_ALLOWED_FOR_TESTS" if policy.allow_private_networks_for_tests else "PUBLIC_ADDRESS_PREFLIGHT_ONLY"
        ),
    )


def _validate_public_url(url: str, policy: RetrievalPolicy) -> None:
    if not isinstance(url, str) or not url:
        raise ResearchInvariantError("URL is required")
    parsed = urllib.parse.urlsplit(url)
    allowed_schemes = {"https"} | ({"http"} if policy.allow_http else set())
    if parsed.scheme.lower() not in allowed_schemes:
        raise ResearchInvariantError("URL scheme not allowed by retrieval policy")
    if not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ResearchInvariantError("URL must contain a hostname and no embedded credentials")
    if parsed.port is not None and not (1 <= parsed.port <= 65535):
        raise ResearchInvariantError("invalid URL port")
    if policy.allow_private_networks_for_tests:
        return
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    try:
        addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ResearchInvariantError("hostname resolution failed") from exc
    if not addresses:
        raise ResearchInvariantError("hostname resolved to no addresses")
    for info in addresses:
        address = ipaddress.ip_address(info[4][0].split("%", 1)[0])
        if not address.is_global:
            raise ResearchInvariantError("private/non-global network destinations are forbidden")
