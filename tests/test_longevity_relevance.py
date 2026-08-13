from scripts.longevity_relevance import add_longevity_fields, score_longevity_relevance


def record(title: str, **overrides):
    return {
        "site_id": "europepmc",
        "site_name": "Europe PMC",
        "source": "Europe PMC",
        "source_type": "paper",
        "title": title,
        "url": "https://europepmc.org/article/MED/123",
        **overrides,
    }


def test_requires_both_ai_and_longevity_signals():
    assert score_longevity_relevance(record("Deep learning predicts biological age from retinal images"))["is_related"]
    assert not score_longevity_relevance(record("A new large language model for coding"))["is_related"]
    assert not score_longevity_relevance(record("Cellular senescence and healthy aging"))["is_related"]


def test_labels_subject_stage_and_risk_without_claiming_efficacy():
    result = score_longevity_relevance(record(
        "Machine learning aging clock in mice: a preprint study",
        publication_stage="preprint",
    ))
    assert result["study_subject"] == "animal"
    assert result["publication_stage"] == "preprint"
    assert "animal_study" in result["risk_flags"]
    assert "preprint_not_peer_reviewed" in result["risk_flags"]
    assert "effective" not in result


def test_adds_public_explainability_fields():
    out = add_longevity_fields(record("Artificial intelligence model for Alzheimer dementia risk prediction"))
    assert out["ai_is_related"]
    assert out["longevity_is_related"]
    assert out["signal_score"] > 0
    assert "neurodegeneration" in out["topics"]
    assert out["relevance_reason"] == "matched_ai_and_longevity_signals"


def test_generic_beauty_content_is_not_promoted():
    result = score_longevity_relevance(record(
        "AI skincare anti-aging cream becomes a celebrity beauty trend",
        site_id="ai_radar_bridge",
        source_type="news",
    ))
    assert not result["is_related"]
    assert result["noise_signals"]


def test_material_aging_is_not_biological_longevity():
    result = score_longevity_relevance(record(
        "Machine learning prediction of aging in a heat-treatable aluminum alloy",
    ))
    assert not result["is_related"]
    assert result["relevance_reason"] == "non_biological_aging_context"
