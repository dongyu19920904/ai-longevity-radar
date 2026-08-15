#!/usr/bin/env python3
"""Build the public AI Longevity Radar snapshots from stable public sources."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from xml.etree import ElementTree as ET

import feedparser
import requests
from dateutil import parser as dateparser

try:
    from scripts.longevity_relevance import add_longevity_fields
except ModuleNotFoundError:  # direct `python scripts/update_longevity_radar.py`
    from longevity_relevance import add_longevity_fields

USER_AGENT = "Aivora-AI-Longevity-Radar/1.0 (+https://radar.aibioo.cn/)"
BRIEFING_LIMIT = 8
RELEVANT_LIMIT = 60
CORE_WINDOW_HOURS = 7 * 24
RELATED_WINDOW_HOURS = 21 * 24

OFFICIAL_FEEDS: tuple[dict[str, str], ...] = (
    {"name": "Nature Aging", "url": "https://www.nature.com/subjects/ageing.rss"},
    {"name": "Fight Aging!", "url": "https://www.fightaging.org/feed/"},
    {"name": "Lifespan.io", "url": "https://www.lifespan.io/feed/"},
    {"name": "Buck Institute", "url": "https://www.buckinstitute.org/feed/"},
    {"name": "Longevity.Technology", "url": "https://longevity.technology/feed/"},
    {"name": "ScienceDaily Healthy Aging", "url": "https://www.sciencedaily.com/rss/health_medicine/healthy_aging.xml"},
    {"name": "ScienceDaily Dementia", "url": "https://www.sciencedaily.com/rss/mind_brain/dementia.xml"},
    {"name": "MedicalXpress Healthy Aging", "url": "https://medicalxpress.com/rss-feed/healthy-aging-news/"},
    {"name": "News-Medical Aging", "url": "https://www.news-medical.net/tag/feed/Aging.aspx"},
    {"name": "News-Medical Alzheimer", "url": "https://www.news-medical.net/tag/feed/Alzheimers-Disease.aspx"},
    {"name": "Google News · AI Longevity", "url": "https://news.google.com/rss/search?q=(AI%20OR%20%22artificial%20intelligence%22%20OR%20%22machine%20learning%22)%20(longevity%20OR%20aging%20OR%20%22biological%20age%22%20OR%20dementia%20OR%20alzheimer)&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Google News · Aging Clocks", "url": "https://news.google.com/rss/search?q=(%22biological%20age%22%20OR%20%22epigenetic%20clock%22%20OR%20%22aging%20clock%22%20OR%20%22brain%20age%22)%20(AI%20OR%20%22machine%20learning%22%20OR%20model)&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Google News · Senescence", "url": "https://news.google.com/rss/search?q=(senescence%20OR%20senolytic%20OR%20%22partial%20reprogramming%22%20OR%20rejuvenation)%20(AI%20OR%20%22machine%20learning%22%20OR%20biotech)&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Google News · Brain Age", "url": "https://news.google.com/rss/search?q=(%22brain%20age%22%20OR%20dementia%20OR%20alzheimer%20OR%20%22digital%20biomarker%22)%20(AI%20OR%20%22machine%20learning%22%20OR%20wearable)&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Google News · Aging Omics", "url": "https://news.google.com/rss/search?q=(%22single-cell%22%20OR%20%22multi-omics%22%20OR%20metabolomics%20OR%20proteomics)%20(aging%20OR%20senescence%20OR%20rejuvenation)%20(AI%20OR%20%22machine%20learning%22%20OR%20model)&hl=en-US&gl=US&ceid=US:en"},
    {"name": "Google News · Healthy Aging AI", "url": "https://news.google.com/rss/search?q=(frailty%20OR%20sarcopenia%20OR%20healthspan%20OR%20%22healthy%20aging%22)%20(AI%20OR%20%22machine%20learning%22%20OR%20wearable%20OR%20biomarker)&hl=en-US&gl=US&ceid=US:en"},
)

PAPERS_COOL_FEEDS: tuple[dict[str, str], ...] = (
    {"name": "Papers.cool q-bio", "url": "https://papers.cool/arxiv/q-bio/feed"},
    {"name": "Papers.cool cs.LG", "url": "https://papers.cool/arxiv/cs.LG/feed"},
    {"name": "Papers.cool cs.AI", "url": "https://papers.cool/arxiv/cs.AI/feed"},
    {"name": "Papers.cool cs.CV", "url": "https://papers.cool/arxiv/cs.CV/feed"},
    {"name": "Papers.cool stat.ML", "url": "https://papers.cool/arxiv/stat.ML/feed"},
    {"name": "Papers.cool physics.med-ph", "url": "https://papers.cool/arxiv/physics.med-ph/feed"},
)

PAPERS_COOL_AI_KEYWORDS = (
    "ai", "artificial intelligence", "machine learning", "deep learning", "foundation model",
    "transformer", "neural network", "self-supervised", "multimodal", "large language model",
    "llm", "diffusion",
)
PAPERS_COOL_BIO_KEYWORDS = (
    "aging", "ageing", "longevity", "biological age", "epigenetic clock", "brain age",
    "dementia", "alzheimer", "senescence", "senolytic", "geroscience", "healthspan",
    "biomarker", "protein", "drug discovery", "molecular", "genomic", "transcriptomic",
    "single-cell", "spatial transcriptomics", "cell segmentation", "omics", "neuron", "cognition",
)
PAPERS_COOL_STRONG_KEYWORDS = (
    "biological age", "epigenetic clock", "methylation clock", "proteomics clock", "brain age",
    "retinal age", "facial age", "senolytic", "geroscience", "healthspan", "alzheimer",
    "dementia", "aging clock", "single-cell", "spatial transcriptomics", "protein design", "drug discovery",
)

EUROPE_PMC_QUERIES = (
    'aging AND "machine learning"',
    '"biological age" AND "machine learning"',
    '("aging clock" OR "epigenetic clock" OR "brain age") AND ("machine learning" OR "artificial intelligence")',
    '(Alzheimer OR dementia OR neurodegeneration) AND ("machine learning" OR "deep learning")',
    '(senescence OR rejuvenation OR reprogramming OR senolytic) AND ("machine learning" OR "artificial intelligence")',
    '(frailty OR sarcopenia OR healthspan OR "digital biomarker") AND ("machine learning" OR "artificial intelligence" OR wearable)',
    '(("single-cell" OR "multi-omics" OR metabolomics OR proteomics OR inflammaging OR immunosenescence) AND (aging OR senescence OR longevity)) AND ("machine learning" OR "artificial intelligence" OR model)',
)

GITHUB_QUERIES = (
    '"aging clock" machine learning',
    '"biological age" deep learning',
    'longevity artificial intelligence',
    'alzheimer machine learning biomarker',
    '"brain age" deep learning',
    '"single-cell aging" machine learning',
)

AI_RADAR_URLS = (
    "https://radar.aivora.cn/data/latest-24h.json",
    "https://raw.githubusercontent.com/dongyu19920904/ai-news-radar/master/data/latest-24h.json",
    "https://api.github.com/repos/dongyu19920904/ai-news-radar/contents/data/latest-24h.json?ref=master",
)
CLINICALTRIALS_QUERY = '("artificial intelligence" OR "machine learning") AND (aging OR ageing OR longevity OR "biological age" OR Alzheimer OR dementia)'


@dataclass
class RawItem:
    site_id: str
    site_name: str
    source: str
    source_type: str
    title: str
    url: str
    published_at: datetime | None
    description: str = ""
    canonical_key: str = ""
    publication_stage: str = ""
    evidence_type: str = ""
    upstream_site_id: str = ""
    upstream_ai_is_related: bool | None = None
    upstream_ai_score: float | None = None


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def iso(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z") if value else None


def parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = dateparser.parse(str(value), tzinfos={"EDT": -4 * 3600, "EST": -5 * 3600, "PDT": -7 * 3600, "PST": -8 * 3600})
        if not parsed.tzinfo:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except (TypeError, ValueError, OverflowError):
        return None


def normalize_url(value: str) -> str:
    try:
        parsed = urlparse(str(value or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ""
        query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                 if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid", "ref", "source"}]
        path = parsed.path.rstrip("/") or "/"
        return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", urlencode(query), ""))
    except Exception:
        return ""


def canonical_key(*, url: str, doi: str = "", pmid: str = "", repo: str = "") -> str:
    if doi:
        return f"doi:{doi.lower().removeprefix('https://doi.org/')}"
    if pmid:
        return f"pmid:{pmid}"
    if repo:
        return f"repo:{repo.lower()}"
    return f"url:{normalize_url(url)}"


def make_id(key: str) -> str:
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, application/rss+xml, application/xml, text/xml, */*"})
    return session


def contains_keyword(text: str, keyword: str) -> bool:
    normalized = str(keyword or "").strip().lower()
    if not normalized:
        return False
    if normalized.isascii() and normalized.isalnum():
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", text))
    return normalized in text


def papers_cool_topic_match(title: str, description: str) -> bool:
    text = f"{title}\n{description}".lower()
    has_ai = any(contains_keyword(text, word) for word in PAPERS_COOL_AI_KEYWORDS)
    has_bio = any(contains_keyword(text, word) for word in PAPERS_COOL_BIO_KEYWORDS)
    has_strong = any(contains_keyword(text, word) for word in PAPERS_COOL_STRONG_KEYWORDS)
    return (has_ai and has_bio) or has_strong


def fetch_rss_sources(session: requests.Session, now: datetime) -> tuple[list[RawItem], dict[str, Any]]:
    items: list[RawItem] = []
    def fetch_one(feed: dict[str, str]) -> tuple[list[RawItem], dict[str, Any]]:
        started = time.perf_counter()
        feed_items: list[RawItem] = []
        error = None
        try:
            response = create_session().get(feed["url"], timeout=12)
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
            for entry in parsed.entries[:50]:
                title = re.sub(r"\s+", " ", str(entry.get("title") or "")).strip()
                url = normalize_url(str(entry.get("link") or ""))
                published = parse_date(entry.get("published") or entry.get("updated"))
                if not title or not url or (published and published < now - timedelta(days=7)):
                    continue
                summary = re.sub(r"<[^>]+>", " ", str(entry.get("summary") or entry.get("description") or ""))
                feed_items.append(RawItem(
                    site_id="official_rss", site_name="机构与行业 RSS", source=feed["name"], source_type="news",
                    title=title, url=url, published_at=published, description=re.sub(r"\s+", " ", summary)[:1000],
                    canonical_key=canonical_key(url=url), publication_stage="secondary_report", evidence_type="news",
                ))
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"[:240]
        status = {
            "feed_name": feed["name"], "feed_url": feed["url"], "ok": error is None,
            "item_count": len(feed_items), "duration_ms": int((time.perf_counter() - started) * 1000), "error": error,
        }
        return feed_items, status

    with ThreadPoolExecutor(max_workers=len(OFFICIAL_FEEDS)) as executor:
        results = list(executor.map(fetch_one, OFFICIAL_FEEDS))
    feed_statuses = [status for _, status in results]
    for rows, _ in results:
        items.extend(rows)
    failed = [row["feed_name"] for row in feed_statuses if not row["ok"]]
    return items, {
        "site_id": "official_rss", "site_name": "机构与行业 RSS", "ok": len(failed) < len(feed_statuses),
        "partial_failures": len(failed), "item_count": len(items), "duration_ms": max((row["duration_ms"] for row in feed_statuses), default=0),
        "error": f"{len(failed)} feeds failed" if failed else None, "feeds": feed_statuses,
    }


def fetch_papers_cool(session: requests.Session, now: datetime) -> tuple[list[RawItem], dict[str, Any]]:
    items: list[RawItem] = []

    def fetch_one(feed: dict[str, str]) -> tuple[list[RawItem], dict[str, Any]]:
        started = time.perf_counter()
        feed_items: list[RawItem] = []
        error = None
        try:
            response = create_session().get(feed["url"], timeout=15)
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
            for entry in parsed.entries[:20]:
                title = re.sub(r"\s+", " ", str(entry.get("title") or "")).strip()
                url = normalize_url(str(entry.get("link") or ""))
                published = parse_date(entry.get("published") or entry.get("updated"))
                summary = re.sub(r"<[^>]+>", " ", str(entry.get("summary") or entry.get("description") or ""))
                summary = re.sub(r"\s+", " ", summary).strip()
                if (
                    not title
                    or not url
                    or (published and published < now - timedelta(days=7))
                    or not papers_cool_topic_match(title, summary)
                ):
                    continue
                feed_items.append(RawItem(
                    site_id="papers_cool", site_name="Papers.cool 论文精选", source=feed["name"], source_type="paper",
                    title=title, url=url, published_at=published, description=summary[:1000],
                    canonical_key=canonical_key(url=url), publication_stage="preprint", evidence_type="preprint",
                ))
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"[:240]
        return feed_items, {
            "feed_name": feed["name"], "feed_url": feed["url"], "ok": error is None,
            "item_count": len(feed_items), "duration_ms": int((time.perf_counter() - started) * 1000), "error": error,
        }

    with ThreadPoolExecutor(max_workers=len(PAPERS_COOL_FEEDS)) as executor:
        results = list(executor.map(fetch_one, PAPERS_COOL_FEEDS))
    feed_statuses = [status for _, status in results]
    for rows, _ in results:
        items.extend(rows)
    failed = [row["feed_name"] for row in feed_statuses if not row["ok"]]
    return items, {
        "site_id": "papers_cool", "site_name": "Papers.cool 论文精选", "ok": len(failed) < len(feed_statuses),
        "partial_failures": len(failed), "item_count": len(items),
        "duration_ms": max((row["duration_ms"] for row in feed_statuses), default=0),
        "error": f"{len(failed)} feeds failed" if failed else None, "feeds": feed_statuses,
    }


def fetch_europe_pmc(session: requests.Session, now: datetime) -> tuple[list[RawItem], dict[str, Any]]:
    started = time.perf_counter()
    items: list[RawItem] = []
    errors: list[str] = []

    def fetch_query(query: str) -> list[RawItem]:
        query_items: list[RawItem] = []
        try:
            start_date = (now - timedelta(days=7)).date().isoformat()
            end_date = now.date().isoformat()
            dated_query = f"FIRST_PDATE:[{start_date} TO {end_date}] AND ({query})"
            response = create_session().get(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                params={"query": dated_query, "format": "json", "resultType": "core", "pageSize": 35}, timeout=15,
            )
            response.raise_for_status()
            for row in response.json().get("resultList", {}).get("result", []):
                title = re.sub(r"\s+", " ", str(row.get("title") or "")).strip()
                pmid = str(row.get("pmid") or "").strip()
                doi = str(row.get("doi") or "").strip()
                result_id = pmid or str(row.get("id") or "").strip()
                if not title or not result_id:
                    continue
                url = f"https://europepmc.org/article/MED/{result_id}"
                pub_type_list = (row.get("pubTypeList") or {}).get("pubType") or []
                pub_types = " ".join(str(value) for value in pub_type_list if value)
                description = " ".join(filter(None, [
                    str(row.get("abstractText") or ""), str(row.get("authorString") or ""),
                    str(row.get("journalTitle") or ""), pub_types, str(row.get("pubType") or ""),
                ]))
                journal_info = row.get("journalInfo") or {}
                stage = "preprint" if "preprint" in pub_types.lower() else "peer_review_status_unknown"
                query_items.append(RawItem(
                    site_id="europepmc", site_name="Europe PMC", source=str(row.get("journalTitle") or "Europe PMC"),
                    source_type="paper", title=title, url=url, published_at=parse_date(row.get("firstPublicationDate") or journal_info.get("printPublicationDate")),
                    description=description, canonical_key=canonical_key(url=url, doi=doi, pmid=pmid),
                    publication_stage=stage, evidence_type="paper",
                ))
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}"[:180])
        return query_items

    with ThreadPoolExecutor(max_workers=len(EUROPE_PMC_QUERIES)) as executor:
        for rows in executor.map(fetch_query, EUROPE_PMC_QUERIES):
            items.extend(rows)
    error = f"{len(errors)} queries failed: {errors[0]}"[:240] if errors else None
    return items, {
        "site_id": "europepmc", "site_name": "Europe PMC", "ok": len(errors) < len(EUROPE_PMC_QUERIES),
        "partial_failures": len(errors),
        "item_count": len(items), "duration_ms": int((time.perf_counter() - started) * 1000), "error": error,
    }


def fetch_clinical_trials(session: requests.Session, now: datetime) -> tuple[list[RawItem], dict[str, Any]]:
    started = time.perf_counter()
    items: list[RawItem] = []
    error = None
    try:
        response = session.get(
            "https://clinicaltrials.gov/api/v2/studies",
            params={"query.term": CLINICALTRIALS_QUERY, "pageSize": 50, "format": "json"}, timeout=25,
        )
        response.raise_for_status()
        for study in response.json().get("studies", []):
            protocol = study.get("protocolSection") or {}
            identity = protocol.get("identificationModule") or {}
            status = protocol.get("statusModule") or {}
            conditions = protocol.get("conditionsModule") or {}
            design = protocol.get("designModule") or {}
            description_module = protocol.get("descriptionModule") or {}
            nct_id = str(identity.get("nctId") or "").strip()
            title = re.sub(r"\s+", " ", str(identity.get("briefTitle") or identity.get("officialTitle") or "")).strip()
            if not nct_id or not title:
                continue
            url = f"https://clinicaltrials.gov/study/{nct_id}"
            text_parts = [
                " ".join(str(value) for value in conditions.get("conditions", []) if value),
                str(description_module.get("briefSummary") or ""),
                str(design.get("studyType") or ""),
            ]
            posted = (status.get("studyFirstPostDateStruct") or {}).get("date")
            updated = (status.get("lastUpdatePostDateStruct") or {}).get("date") or posted
            items.append(RawItem(
                site_id="clinicaltrials", site_name="ClinicalTrials.gov", source=nct_id, source_type="trial",
                title=title, url=url, published_at=parse_date(updated or posted),
                description=re.sub(r"\s+", " ", " ".join(text_parts))[:1000],
                canonical_key=f"nct:{nct_id.lower()}", publication_stage="registered_trial", evidence_type="trial_registry",
            ))
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"[:240]
    return items, {
        "site_id": "clinicaltrials", "site_name": "ClinicalTrials.gov", "ok": error is None,
        "item_count": len(items), "duration_ms": int((time.perf_counter() - started) * 1000), "error": error,
    }


def fetch_github_projects(session: requests.Session, now: datetime) -> tuple[list[RawItem], dict[str, Any]]:
    started = time.perf_counter()
    items: list[RawItem] = []
    errors: list[str] = []

    def fetch_query(query: str) -> list[RawItem]:
        query_items: list[RawItem] = []
        try:
            response = create_session().get(
                "https://api.github.com/search/repositories",
                params={"q": f"{query} archived:false", "sort": "updated", "order": "desc", "per_page": 15}, timeout=15,
            )
            response.raise_for_status()
            for repo in response.json().get("items", []):
                full_name = str(repo.get("full_name") or "").strip()
                url = normalize_url(str(repo.get("html_url") or ""))
                if not full_name or not url:
                    continue
                query_items.append(RawItem(
                    site_id="github_projects", site_name="GitHub 研究项目", source=full_name, source_type="project",
                    title=f"{full_name}: {repo.get('description') or 'AI longevity research project'}", url=url,
                    published_at=parse_date(repo.get("pushed_at") or repo.get("updated_at")),
                    description=f"GitHub open source software. Stars: {repo.get('stargazers_count', 0)}. Language: {repo.get('language') or 'unknown'}.",
                    canonical_key=canonical_key(url=url, repo=full_name), publication_stage="software_project", evidence_type="project",
                ))
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}"[:180])
        return query_items

    with ThreadPoolExecutor(max_workers=len(GITHUB_QUERIES)) as executor:
        for rows in executor.map(fetch_query, GITHUB_QUERIES):
            items.extend(rows)
    error = f"{len(errors)} queries failed: {errors[0]}"[:240] if errors else None
    return items, {
        "site_id": "github_projects", "site_name": "GitHub 研究项目", "ok": len(errors) < len(GITHUB_QUERIES),
        "partial_failures": len(errors),
        "item_count": len(items), "duration_ms": int((time.perf_counter() - started) * 1000), "error": error,
    }


def ai_radar_site_id(value: Any) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return f"ai_radar_{slug or 'unknown'}"


def optional_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def fetch_ai_radar_bridge(session: requests.Session, now: datetime) -> tuple[list[RawItem], dict[str, Any]]:
    started = time.perf_counter()
    items: list[RawItem] = []
    error = None
    endpoint_used = None
    endpoint_errors: list[str] = []
    upstream_counts: Counter[str] = Counter()
    upstream_names: dict[str, str] = {}
    payload: dict[str, Any] | None = None
    for endpoint in AI_RADAR_URLS:
        try:
            response = session.get(endpoint, timeout=24)
            response.raise_for_status()
            candidate = response.json()
            if isinstance(candidate, dict) and candidate.get("encoding") == "none" and candidate.get("git_url"):
                blob_url = str(candidate["git_url"])
                parsed_blob_url = urlparse(blob_url)
                if parsed_blob_url.scheme != "https" or parsed_blob_url.hostname != "api.github.com":
                    raise ValueError("GitHub contents response returned an unsafe git_url")
                blob_response = session.get(blob_url, timeout=30)
                blob_response.raise_for_status()
                candidate = blob_response.json()
            if isinstance(candidate, dict) and candidate.get("encoding") == "base64" and candidate.get("content"):
                candidate = json.loads(base64.b64decode(str(candidate["content"])).decode("utf-8"))
            if not isinstance(candidate, dict) or not isinstance(candidate.get("items"), list):
                raise ValueError("response does not contain an items list")
            payload = candidate
            endpoint_used = endpoint
            break
        except Exception as exc:
            endpoint_errors.append(f"{endpoint}: {type(exc).__name__}: {exc}"[:300])

    if payload is None:
        error = f"all endpoints failed: {' | '.join(endpoint_errors)}"[:600]
    else:
        for row in payload["items"]:
            if not isinstance(row, dict):
                continue
            url = normalize_url(str(row.get("url") or ""))
            title = str(row.get("title_original") or row.get("title") or "").strip()
            if not title or not url:
                continue
            upstream_site_id = str(row.get("site_id") or "unknown").strip() or "unknown"
            upstream_site_name = str(row.get("site_name") or upstream_site_id).strip() or upstream_site_id
            upstream_counts[upstream_site_id] += 1
            upstream_names[upstream_site_id] = upstream_site_name
            items.append(RawItem(
                site_id=ai_radar_site_id(upstream_site_id), site_name=f"爱窝啦 AI雷达 · {upstream_site_name}",
                source=str(row.get("source") or upstream_site_name),
                source_type="news", title=title, url=url, published_at=parse_date(row.get("published_at") or row.get("first_seen_at")),
                canonical_key=canonical_key(url=url), publication_stage="secondary_report", evidence_type="news",
                upstream_site_id=upstream_site_id, upstream_ai_is_related=row.get("ai_is_related"),
                upstream_ai_score=optional_float(row.get("ai_score")),
            ))
    upstream_sources = [
        {"site_id": site_id, "site_name": upstream_names[site_id], "item_count": count}
        for site_id, count in upstream_counts.most_common()
    ]
    return items, {
        "site_id": "ai_radar_bridge", "site_name": "爱窝啦 AI雷达", "ok": error is None,
        "item_count": len(items), "source_count": len(upstream_sources), "upstream_sources": upstream_sources,
        "endpoint_used": endpoint_used, "fallback_errors": endpoint_errors,
        "duration_ms": int((time.perf_counter() - started) * 1000), "error": error,
    }


def load_archive(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("items", payload) if isinstance(payload, dict) else []
        return {str(row["canonical_key"]): row for row in rows if isinstance(row, dict) and row.get("canonical_key")}
    except (json.JSONDecodeError, OSError):
        return {}


def raw_to_record(raw: RawItem, now: datetime, archive: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    url = normalize_url(raw.url)
    if not raw.title.strip() or not url:
        return None
    key = raw.canonical_key or canonical_key(url=url)
    prior = archive.get(key, {})
    record = {
        "id": make_id(key), "canonical_key": key, "site_id": raw.site_id, "site_name": raw.site_name,
        "source": raw.source, "source_type": raw.source_type, "title": raw.title.strip(), "url": url,
        "published_at": iso(raw.published_at), "first_seen_at": prior.get("first_seen_at") or iso(now), "last_seen_at": iso(now),
        "description": raw.description[:1000], "publication_stage": raw.publication_stage, "evidence_type": raw.evidence_type,
    }
    if raw.upstream_site_id:
        record.update({
            "upstream_site_id": raw.upstream_site_id, "upstream_ai_is_related": raw.upstream_ai_is_related,
            "upstream_ai_score": raw.upstream_ai_score,
        })
    return add_longevity_fields(record)


def event_time(record: dict[str, Any]) -> datetime | None:
    return parse_date(record.get("published_at")) or parse_date(record.get("first_seen_at"))


def record_freshness_score(record: dict[str, Any], now: datetime, window_hours: int) -> float:
    timestamp = event_time(record)
    if not timestamp:
        return 0.0
    age_hours = max(0.0, (now - timestamp).total_seconds() / 3600)
    return round(max(0.0, 1.0 - age_hours / max(1, window_hours)), 3)


def select_relevant_records(
    records: list[dict[str, Any]], *, now: datetime, core_window_hours: int = CORE_WINDOW_HOURS,
    related_window_hours: int = RELATED_WINDOW_HOURS, limit: int = RELEVANT_LIMIT,
) -> list[dict[str, Any]]:
    """Select the useful rolling layer without filling it from generic AI rows."""
    core_cutoff = now - timedelta(hours=core_window_hours)
    related_cutoff = now - timedelta(hours=related_window_hours)
    candidates: list[dict[str, Any]] = []
    for record in records:
        timestamp = event_time(record)
        tier = str(record.get("relevance_tier") or "all")
        if not timestamp or tier not in {"core", "related"}:
            continue
        if tier == "core" and timestamp < core_cutoff:
            continue
        if tier == "related" and timestamp < related_cutoff:
            continue
        candidates.append({
            **record,
            "freshness_score": record_freshness_score(record, now, core_window_hours if tier == "core" else related_window_hours),
        })

    candidates.sort(key=lambda row: (
        1 if row.get("relevance_tier") == "core" else 0,
        row.get("signal_score", 0), row.get("domain_score", 0), row.get("freshness_score", 0),
        event_time(row) or datetime.min.replace(tzinfo=UTC),
    ), reverse=True)

    selected: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    site_counts: Counter[str] = Counter()
    topic_counts: Counter[str] = Counter()
    site_cap = max(8, int(limit * 0.30))
    topic_cap = max(12, int(limit * 0.40))
    for row in candidates:
        site_id = str(row.get("site_id") or "unknown")
        topic = str(row.get("primary_topic") or "ai_longevity")
        if site_counts[site_id] >= site_cap or topic_counts[topic] >= topic_cap:
            deferred.append(row)
            continue
        selected.append(row)
        site_counts[site_id] += 1
        topic_counts[topic] += 1
        if len(selected) >= limit:
            return selected

    for row in deferred:
        selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for record in records:
        key = str(record.get("canonical_key") or canonical_key(url=str(record.get("url") or "")))
        existing = best.get(key)
        if not existing or (record.get("signal_score", 0), event_time(record) or datetime.min.replace(tzinfo=UTC)) > (
            existing.get("signal_score", 0), event_time(existing) or datetime.min.replace(tzinfo=UTC)
        ):
            best[key] = record
    return sorted(best.values(), key=lambda row: (event_time(row) or datetime.min.replace(tzinfo=UTC), row.get("signal_score", 0)), reverse=True)


def public_item(record: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "id", "canonical_key", "site_id", "site_name", "source", "source_type", "title", "title_zh", "title_en",
        "url", "published_at", "first_seen_at", "last_seen_at", "ai_is_related", "ai_score",
        "longevity_is_related", "longevity_score", "signal_score", "domain_score", "freshness_score",
        "relevance_tier", "relevance_path", "selection_reason", "topics", "primary_topic", "study_subject",
        "publication_stage", "evidence_type", "risk_flags", "relevance_reason", "ai_signals", "longevity_signals",
        "noise_signals", "demographic_noise_signals", "non_biological_noise_signals",
        "biomedical_signals", "biological_context_signals", "upstream_site_id", "upstream_ai_is_related", "upstream_ai_score",
    )
    return {key: record.get(key) for key in allowed if key in record}


def load_title_cache(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {str(key): str(value) for key, value in data.items() if str(key).strip() and str(value).strip()}
    except (json.JSONDecodeError, OSError, AttributeError):
        return {}


def has_cjk(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value or ""))


def has_mojibake(value: str) -> bool:
    text = value or ""
    return "�" in text or text.count("?") >= 3 or any(marker in text for marker in ("��", "Ŧ", "ѧ", "˹"))


def translate_title(session: requests.Session, title: str) -> str | None:
    try:
        response = session.get(
            "https://api.mymemory.translated.net/get",
            params={"q": title, "langpair": "en|zh-CN"}, timeout=20,
        )
        response.raise_for_status()
        response.encoding = "utf-8"
        translated = str((response.json().get("responseData") or {}).get("translatedText") or "").strip()
        if translated and translated.lower() != title.lower() and has_cjk(translated) and not has_mojibake(translated):
            return translated
    except Exception:
        pass
    try:
        response = session.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "auto", "tl": "zh-CN", "dt": "t", "q": title}, timeout=12,
        )
        response.raise_for_status()
        response.encoding = "utf-8"
        segments = response.json()[0]
        translated = "".join(str(segment[0]) for segment in segments if isinstance(segment, list) and segment and segment[0]).strip()
        return translated if translated and translated != title and has_cjk(translated) and not has_mojibake(translated) else None
    except Exception:
        return None


def add_bilingual_titles(items: list[dict[str, Any]], cache: dict[str, str], max_new: int = 24) -> int:
    translated_count = 0
    session = create_session()
    for item in items:
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        if has_cjk(title):
            item["title_zh"] = title
            continue
        item["title_en"] = title
        translated = cache.get(title)
        if not translated and translated_count < max_new:
            translated = translate_title(session, title)
            if translated:
                cache[title] = translated
                translated_count += 1
        if translated:
            item["title_zh"] = translated
    return translated_count


def build_briefing(items: list[dict[str, Any]], generated_at: str, window_hours: int) -> dict[str, Any]:
    candidates = sorted(items, key=lambda row: (
        1 if row.get("relevance_tier") == "core" else 0,
        row.get("signal_score", 0), row.get("domain_score", 0),
        event_time(row) or datetime.min.replace(tzinfo=UTC),
    ), reverse=True)
    selected: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    for row in candidates:
        source_key = f"{row.get('site_id')}::{row.get('source')}"
        if source_key in seen_sources:
            continue
        selected.append(row)
        seen_sources.add(source_key)
        if len(selected) >= BRIEFING_LIMIT:
            break
    compact = [{key: row.get(key) for key in (
        "id", "title", "title_zh", "title_en", "url", "source", "site_id", "source_type", "published_at",
        "signal_score", "domain_score", "freshness_score", "relevance_tier", "relevance_path", "selection_reason",
        "primary_topic", "study_subject", "publication_stage", "risk_flags",
    )} for row in selected]
    return {
        "schema_version": "bio-radar-v1", "generated_at": generated_at, "window_hours": window_hours,
        "selection_mode": "core_first_related_fallback", "item_count": len(compact),
        "source_count": len(seen_sources), "items": compact,
    }


def generate(output_dir: Path, *, window_hours: int = 24, archive_days: int = 21, now: datetime | None = None) -> dict[str, Any]:
    now = now or utc_now()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / "archive.json"
    old_archive = load_archive(archive_path)
    collectors: tuple[Callable[[requests.Session, datetime], tuple[list[RawItem], dict[str, Any]]], ...] = (
        fetch_europe_pmc, fetch_clinical_trials, fetch_rss_sources, fetch_papers_cool,
        fetch_github_projects, fetch_ai_radar_bridge,
    )
    raw_items: list[RawItem] = []
    statuses: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=len(collectors)) as executor:
        results = list(executor.map(lambda collector: collector(create_session(), now), collectors))
    for rows, status in results:
        raw_items.extend(rows)
        statuses.append(status)

    records = [row for raw in raw_items if (row := raw_to_record(raw, now, old_archive))]
    records = dedupe_records(records)
    archive_cutoff = now - timedelta(days=archive_days)
    archive_records: dict[str, dict[str, Any]] = {}
    for row in list(old_archive.values()) + records:
        if (event_time(row) or now) >= archive_cutoff:
            # Re-score still-live archive rows so additive relevance fields and
            # rule improvements take effect immediately after a deployment.
            refreshed = add_longevity_fields(row)
            archive_records[str(refreshed["canonical_key"])] = refreshed
    # A transient source failure must not erase still-fresh public signals.
    all_recent = dedupe_records([
        row for row in archive_records.values()
        if (event_time(row) or now) >= now - timedelta(hours=window_hours)
    ])
    focused = [row for row in all_recent if row.get("is_related")]
    focused.sort(key=lambda row: (row.get("signal_score", 0), event_time(row) or datetime.min.replace(tzinfo=UTC)), reverse=True)
    relevant = select_relevant_records(
        dedupe_records(list(archive_records.values())), now=now,
        core_window_hours=CORE_WINDOW_HOURS, related_window_hours=min(archive_days * 24, RELATED_WINDOW_HOURS),
        limit=RELEVANT_LIMIT,
    )
    core_rolling = [row for row in relevant if row.get("relevance_tier") == "core"]
    all_recent.sort(key=lambda row: event_time(row) or datetime.min.replace(tzinfo=UTC), reverse=True)
    title_cache_path = output_dir / "title-zh-cache.json"
    title_cache = load_title_cache(title_cache_path)
    title_cache = {key: value for key, value in title_cache.items() if has_cjk(value) and not has_mojibake(value)}
    translated_count = add_bilingual_titles(relevant, title_cache)
    for row in focused + all_recent:
        if not has_cjk(str(row.get("title") or "")):
            row["title_en"] = row.get("title")
        if row.get("title") in title_cache:
            row["title_zh"] = title_cache[str(row["title"])]

    generated_at = iso(now) or ""
    site_stats = []
    for site_id, count in Counter(str(row.get("site_id") or "unknown") for row in focused).most_common():
        sample = next(row for row in focused if row.get("site_id") == site_id)
        site_stats.append({"site_id": site_id, "site_name": sample.get("site_name") or site_id, "count": count, "raw_count": sum(1 for row in all_recent if row.get("site_id") == site_id)})

    relevant_site_stats = []
    for site_id, count in Counter(str(row.get("site_id") or "unknown") for row in relevant).most_common():
        sample = next(row for row in relevant if row.get("site_id") == site_id)
        relevant_site_stats.append({
            "site_id": site_id, "site_name": sample.get("site_name") or site_id, "count": count,
            "raw_count": sum(1 for row in archive_records.values() if row.get("site_id") == site_id),
        })

    latest_payload = {
        "schema_version": "bio-radar-v1", "generated_at": generated_at, "window_hours": window_hours,
        "total_items": len(focused), "total_items_raw": len(all_recent), "total_items_all_mode": len(all_recent),
        "archive_total": len(archive_records), "site_count": len({row.get("site_id") for row in focused}),
        "source_count": len({f"{row.get('site_id')}::{row.get('source')}" for row in focused}), "site_stats": site_stats,
        "items": [public_item(row) for row in focused], "items_ai": [public_item(row) for row in focused],
        "relevant_data_url": "data/latest-relevant.json",
        "all_mode_data_url": "data/latest-24h-all.json",
        "methodology_url": "https://radar.aibioo.cn/methodology.html",
        "medical_disclaimer": "Research signal index only; not medical advice, diagnosis, or treatment guidance.",
    }
    relevant_payload = {
        "schema_version": "bio-radar-v1", "generated_at": generated_at,
        "window_hours": min(archive_days * 24, RELATED_WINDOW_HOURS),
        "core_window_hours": CORE_WINDOW_HOURS,
        "related_window_hours": min(archive_days * 24, RELATED_WINDOW_HOURS),
        "selection_limit": RELEVANT_LIMIT,
        "total_items": len(relevant), "total_core_items": len(core_rolling),
        "total_related_items": sum(1 for row in relevant if row.get("relevance_tier") == "related"),
        "total_items_raw": len(all_recent), "total_items_all_mode": len(all_recent),
        "site_count": len({row.get("site_id") for row in relevant}),
        "source_count": len({f"{row.get('site_id')}::{row.get('source')}" for row in relevant}),
        "site_stats": relevant_site_stats,
        "items": [public_item(row) for row in relevant],
        "items_relevant": [public_item(row) for row in relevant],
        "items_core": [public_item(row) for row in core_rolling],
        "strict_24h_data_url": "data/latest-24h.json",
        "all_mode_data_url": "data/latest-24h-all.json",
        "selection_policy": "7d core + 21d related; no generic AI fill",
        "methodology_url": "https://radar.aibioo.cn/methodology.html",
        "medical_disclaimer": "Research signal index only; not medical advice, diagnosis, or treatment guidance.",
    }
    all_payload = {
        "schema_version": "bio-radar-v1", "generated_at": generated_at, "window_hours": window_hours,
        "total_items_raw": len(all_recent), "total_items_all_mode": len(all_recent),
        "items_all": [public_item(row) for row in all_recent], "items_all_raw": [public_item(row) for row in all_recent],
    }
    status_payload = {
        "schema_version": "bio-radar-v1", "generated_at": generated_at, "sites": statuses,
        "successful_sites": sum(1 for row in statuses if row.get("ok")),
        "failed_sites": [row["site_id"] for row in statuses if not row.get("ok")],
        "partial_sites": [row["site_id"] for row in statuses if row.get("partial_failures")],
        "zero_item_sites": [row["site_id"] for row in statuses if row.get("ok") and not row.get("item_count")],
        "fetched_raw_items": len(raw_items), "items_before_topic_filter": len(all_recent), "items_in_24h": len(focused),
        "items_core_7d": len(core_rolling), "items_relevant_21d": len(relevant),
        "relevance_tiers": dict(Counter(str(row.get("relevance_tier") or "all") for row in relevant)),
    }
    topic_payload = {
        "schema_version": "bio-radar-v1", "generated_at": generated_at,
        "topics": dict(Counter(topic for row in focused for topic in row.get("topics", []))),
        "source_types": dict(Counter(str(row.get("source_type") or "unknown") for row in focused)),
        "study_subjects": dict(Counter(str(row.get("study_subject") or "unknown") for row in focused)),
        "publication_stages": dict(Counter(str(row.get("publication_stage") or "unknown") for row in focused)),
        "relevant_topics": dict(Counter(topic for row in relevant for topic in row.get("topics", []))),
        "relevance_tiers": dict(Counter(str(row.get("relevance_tier") or "all") for row in relevant)),
    }
    payloads = {
        "latest-24h.json": latest_payload, "latest-relevant.json": relevant_payload,
        "latest-24h-all.json": all_payload,
        "briefing-lite.json": build_briefing(relevant, generated_at, min(archive_days * 24, RELATED_WINDOW_HOURS)),
        "source-status.json": status_payload, "topic-stats.json": topic_payload,
        "title-zh-cache.json": title_cache,
        "archive.json": {"schema_version": "bio-radar-v1", "generated_at": generated_at, "items": list(archive_records.values())},
    }
    for name, payload in payloads.items():
        (output_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "generated_at": generated_at, "focused": len(focused), "all": len(all_recent),
        "focused_24h": len(focused), "core_7d": len(core_rolling),
        "relevant_21d": len(relevant), "all_24h": len(all_recent), "archive": len(archive_records),
        "translated": translated_count, "failed_sites": status_payload["failed_sites"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the AI Longevity Radar snapshots")
    parser.add_argument("--output-dir", default="data")
    parser.add_argument("--window-hours", type=int, default=24)
    parser.add_argument("--archive-days", type=int, default=21)
    args = parser.parse_args()
    summary = generate(Path(args.output_dir), window_hours=max(1, args.window_hours), archive_days=max(1, args.archive_days))
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
