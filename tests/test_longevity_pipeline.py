from datetime import UTC, datetime

from scripts.update_longevity_radar import RawItem, build_briefing, canonical_key, dedupe_records, normalize_url, raw_to_record


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
