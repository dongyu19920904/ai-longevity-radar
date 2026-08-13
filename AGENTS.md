# AI Longevity Radar Agent Notes

## Scope

This repository powers the public AI Longevity Radar at `radar.aibioo.cn`. It must remain independently buildable and deployable from AI Longevity Daily.

## Working rules

- Prefer stable public APIs, RSS/Atom feeds, and primary research metadata.
- Preserve `bio-radar-v1` public JSON compatibility; version breaking changes.
- Never infer clinical efficacy from a title or score.
- Keep unknown research subjects and publication stages explicitly unknown.
- Isolate source failures and retain still-fresh archived records.
- Do not commit credentials, cookies, private feeds, personal health data, or generated secrets.
- Do not reintroduce source-repository history or generic AI Radar data files.

## Validation

```powershell
python -m pytest -q -p no:cacheprovider
node --test tests/frontend-core.test.cjs tests/frontend-contract.test.cjs
node --check assets/core.js
node --check assets/app.js
python scripts/update_longevity_radar.py --output-dir data --window-hours 24 --archive-days 21
```

On Windows, follow the workspace `project-cache-hygiene` policy and keep task caches under `D:\CodexCache`.
