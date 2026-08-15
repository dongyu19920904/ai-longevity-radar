#!/usr/bin/env python3
"""Explainable AI + longevity relevance and evidence metadata.

The scorer is deliberately deterministic. It labels what a public record says;
it does not infer clinical efficacy and it never produces medical advice.
"""

from __future__ import annotations

import re
from typing import Any

AI_RELEVANCE_THRESHOLD = 0.55
LONGEVITY_RELEVANCE_THRESHOLD = 0.55

AI_KEYWORDS = (
    "ai", "ml", "llm", "xai",
    "artificial intelligence", "machine learning", "deep learning", "foundation model",
    "neural network", "computer vision", "natural language processing", "generative ai",
    "large language model", "transformer", "multimodal", "representation learning",
    "digital twin", "predictive model", "risk prediction", "algorithm", "ai model",
    "人工智能", "机器学习", "深度学习", "基础模型", "神经网络", "计算机视觉",
    "自然语言处理", "生成式 ai", "大模型", "多模态", "预测模型", "算法",
)

BIOMEDICAL_ADJACENT_KEYWORDS = (
    "biomarker", "biomarkers", "drug discovery", "therapeutic discovery", "protein design",
    "genomic", "genomics", "transcriptomic", "transcriptomics", "proteomic", "proteomics",
    "metabolomic", "metabolomics", "multi-omics", "multiomics", "single-cell",
    "spatial transcriptomics", "cell segmentation", "digital health", "clinical trial",
    "precision medicine", "wearable", "medical imaging", "disease risk",
    "生物标志物", "药物发现", "药物设计", "蛋白质设计", "基因组", "转录组",
    "蛋白质组", "代谢组", "多组学", "单细胞", "数字健康", "临床试验", "精准医疗",
)

STRONG_BIOMEDICAL_ADJACENT_KEYWORDS = (
    "drug discovery", "therapeutic discovery", "protein design", "multi-omics", "multiomics",
    "single-cell", "spatial transcriptomics", "clinical trial", "precision medicine",
    "药物发现", "药物设计", "蛋白质设计", "多组学", "单细胞", "临床试验", "精准医疗",
)

LONGEVITY_KEYWORDS = (
    "longevity", "healthspan", "lifespan", "aging", "ageing", "geroscience",
    "biological age", "aging clock", "age clock", "epigenetic clock", "methylation age",
    "brain age", "retinal age", "facial age", "proteomic clock", "metabolomic clock",
    "senescence", "senolytic", "geroprotector", "rejuvenation", "partial reprogramming",
    "cellular reprogramming", "epigenetic reprogramming",
    "frailty", "sarcopenia", "immunosenescence", "inflammaging", "age-related",
    "alzheimer", "dementia", "neurodegeneration", "healthy aging", "healthy ageing",
    "mortality risk", "multi-omics aging", "single-cell aging", "anti-aging",
    "长寿", "延寿", "寿命", "衰老", "老化", "健康寿命", "生命延续", "生物年龄",
    "年龄时钟", "衰老时钟", "表观遗传时钟", "脑龄", "细胞衰老", "年轻化",
    "重编程", "衰老细胞", "老年痴呆", "阿尔茨海默", "神经退行", "肌少症",
    "虚弱", "免疫衰老", "炎症性衰老",
)

GENERIC_HEALTH_NOISE = (
    "weight loss", "skincare", "cosmetic", "beauty", "celebrity", "diet hack",
    "miracle cure", "anti-aging cream", "supplement launch", "menopause care", "wellness",
    "减肥", "护肤", "美容", "明星", "神药", "保健品发布",
)

DEMOGRAPHIC_AGING_NOISE = (
    "global aging", "global ageing", "population aging", "population ageing", "aging population",
    "ageing population", "aging society", "ageing society",
)

NON_BIOLOGICAL_AGING_NOISE = (
    "aluminum alloy", "aluminium alloy", "heat-treatable", "strength-ductility",
    "material aging", "materials aging", "battery aging", "battery ageing",
    "concrete aging", "transformer aging", "polymer aging", "steel aging",
)

