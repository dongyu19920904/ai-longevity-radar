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


def test_ai_acronyms_use_token_boundaries():
    matched = score_longevity_relevance(record("AI aging clock predicts human biological age"))
    false_positive = score_longevity_relevance(record("Researchers said healthy aging improved"))
    assert matched["is_related"]
    assert "ai" in matched["ai_signals"]
    assert "ai" not in false_positive["ai_signals"]


def test_upstream_ai_decision_is_valid_ai_evidence_but_not_longevity_evidence():
    longevity = score_longevity_relevance(record(
        "A new biological age clock for healthy aging",
        site_id="ai_radar_official_ai",
        source_type="news",
        upstream_ai_is_related=True,
        upstream_ai_score=0.91,
    ))
    generic = score_longevity_relevance(record(
        "A new developer platform release",
        site_id="ai_radar_official_ai",
        source_type="news",
        upstream_ai_is_related=True,
        upstream_ai_score=0.91,
    ))
    assert longevity["is_related"]
    assert longevity["relevance_path"] == "upstream_ai_plus_longevity"
    assert longevity["relevance_reason"] == "matched_ai_and_longevity_signals"
    assert not generic["is_related"]
    assert generic["relevance_tier"] == "all"


def test_relevance_tiers_keep_useful_background_without_generic_ai_fill():
    background = score_longevity_relevance(record("Cellular senescence and healthy aging"))
    ai_bio_tool = score_longevity_relevance(record(
        "LLM platform for protein design, single-cell genomics and biomarker discovery",
        source_type="project",
    ))
    generic_ai = score_longevity_relevance(record("LLM platform for software developers", source_type="news"))
    assert background["relevance_tier"] == "related"
    assert background["relevance_path"] == "longevity_background"
    assert ai_bio_tool["relevance_tier"] == "related"
    assert ai_bio_tool["relevance_path"] == "ai_biomedical_tool"
    assert generic_ai["relevance_tier"] == "all"


def test_source_brand_is_not_counted_as_longevity_content_evidence():
    result = score_longevity_relevance(record(
        "A general healthcare data partnership",
        site_id="official_rss",
        source_type="news",
        source="Longevity.Technology",
        description="Clinical workflow tools. The post A partnership appeared first on Longevity.Technology.",
    ))
    assert result["relevance_tier"] == "all"
    assert not result["longevity_signals"]


def test_population_aging_and_metabolic_reprogramming_do_not_masquerade_as_longevity():
    demographic = score_longevity_relevance(record(
        "Machine learning studies tourism participation during global aging",
    ))
    metabolic = score_longevity_relevance(record(
        "Machine learning maps metabolic reprogramming in lung cancer",
    ))
    assert demographic["relevance_tier"] == "all"
    assert demographic["relevance_reason"] == "demographic_aging_context"
    assert metabolic["relevance_tier"] == "all"


def test_aging_requires_biological_context_and_stays_out_of_core_without_a_strong_signal():
    hardware = score_longevity_relevance(record("AI sustains an aging ICBM missile fleet", source_type="news"))
    gpu = score_longevity_relevance(record("AI makes aging GPU hardware profitable", source_type="news"))
    healthy_context = score_longevity_relevance(record("AI supports healthcare for aging patients", source_type="news"))
    assert hardware["relevance_tier"] == "all"
    assert gpu["relevance_tier"] == "all"
    assert healthy_context["relevance_tier"] == "related"
    assert healthy_context["relevance_path"] == "ai_healthy_aging_context"


def test_ai_finance_rejuvenation_and_personal_training_marketing_are_not_selected():
    finance = score_longevity_relevance(record("Tencent AI spend in overdrive; rejuvenation needs a final push", source_type="news"))
    fitness = score_longevity_relevance(record("Personal training outlook: longevity, GLP-1s and AI change the game", source_type="news"))
    assert finance["relevance_tier"] == "all"
    assert fitness["relevance_tier"] == "all"


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
    assert out["relevance_tier"] == "core"
    assert out["domain_score"] >= out["longevity_score"]
    assert out["selection_reason"]


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


def test_prefixed_ai_radar_sources_keep_bridge_prior():
    direct = score_longevity_relevance(record(
        "Machine learning predicts biological age", site_id="ai_radar_bridge", source_type="news",
    ))
    prefixed = score_longevity_relevance(record(
        "Machine learning predicts biological age", site_id="ai_radar_official_ai", source_type="news",
    ))
    assert prefixed["ai_score"] == direct["ai_score"]
    assert prefixed["longevity_score"] == direct["longevity_score"]
