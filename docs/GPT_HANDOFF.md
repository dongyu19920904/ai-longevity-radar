# AI Longevity Radar handoff

- Repository: `dongyu19920904/ai-longevity-radar`
- Production: `https://radar.aibioo.cn/`
- Main workflow: `.github/workflows/update-news.yml`
- Data generator: `scripts/update_longevity_radar.py`
- Explainable scorer: `scripts/longevity_relevance.py`
- Public integration payload: `data/briefing-lite.json`
- Contract version: `bio-radar-v1`

The repository is a clean source snapshot adaptation, not a fork with shared history. It contains no copied archive, private OPML, credentials, or generic-radar generated data. AI Longevity Daily integration must remain fail-open: a JSON fetch failure can hide the radar card, but must never block the Daily build or page.