TOPIC_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("aging_clock", ("biological age", "aging clock", "age clock", "epigenetic clock", "methylation age", "brain age", "retinal age", "facial age", "生物年龄", "年龄时钟", "衰老时钟", "表观遗传时钟", "脑龄")),
    ("rejuvenation", ("rejuvenation", "partial reprogramming", "cellular reprogramming", "epigenetic reprogramming", "senolytic", "geroprotector", "young blood", "年轻化", "重编程", "衰老细胞")),
    ("drug_discovery", ("drug discovery", "therapeutic discovery", "protein design", "small molecule", "药物发现", "药物设计", "蛋白质设计")),
    ("digital_biomarker", ("digital biomarker", "wearable", "gait", "voice biomarker", "retinal", "facial age", "数字生物标志物", "可穿戴", "步态", "视网膜")),
    ("neurodegeneration", ("alzheimer", "dementia", "neurodegeneration", "brain age", "阿尔茨海默", "老年痴呆", "神经退行", "脑龄")),
    ("multi_omics", ("multi-omics", "multiomics", "single-cell", "proteomic", "metabolomic", "methylation", "transcriptomic", "多组学", "单细胞", "蛋白质组", "代谢组", "甲基化")),
    ("clinical_trial", ("clinical trial", "randomized", "placebo", "nct0", "临床试验", "随机对照", "安慰剂")),
    ("research_tool", ("github.com", "open source", "software", "toolkit", "package", "开源", "工具包", "软件")),
    ("aging_mechanism", ("senescence", "telomere", "autophagy", "mitochond", "inflammaging", "immunosenescence", "衰老", "端粒", "自噬", "线粒体", "免疫衰老")),
    ("industry", ("funding", "investment", "partnership", "acquisition", "startup", "融资", "投资", "合作", "收购", "初创")),
)

SOURCE_PRIORS = {
    "europepmc": 0.22,
    "pubmed": 0.22,
    "clinicaltrials": 0.20,
    "official_rss": 0.16,
    "github_projects": 0.13,
    "papers_cool": 0.18,
    "opmlrss": 0.10,
    "ai_radar_bridge": 0.05,
}


def _text(record: dict[str, Any]) -> str:
    description = str(record.get("description") or "")
    description = re.sub(r"the post .*? appeared first on [^.]+\.?", " ", description, flags=re.IGNORECASE)
    parts = (
        record.get("title"), description, " ".join(record.get("keywords") or []),
    )
    return " ".join(str(value) for value in parts if value).lower()


def _contains_keyword(text: str, keyword: str) -> bool:
    """Match ASCII words on token boundaries while retaining phrase/CJK matching."""
    normalized = keyword.strip().lower()
    if not normalized:
        return False
    if normalized.isascii() and normalized.isalnum():
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", text))
    return normalized in text


def _matches(text: str, words: tuple[str, ...], ascii_tokens: set[str] | None = None) -> list[str]:
    tokens = ascii_tokens if ascii_tokens is not None else set(re.findall(r"[a-z0-9]+", text))
    return sorted({
        word for word in words
        if (word in tokens if word.isascii() and word.isalnum() else word in text)
    })


def infer_topics(text: str) -> list[str]:
    ascii_tokens = set(re.findall(r"[a-z0-9]+", text))
    topics = [topic for topic, keywords in TOPIC_RULES if _matches(text, keywords, ascii_tokens)]
    return topics or ["ai_longevity"]


def infer_study_subject(text: str) -> str:
    if re.search(r"\b(mouse|mice|murine|rat|rats|drosophila|c\. elegans|animal model)\b", text):
        return "animal"
    if re.search(r"\b(in vitro|cell line|cell culture|organoid|fibroblast|stem cell)\b", text):
        return "cell_or_organoid"
    if re.search(r"\b(patient|patients|participant|participants|cohort|human|clinical|randomized|randomised)\b", text):
        return "human"
    if re.search(r"\b(dataset|benchmark|simulation|in silico|computational|retrospective database)\b", text):
        return "computational_or_dataset"
    return "unknown"


