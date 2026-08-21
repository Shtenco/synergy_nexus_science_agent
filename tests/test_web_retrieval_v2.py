from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

import pytest

from nexus_science_agent.core import ResearchInvariantError, SearchIndex
from nexus_science_agent.retrieval import RetrievalPolicy, fetch_web_document


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/paper")
            self.end_headers()
            return
        body = b"<html><head><style>hidden</style></head><body><h1>Graph evidence</h1><p>Small-world routing supports efficient retrieval.</p><script>ignore()</script></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class LocalServer:
    def __enter__(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base = f"http://{host}:{port}"
        return self

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def test_default_policy_blocks_private_loopback():
    policy = RetrievalPolicy(allow_http=True)
    with pytest.raises(ResearchInvariantError, match="private/non-global"):
        fetch_web_document("http://127.0.0.1:8080/paper", document_id="doc-1", policy=policy)


def test_local_test_policy_produces_content_addressed_web_snapshot():
    policy = RetrievalPolicy(allow_http=True, allow_private_networks_for_tests=True)
    with LocalServer() as server:
        snapshot = fetch_web_document(
            server.base + "/paper",
            document_id="doc-1",
            policy=policy,
            retrieved_at="2026-08-21T07:00:00Z",
        )
    assert snapshot.raw_bytes > 0
    assert len(snapshot.raw_sha256) == 64
    assert snapshot.document.content_sha256 == snapshot.text_sha256
    assert "Small-world routing" in snapshot.document.content
    assert "ignore()" not in snapshot.document.content
    assert snapshot.scientific_truth_authority == "NONE"
    assert len(snapshot.artifact()["digest"]) == 64


def test_redirect_is_revalidated_and_final_url_is_recorded():
    policy = RetrievalPolicy(allow_http=True, allow_private_networks_for_tests=True)
    with LocalServer() as server:
        snapshot = fetch_web_document(
            server.base + "/redirect",
            document_id="doc-redirect",
            policy=policy,
            retrieved_at="2026-08-21T07:00:00Z",
        )
    assert snapshot.final_url.endswith("/paper")


def test_web_snapshot_feeds_same_deterministic_search_index():
    policy = RetrievalPolicy(allow_http=True, allow_private_networks_for_tests=True)
    with LocalServer() as server:
        snapshot = fetch_web_document(
            server.base + "/paper",
            document_id="doc-search",
            policy=policy,
            retrieved_at="2026-08-21T07:00:00Z",
        )
    index = SearchIndex([snapshot.document])
    result = index.search("small world retrieval")
    assert result[0]["document_id"] == "doc-search"
    assert result[0]["content_sha256"] == snapshot.text_sha256
