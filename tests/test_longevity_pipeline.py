import base64
import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.update_longevity_radar import (
    RawItem,
    build_briefing,
    canonical_key,
    dedupe_records,
    fetch_ai_radar_bridge,
    normalize_url,
    public_item,
    raw_to_record,
    select_relevant_records,
    generate,
)


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
        {"id": str(i), "title": f"item {i}", "url": f"https://x/{i}", "site_id": f"site-{i % 3}", "source": f"source-{i % 3}", "source_type": "paper", "published_at": "2026-08-13T00:00:00Z", "signal_score": 1 - i / 100, "primary_topic": "aging_clock", "study_subject": "human", "publication_stage": "unknown", "risk_flags": [], "relevance_tier": "core", "selection_reason": "AI 与生命延续双重相关"}
        for i in range(12)
    ]
    payload = build_briefing(rows, "2026-08-13T00:00:00Z", 24)
    assert payload["schema_version"] == "bio-radar-v1"
    assert payload["item_count"] == 3
    assert payload["source_count"] == 3
    assert all(row["relevance_tier"] == "core" for row in payload["items"])


def test_relevant_selection_uses_rolling_windows_and_never_fills_from_all_tier():
    now = datetime(2026, 8, 15, tzinfo=UTC)
    rows = [
        {
            "id": "core-new", "canonical_key": "url:https://x/core-new", "title": "core", "url": "https://x/core-new",
            "site_id": "europepmc", "source": "journal-a", "source_type": "paper",
            "published_at": "2026-08-12T00:00:00Z", "signal_score": 0.9, "domain_score": 0.9,
            "primary_topic": "aging_clock", "relevance_tier": "core",
        },
        {
            "id": "related-old", "canonical_key": "url:https://x/related-old", "title": "related", "url": "https://x/related-old",
            "site_id": "official_rss", "source": "journal-b", "source_type": "news",
            "published_at": "2026-08-01T00:00:00Z", "signal_score": 0.7, "domain_score": 0.8,
            "primary_topic": "aging_mechanism", "relevance_tier": "related",
        },
        {
            "id": "generic", "canonical_key": "url:https://x/generic", "title": "generic AI", "url": "https://x/generic",
            "site_id": "ai_radar_bridge", "source": "generic", "source_type": "news",
            "published_at": "2026-08-15T00:00:00Z", "signal_score": 1.0, "domain_score": 0.0,
            "primary_topic": "ai_longevity", "relevance_tier": "all",
        },
    ]
    selected = select_relevant_records(rows, now=now, core_window_hours=168, related_window_hours=504, limit=60)
    assert [row["id"] for row in selected] == ["core-new", "related-old"]
    assert selected[0]["freshness_score"] > selected[1]["freshness_score"]


def test_generate_rescores_legacy_archive_rows(monkeypatch, tmp_path: Path):
    now = datetime(2026, 8, 15, tzinfo=UTC)
    legacy = {
        "id": "legacy", "canonical_key": "url:https://x/legacy", "title": "Cellular senescence and healthy aging",
        "url": "https://x/legacy", "site_id": "europepmc", "site_name": "Europe PMC", "source": "journal",
        "source_type": "paper", "published_at": "2026-08-10T00:00:00Z", "first_seen_at": "2026-08-10T00:00:00Z",
        "last_seen_at": "2026-08-10T00:00:00Z", "description": "", "publication_stage": "peer_review_status_unknown",
        "evidence_type": "paper",
    }
    (tmp_path / "archive.json").write_text(json.dumps({"items": [legacy]}), encoding="utf-8")

    def empty_collector(_session, _now):
        return [], {"site_id": "empty", "site_name": "empty", "ok": True, "item_count": 0, "error": None}

    monkeypatch.setattr("scripts.update_longevity_radar.fetch_europe_pmc", empty_collector)
    monkeypatch.setattr("scripts.update_longevity_radar.fetch_clinical_trials", empty_collector)
    monkeypatch.setattr("scripts.update_longevity_radar.fetch_rss_sources", empty_collector)
    monkeypatch.setattr("scripts.update_longevity_radar.fetch_papers_cool", empty_collector)
    monkeypatch.setattr("scripts.update_longevity_radar.fetch_github_projects", empty_collector)
    monkeypatch.setattr("scripts.update_longevity_radar.fetch_ai_radar_bridge", empty_collector)
    monkeypatch.setattr("scripts.update_longevity_radar.add_bilingual_titles", lambda *_args, **_kwargs: 0)

    summary = generate(tmp_path, now=now)
    relevant = json.loads((tmp_path / "latest-relevant.json").read_text(encoding="utf-8"))
    assert summary["relevant_21d"] == 1
    assert relevant["items"][0]["relevance_tier"] == "related"


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