def infer_publication_stage(record: dict[str, Any], text: str) -> str:
    explicit = str(record.get("publication_stage") or "").strip().lower()
    if explicit:
        return explicit
    source_type = str(record.get("source_type") or "")
    if source_type == "trial":
        return "registered_trial"
    if source_type == "project":
        return "software_project"
    if "preprint" in text or any(host in text for host in ("biorxiv.org", "medrxiv.org", "arxiv.org")):
        return "preprint"
    if source_type == "paper":
        return "peer_review_status_unknown"
    if source_type == "news":
        return "secondary_report"
    return "unknown"


def infer_risk_flags(record: dict[str, Any], text: str, subject: str, stage: str) -> list[str]:
    flags: list[str] = []
    if stage == "preprint":
        flags.append("preprint_not_peer_reviewed")
    if subject == "animal":
        flags.append("animal_study")
    elif subject == "cell_or_organoid":
        flags.append("cell_or_organoid_study")
    elif subject == "unknown" and record.get("source_type") == "paper":
        flags.append("study_subject_unknown")
    if stage == "secondary_report":
        flags.append("secondary_source")
    if record.get("source_type") in {"news", "social"}:
        flags.append("not_primary_evidence")
    return flags


def score_longevity_relevance(record: dict[str, Any]) -> dict[str, Any]:
    text = _text(record)
    ascii_tokens = set(re.findall(r"[a-z0-9]+", text))
    ai_signals = _matches(text, AI_KEYWORDS, ascii_tokens)
    longevity_signals = _matches(text, LONGEVITY_KEYWORDS, ascii_tokens)
    biomedical_signals = _matches(text, BIOMEDICAL_ADJACENT_KEYWORDS, ascii_tokens)
    strong_biomedical_signals = _matches(text, STRONG_BIOMEDICAL_ADJACENT_KEYWORDS, ascii_tokens)
    noise = _matches(text, GENERIC_HEALTH_NOISE, ascii_tokens)
    demographic_noise = _matches(text, DEMOGRAPHIC_AGING_NOISE, ascii_tokens)
    non_biological_noise = _matches(text, NON_BIOLOGICAL_AGING_NOISE, ascii_tokens)
    site_id = str(record.get("site_id") or "")
    source_prior = SOURCE_PRIORS.get(site_id, SOURCE_PRIORS["ai_radar_bridge"] if site_id.startswith("ai_radar_") else 0.0)

    upstream_ai_score = 0.0
    try:
        upstream_ai_score = max(0.0, min(1.0, float(record.get("upstream_ai_score") or 0.0)))
    except (TypeError, ValueError):
        upstream_ai_score = 0.0
    upstream_ai_evidence = record.get("upstream_ai_is_related") is True or upstream_ai_score >= 0.65

    local_ai_score = min(1.0, source_prior + min(0.76, 0.32 + 0.11 * len(ai_signals))) if ai_signals else source_prior
    ai_score = max(local_ai_score, upstream_ai_score if upstream_ai_evidence else 0.0)
    longevity_score = min(1.0, source_prior + min(0.78, 0.34 + 0.10 * len(longevity_signals))) if longevity_signals else source_prior
    biomedical_score = min(1.0, source_prior + min(0.72, 0.30 + 0.10 * len(biomedical_signals))) if biomedical_signals else source_prior
    if noise:
        ai_score = max(0.0, ai_score - min(0.25, len(noise) * 0.08))
        longevity_score = max(0.0, longevity_score - min(0.30, len(noise) * 0.10))
    if non_biological_noise:
        longevity_score = max(0.0, longevity_score - 0.72)
    demographic_aging_context = bool(demographic_noise) and set(longevity_signals).issubset({"aging", "ageing"})
    if demographic_aging_context:
        longevity_score = max(0.0, longevity_score - 0.72)

    ai_related = (local_ai_score >= AI_RELEVANCE_THRESHOLD and bool(ai_signals)) or upstream_ai_evidence
    longevity_related = (
        longevity_score >= LONGEVITY_RELEVANCE_THRESHOLD
        and bool(longevity_signals)
        and not non_biological_noise
        and not demographic_aging_context
    )
    keep = ai_related and longevity_related
    source_type = str(record.get("source_type") or "unknown")
    ai_biomedical_tool = (
        ai_related
        and not longevity_related
        and not noise
        and not non_biological_noise
        and source_type in {"paper", "trial", "project"}
        and biomedical_score >= 0.60
        and (source_type == "project" or len(strong_biomedical_signals) >= 2)
    )
    longevity_background = longevity_related and not ai_related and not noise and not non_biological_noise
    if keep:
        relevance_tier = "core"
        relevance_path = "local_ai_plus_longevity" if ai_signals else "upstream_ai_plus_longevity"
        selection_reason = "AI 与生命延续双重相关"
    elif longevity_background:
        relevance_tier = "related"
        relevance_path = "longevity_background"
        selection_reason = "生命延续背景研究"
    elif ai_biomedical_tool:
        relevance_tier = "related"
        relevance_path = "ai_biomedical_tool"
        selection_reason = "可用于生命科学研究的 AI 工具或方法"
    else:
        relevance_tier = "all"
        relevance_path = "generic_ai_only" if ai_related else "insufficient_domain_evidence"
        selection_reason = "仅保留在全部来源层"
    topics = infer_topics(text)
    subject = infer_study_subject(text)
    stage = infer_publication_stage(record, text)
    risks = infer_risk_flags(record, text, subject, stage)

    source_authority = min(1.0, source_prior * 3.2)
    evidence_bonus = 0.12 if source_type in {"paper", "trial"} else 0.04
    signal_score = min(1.0, 0.43 * longevity_score + 0.30 * ai_score + 0.17 * source_authority + evidence_bonus)
    domain_score = max(longevity_score, biomedical_score if ai_biomedical_tool else 0.0)
    if relevance_tier == "related":
        signal_score = min(1.0, 0.50 * domain_score + 0.24 * ai_score + 0.16 * source_authority + evidence_bonus)
    elif relevance_tier == "all":
        signal_score *= 0.45

    if not ai_related:
        reason = "missing_ai_signal"
    elif not longevity_signals:
        reason = "missing_longevity_signal"
    elif non_biological_noise:
        reason = "non_biological_aging_context"
    elif demographic_aging_context:
        reason = "demographic_aging_context"
    elif noise and not keep:
        reason = "health_or_commerce_noise"
    else:
        reason = "matched_ai_and_longevity_signals"

    return {
        "is_related": keep,
        "ai_is_related": ai_related,
        "ai_score": round(ai_score, 3),
        "longevity_is_related": longevity_related,
        "longevity_score": round(longevity_score, 3),
        "signal_score": round(signal_score, 3),
        "domain_score": round(domain_score, 3),
        "relevance_tier": relevance_tier,
        "relevance_path": relevance_path,
        "selection_reason": selection_reason,
        "topics": topics,
        "primary_topic": topics[0],
        "study_subject": subject,
        "publication_stage": stage,
        "evidence_type": str(record.get("evidence_type") or record.get("source_type") or "unknown"),
        "risk_flags": risks,
        "relevance_reason": reason,
        "ai_signals": ai_signals[:12],
        "longevity_signals": longevity_signals[:12],
        "biomedical_signals": biomedical_signals[:12],
        "noise_signals": noise[:8],
        "demographic_noise_signals": demographic_noise[:8],
        "non_biological_noise_signals": non_biological_noise[:8],
    }


def add_longevity_fields(record: dict[str, Any]) -> dict[str, Any]:
    return {**record, **score_longevity_relevance(record)}
