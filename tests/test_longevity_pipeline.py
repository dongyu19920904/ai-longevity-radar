import base64
import json
from datetime import UTC, datetime

from scripts.update_longevity_radar import RawItem, build_briefing, canonical_key, dedupe_records, fetch_ai_radar_bridge, normalize_url, public_item, raw_to_record


def test_url_and_entity_keys_are_stable():
    assert normalize_url("https://Example.com/paper/?utm_source=x&fbclid=y") == "https://example.com/paper"
    assert canonical_key(url="https://x", doi="10.1000/Test") == "doi:10.1000/test"
    assert canonical_key(url="https://x", pmid="123") == "pmid:123"
    assert canonical_key(url="https://x", repo="Owner/Repo") == "repo:owner/repo"


def test_raw_record_exposes_domain_contract():
    now = datetime(2026, 8, 13, tzinfo=UTC)
    row = raw_to_record(RawItem(
        site_id="europepmc", site_name="Europe PMC", source="Journal", source_type="paper",
        title="Deep learning predicts biological age in a human cohort", url="https://europepmc.org/article/MED/1",
        published_at=now, canonical_key="pmid:1", publication_stage="peer_review_status_unknown", evidence_type="paper",
    ), now, {})
    assert row is not None
    assert row["is_related"]
    assert row["canonical_key"] == "pmid:1"
    assert row["study_subject"] == "human"
    assert row["evidence_type"] == "paper"


def test_dedupe_prefers_stronger_entity_record():
    base = {"canonical_key": "doi:1", "published_at": "2026-08-13T00:00:00Z", "url": "https://x", "title": "x"}
    result = dedupe_records([{**base, "signal_score": 0.5}, {**base, "signal_score": 0.9, "source": "primary"}])
    assert len(result) == 1
    assert result[0]["source"] == "primary"


def test_briefing_is_small_and_source_diverse():
    rows = [
        {"id": str(i), "title": f"item {i}", "url": f"https://x/{i}", "site_id": f"site-{i % 3}", "source": f"source-{i % 3}", "source_type": "paper", "published_at": "2026-08-13T00:00:00Z", "signal_score": 1 - i / 100, "primary_topic": "aging_clock", "study_subject": "human", "publication_stage": "unknown", "risk_flags": []}
        for i in range(12)
    ]
    payload = build_briefing(rows, "2026-08-13T00:00:00Z", 24)
    assert payload["schema_version"] == "bio-radar-v1"
    assert payload["item_count"] == 3
    assert payload["source_count"] == 3


def test_ai_radar_bridge_preserves_each_upstream_source_identity():
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"items": [{
                "site_id": "official_ai", "site_name": "Official AI Updates", "source": "OpenAI",
                "title": "AI model update", "url": "https://example.com/update", "published_at": "2026-08-13T00:00:00Z",
                "ai_is_related": True, "ai_score": 0.91,
            }]}

    class Session:
        def get(self, *_args, **_kwargs):
            return Response()

    now = datetime(2026, 8, 13, tzinfo=UTC)
    rows, status = fetch_ai_radar_bridge(Session(), now)
    assert len(rows) == 1
    assert rows[0].site_id == "ai_radar_official_ai"
    assert rows[0].site_name == "爱窝啦 AI雷达 · Official AI Updates"
    assert status["source_count"] == 1
    exposed = public_item(raw_to_record(rows[0], now, {}))
    assert exposed["upstream_site_id"] == "official_ai"
    assert exposed["upstream_ai_is_related"] is True
    assert exposed["upstream_ai_score"] == 0.91


def test_ai_radar_bridge_falls_back_when_custom_domain_fails():
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"items": [{
                "site_id": "buzzing", "site_name": "Buzzing", "source": "Hacker News",
                "title": "An AI release", "url": "https://example.com/release",
            }]}

    class Session:
        calls = 0

        def get(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("TLS reset")
            return Response()

    rows, status = fetch_ai_radar_bridge(Session(), datetime(2026, 8, 13, tzinfo=UTC))
    assert rows[0].site_id == "ai_radar_buzzing"
    assert "raw.githubusercontent.com" in status["endpoint_used"]
    assert len(status["fallback_errors"]) == 1
    assert status["ok"] is True


def test_ai_radar_bridge_reads_large_file_through_git_blob_api():
    payload = {"items": [{
        "site_id": "techurls", "site_name": "TechURLs", "source": "TechURLs",
        "title": "AI infrastructure news", "url": "https://example.com/infrastructure",
    }]}

    class Response:
        def __init__(self, value):
            self.value = value

        def raise_for_status(self):
            return None

        def json(self):
            return self.value

    class Session:
        calls = 0

        def get(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls <= 2:
                raise RuntimeError("endpoint unavailable")
            if self.calls == 3:
                return Response({"encoding": "none", "git_url": "https://api.github.com/blob/1"})
            encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
            return Response({"encoding": "base64", "content": encoded})

    rows, status = fetch_ai_radar_bridge(Session(), datetime(2026, 8, 13, tzinfo=UTC))
    assert rows[0].site_id == "ai_radar_techurls"
    assert "api.github.com/repos/" in status["endpoint_used"]
    assert status["source_count"] == 1


def test_ai_radar_bridge_rejects_unsafe_blob_url():
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"encoding": "none", "git_url": "https://example.com/private"}

    class Session:
        calls = 0

        def get(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls <= 2:
                raise RuntimeError("endpoint unavailable")
            return Response()

    rows, status = fetch_ai_radar_bridge(Session(), datetime(2026, 8, 13, tzinfo=UTC))
    assert rows == []
    assert status["ok"] is False
    assert "unsafe git_url" in status["error"]
