# Source coverage and evidence boundaries

## Default collectors

| Collector | Role | Canonical entity key | Failure behavior |
|---|---|---|---|
| Europe PMC | Paper metadata | DOI, then PMID | Isolated |
| ClinicalTrials.gov API v2 | Trial registry metadata | NCT identifier | Isolated |
| Public RSS feeds | Institutions and longevity industry | Normalized URL | Per-feed isolated |
| GitHub Search API | Open research software | `owner/repo` | Isolated |
| Aivora AI Radar JSON | General-AI candidate bridge | Normalized URL | Optional and isolated |

The AI Radar bridge is a discovery supplement, not a dependency or evidence authority. Every bridged item is scored again for longevity relevance.

## Source admission criteria

New default sources should be public, timestamped, attributable, stable enough for unattended hourly access, and useful for AI × longevity coverage. Prefer primary metadata over summaries. Do not add account-bound timelines, login-only pages, private newsletters, health records, or sources whose terms prohibit automated access.

## Evidence labels

The pipeline separates source type, study subject, publication stage, topic, and risk flags. Missing facts stay `unknown`. `paper`, `trial`, `project`, and `news` describe record provenance; they do not establish quality or efficacy.

## Availability contract

Each collector returns a status record. A collector error is written to `data/source-status.json` and does not fail the overall update. Existing archive entries still inside the requested time window remain eligible, preventing a transient outage from erasing the feed.
