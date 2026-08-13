const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "..");
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");
const html = read("index.html");
const app = read("assets/app.js");
const styles = read("assets/styles.css");
const workflow = read(".github/workflows/update-news.yml");
const cname = read("CNAME").trim();
const robots = read("robots.txt");
const sitemap = read("sitemap.xml");
const llms = read("llms.txt");

test("every app element reference exists in the document", () => {
  const documentIds = new Set([...html.matchAll(/\sid="([^"]+)"/g)].map((match) => match[1]));
  const appIds = [...app.matchAll(/byId\("([^"]+)"\)/g)].map((match) => match[1]);
  const missing = appIds.filter((id) => !documentIds.has(id));
  assert.deepEqual(missing, []);
});

test("core loads before app and page metadata points to the branded custom domain", () => {
  assert.ok(html.indexOf("./assets/core.js") < html.indexOf("./assets/app.js"));
  assert.match(html, /<title>爱窝啦 AI生命延续学雷达/);
  assert.match(html, /<link rel="canonical" href="https:\/\/radar\.aibioo\.cn\/"/);
  assert.match(html, /<meta property="og:url" content="https:\/\/radar\.aibioo\.cn\/"/);
  assert.match(html, /<meta\s+name="description"/s);
});

test("visible ecosystem navigation links the Aivora sites", () => {
  assert.match(html, /aria-label="爱窝啦网站导航"/);
  assert.match(html, /href="https:\/\/www\.aivora\.cn\/"/);
  assert.match(html, /href="https:\/\/news\.aivora\.cn\/"/);
  assert.match(html, /href="https:\/\/news\.aibioo\.cn\/"/);
  assert.match(html, /href="https:\/\/radar\.aivora\.cn\/"/);
});

test("JSON-LD describes the publisher, website, and collection page", () => {
  const match = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/);
  assert.ok(match, "expected JSON-LD in index.html");
  const payload = JSON.parse(match[1]);
  const types = new Set(payload["@graph"].map((entry) => entry["@type"]));
  assert.deepEqual(types, new Set(["Organization", "WebSite", "CollectionPage"]));
  assert.equal(payload["@graph"].find((entry) => entry["@type"] === "WebSite").url, "https://radar.aibioo.cn/");
});

test("crawler and AI discovery files use the custom domain", () => {
  assert.equal(cname, "radar.aibioo.cn");
  assert.match(robots, /Sitemap: https:\/\/radar\.aibioo\.cn\/sitemap\.xml/);
  assert.match(sitemap, /<loc>https:\/\/radar\.aibioo\.cn\/<\/loc>/);
  assert.match(llms, /https:\/\/radar\.aibioo\.cn\/data\/latest-24h\.json/);
  assert.match(llms, /https:\/\/www\.aivora\.cn\//);
});

test("static links opened in new tabs have opener protection", () => {
  const externalAnchors = [...html.matchAll(/<a\b[^>]*target="_blank"[^>]*>/gs)].map((match) => match[0]);
  assert.ok(externalAnchors.length > 0);
  externalAnchors.forEach((anchor) => assert.match(anchor, /\brel="[^"]*noopener[^"]*"/));
});

test("rendering avoids untrusted innerHTML and URL assignment is centralized", () => {
  assert.doesNotMatch(app, /\.innerHTML\s*=/);
  assert.doesNotMatch(app, /\.href\s*=\s*item\./);
  assert.match(app, /core\.safeHttpUrl/);
});

test("Hallmark stamp, token import, and page-edge clipping are present", () => {
  assert.match(styles.split(/\r?\n/, 1)[0], /^\/\* Hallmark ·/);
  assert.match(styles, /@import url\("\.\.\/tokens\.css"\);/);
  assert.match(styles, /:root\s*\{[^}]*overflow-x:\s*clip;/s);
  assert.match(styles, /body\s*\{[^}]*overflow-x:\s*clip;/s);
});

test("page workflow publishes only the runtime artifact", () => {
  assert.match(workflow, /actions\/configure-pages@v5/);
  assert.match(workflow, /actions\/upload-pages-artifact@v4/);
  assert.match(workflow, /actions\/deploy-pages@v4/);
  assert.match(workflow, /cp data\/latest-24h\.json data\/latest-24h-all\.json data\/briefing-lite\.json data\/source-status\.json data\/topic-stats\.json _site\/data\//);
  assert.match(workflow, /cp CNAME robots\.txt sitemap\.xml llms\.txt _site\//);
  assert.doesNotMatch(workflow, /cp\s+-r\s+data/);
});
