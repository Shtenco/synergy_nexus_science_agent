from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nexus_research.contracts import SourceRecord
from nexus_research.cache import ResearchIndex


def source(sid, url, text, sha, lineage="lab-a", quality=0.8):
    return SourceRecord(
        source_id=sid,
        url=url,
        title="Test paper about batteries",
        text=text,
        content_sha256=sha,
        retrieved_at="2026-09-11T00:00:00Z",
        published_at="2026-09-01",
        source_type="paper",
        domain="science",
        lineage_id=lineage,
        is_primary=True,
        quality_score=quality,
    )


class ResearchIndexContracts(unittest.TestCase):
    def test_dedup_and_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            with ResearchIndex(Path(td) / "research.sqlite") as idx:
                self.assertTrue(idx.add(source("a", "https://a.test/1", "battery experiment data", "a" * 64)))
                self.assertFalse(idx.add(source("b", "https://b.test/2", "same bytes elsewhere", "a" * 64)))
                self.assertEqual(idx.count(), 1)
                self.assertEqual(idx.manifest(), {"a": "a" * 64})

    def test_search_returns_stored_source(self):
        with tempfile.TemporaryDirectory() as td:
            with ResearchIndex(Path(td) / "research.sqlite") as idx:
                idx.add(source("a", "https://a.test/1", "solid state battery electrolyte experiment", "b" * 64))
                rows = idx.search("battery", limit=5)
                self.assertEqual(rows[0].source_id, "a")


if __name__ == "__main__":
    unittest.main()
