const test = require("node:test");
const assert = require("node:assert/strict");
const core = require("../assets/core.js");

const now = Date.parse("2026-07-31T12:00:00Z");

function item(overrides = {}) {
  return {
    site_id: "europepmc",
    site_name: "Europe PMC",
    source: "Nature Aging",
    source_type: "paper",
    title: "Deep learning biological age clock",
    url: "https://example.com/update",
    published_at: "2026-07-31T11:00:00Z",
    ai_score: 0.9,
    longevity_score: 0.92,
    signal_score: 0.9,
    study_subject: "human",
    publication_stage: "peer_review_status_unknown",
    ...overrides,
  };
}

test("safeHttpUrl accepts only http and https", () => {
  assert.equal(core.safeHttpUrl("https://example.com/a"), "https://example.com/a");
  assert.equal(core.safeHttpUrl("http://example.com/a"), "http://example.com/a");
  assert.equal(core.safeHttpUrl("javascript:alert(1)"), "");
  assert.equal(core.safeHttpUrl("data:text/html,hi"), "");
  assert.equal(core.safeHttpUrl("not a url"), "");
});

test("briefing selection is deterministic, fresh, and source-diverse", () => {
  const items = [
    item({ url: "https://a.example/1", site_id: "europepmc", signal_score: 0.95 }),
    item({ url: "https://a.example/2", site_id: "europepmc", signal_score: 0.94 }),
    item({ url: "https://b.example/1", site_id: "github_projects", source_type: "project", signal_score: 0.9 }),
    item({ url: "https://c.example/1", site_id: "clinicaltrials", source_type: "trial", signal_score: 0.85 }),
  ];
  const first = core.selectBriefingItems(items, 3, now);
  const second = core.selectBriefingItems(items, 3, now);
  assert.deepEqual(first.map(core.itemIdentity), second.map(core.itemIdentity));
  assert.equal(new Set(first.map((entry) => entry.site_id)).size, 3);
});

test("briefing ignores unsafe and duplicate URLs", () => {
  const duplicate = item({ url: "https://example.com/update" });
  const unsafe = item({ url: "javascript:alert(1)", title: "Unsafe" });
  const selected = core.selectBriefingItems([duplicate, duplicate, unsafe], 3, now);
  assert.equal(selected.length, 1);
});

test("briefing prefers core relevance over related fallback", () => {
  const related = item({ url: "https://example.com/related", relevance_tier: "related", signal_score: 0.99 });
  const coreItem = item({ url: "https://example.com/core", relevance_tier: "core", signal_score: 0.8 });
  const selected = core.selectBriefingItems([related, coreItem], 1, now);
  assert.equal(selected[0].relevance_tier, "core");
});

test("surprise avoids the previous story when possible", () => {
  const first = item({ url: "https://example.com/first" });
  const second = item({ url: "https://example.com/second" });
  const picked = core.pickSurprise([first, second], core.itemIdentity(first), 0);
  assert.equal(core.itemIdentity(picked), core.itemIdentity(second));
});

test("saved-entry parsing recovers from corrupt storage and sanitizes notes", () => {
  assert.deepEqual(core.parseSavedEntries("{broken"), []);
  const parsed = core.parseSavedEntries(
    JSON.stringify([
      {
        url: "https://example.com/saved",
        title: " Saved story ",
        siteName: " Site ",
        takeaway: "  one   useful   thought  ",
        savedAt: now,
      },
      { url: "javascript:alert(1)", title: "Unsafe" },
    ])
  );
  assert.equal(parsed.length, 1);
  assert.equal(parsed[0].takeaway, "one useful thought");
});

test("progress counts only entries with a takeaway", () => {
  const progress = core.dailyProgress([
    { takeaway: "learned" },
    { takeaway: "" },
    { takeaway: "another" },
  ]);
  assert.deepEqual(progress, { learned: 2, target: 3, complete: false });
});
