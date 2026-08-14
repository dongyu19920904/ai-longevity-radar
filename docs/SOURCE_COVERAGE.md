# Source coverage and evidence boundaries

## Default collectors

| Collector | Role | Canonical entity key | Failure behavior |
|---|---|---|---|
| Europe PMC | Paper metadata | DOI, then PMID | Isolated |
| ClinicalTrials.gov API v2 | Trial registry metadata | NCT identifier | Isolated |
| Public RSS feeds | Institutions and longevity industry | Normalized URL | Per-feed isolated |
| GitHub Search API | Open research software | `owner/repo` | Isolated |
| Aivora AI Radar JSON | Full general-AI source bridge | Normalized URL | Optional and isolated |

The AI Radar bridge consumes its curated `latest-24h.json` feed and preserves each upstream `site_id`, `site_name`, source label, AI relevance decision, and AI score. The public upstream groups are Official AI Updates, AI Breakfast, Follow Builders, TechURLs, Buzzing, Info Flow, BestBlogs, TopHub, Zeli, AI HubToday, AIbase, AI HOT, NewsNow, plus any public OPML RSS rows present in the upstream snapshot. A group may legitimately contribute zero rows during a particular 24-hour window.

The website opens the deduplicated full-source layer by default: the complete upstream AI feed plus the longevity-specific collectors above. The bridge prefers the custom-domain JSON and automatically retries the same public snapshot through GitHub Raw and the GitHub Contents API; the selected endpoint and earlier endpoint errors are recorded in source status. The `AI + longevity` view, `latest-24h.json`, and `briefing-lite.json` remain the stricter intersection. Every bridged item is scored again for longevity relevance; an upstream AI score is traceability metadata, not longevity evidence.

## Source admission criteria

New default sources should be public, timestamped, attributable, stable enough for unattended hourly access, and useful for AI × longevity coverage. Prefer primary metadata over summaries. Do not add account-bound timelines, login-only pages, private newsletters, health records, or sources whose terms prohibit automated access.

## Evidence labels

The pipeline separates source type, study subject, publication stage, topic, and risk flags. Missing facts stay `unknown`. `paper`, `trial`, `project`, and `news` describe record provenance; they do not establish quality or efficacy.

## Availability contract

Each collector returns a status record. A collector error is written to `data/source-status.json` and does not fail the overall update. Existing archive entries still inside the requested time window remain eligible, preventing a transient outage from erasing the feed.
