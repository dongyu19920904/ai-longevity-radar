(function initCore(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.AILongevityRadarCore = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function buildCore() {
  "use strict";

  const MAX_TAKEAWAY_LENGTH = 180;

  function safeHttpUrl(value) {
    if (typeof value !== "string" || !value.trim()) return "";
    try {
      const parsed = new URL(value.trim());
      return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : "";
    } catch {
      return "";
    }
  }

  function finiteNumber(value, fallback = 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function itemIdentity(item) {
    const safeUrl = safeHttpUrl(item?.url);
    if (safeUrl) return safeUrl;
    return [
      item?.site_id || "",
      item?.source || "",
      item?.title || item?.title_zh || item?.title_en || "",
      item?.published_at || item?.first_seen_at || "",
    ].join("|");
  }

  function timestampOf(item) {
    const raw = item?.published_at || item?.first_seen_at;
    const timestamp = Date.parse(raw || "");
    return Number.isFinite(timestamp) ? timestamp : 0;
  }

  function itemScore(item, nowMs = Date.now()) {
    const aiRelevance = Math.max(
      0,
      Math.min(1, finiteNumber(item?.ai_score, 0))
    );
    const longevityRelevance = Math.max(0, Math.min(1, finiteNumber(item?.longevity_score, 0)));
    const signal = Math.max(0, Math.min(1, finiteNumber(item?.signal_score, Math.min(aiRelevance, longevityRelevance))));
    const publishedAt = timestampOf(item);
    const ageHours = publishedAt ? Math.max(0, (nowMs - publishedAt) / 3600000) : 48;
    const freshness = Math.max(0, 24 - Math.min(ageHours, 24));
    const evidenceBonus = item?.source_type === "paper" ? 14 : item?.source_type === "trial" ? 10 : 0;
    const transparencyBonus = item?.study_subject && item?.publication_stage ? 4 : 0;
    const bilingual = item?.title_zh && item?.title_en ? 3 : 0;
    return signal * 100 + Math.min(aiRelevance, longevityRelevance) * 25 + freshness + evidenceBonus + transparencyBonus + bilingual;
  }

  function compareItems(a, b, nowMs) {
    const scoreDelta = itemScore(b, nowMs) - itemScore(a, nowMs);
    if (scoreDelta) return scoreDelta;
    const timeDelta = timestampOf(b) - timestampOf(a);
    if (timeDelta) return timeDelta;
    return itemIdentity(a).localeCompare(itemIdentity(b));
  }

  function selectBriefingItems(items, limit = 3, nowMs = Date.now()) {
    if (!Array.isArray(items) || limit <= 0) return [];
    const unique = [];
    const seenIds = new Set();
    items.forEach((item) => {
      const id = itemIdentity(item);
      if (!id || seenIds.has(id) || !safeHttpUrl(item?.url)) return;
      seenIds.add(id);
      unique.push(item);
    });
    unique.sort((a, b) => compareItems(a, b, nowMs));

    const selected = [];
    const seenSites = new Set();
    for (const item of unique) {
      const siteKey = item.site_id || item.site_name || item.source || itemIdentity(item);
      if (seenSites.has(siteKey)) continue;
      selected.push(item);
      seenSites.add(siteKey);
      if (selected.length === limit) return selected;
    }
    for (const item of unique) {
      if (selected.includes(item)) continue;
      selected.push(item);
      if (selected.length === limit) break;
    }
    return selected;
  }

  function pickSurprise(items, previousIdentity = "", randomValue = Math.random()) {
    if (!Array.isArray(items)) return null;
    const candidates = items.filter((item) => safeHttpUrl(item?.url));
    if (!candidates.length) return null;
    const withoutPrevious = candidates.filter((item) => itemIdentity(item) !== previousIdentity);
    const pool = withoutPrevious.length ? withoutPrevious : candidates;
    const normalizedRandom = Math.max(0, Math.min(0.999999, finiteNumber(randomValue, 0)));
    return pool[Math.floor(normalizedRandom * pool.length)] || null;
  }

  function sanitizeTakeaway(value) {
    if (typeof value !== "string") return "";
    return value.replace(/\s+/g, " ").trim().slice(0, MAX_TAKEAWAY_LENGTH);
  }

  function normalizeSavedEntry(value) {
    if (!value || typeof value !== "object") return null;
    const url = safeHttpUrl(value.url);
    const title = typeof value.title === "string" ? value.title.trim().slice(0, 300) : "";
    if (!url || !title) return null;
    return {
      id: url,
      url,
      title,
      siteName: typeof value.siteName === "string" ? value.siteName.trim().slice(0, 120) : "",
      takeaway: sanitizeTakeaway(value.takeaway),
      savedAt: Number.isFinite(Number(value.savedAt)) ? Number(value.savedAt) : Date.now(),
    };
  }

  function parseSavedEntries(raw) {
    if (typeof raw !== "string" || !raw.trim()) return [];
    try {
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      const seen = new Set();
      return parsed
        .map(normalizeSavedEntry)
        .filter((entry) => {
          if (!entry || seen.has(entry.id)) return false;
          seen.add(entry.id);
          return true;
        });
    } catch {
      return [];
    }
  }

  function dailyProgress(entries, target = 3) {
    const learned = Array.isArray(entries)
      ? entries.filter((entry) => sanitizeTakeaway(entry?.takeaway)).length
      : 0;
    return {
      learned,
      target: Math.max(1, finiteNumber(target, 3)),
      complete: learned >= Math.max(1, finiteNumber(target, 3)),
    };
  }

  return {
    MAX_TAKEAWAY_LENGTH,
    dailyProgress,
    itemIdentity,
    itemScore,
    parseSavedEntries,
    pickSurprise,
    safeHttpUrl,
    sanitizeTakeaway,
    selectBriefingItems,
  };
});
