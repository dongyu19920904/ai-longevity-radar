(() => {
  "use strict";

  const core = window.AILongevityRadarCore;
  if (!core) throw new Error("AI 生命延续学雷达核心模块未加载");

  const STORAGE_KEY = "ai-longevity-radar.takeaways.v1";
  const INITIAL_LIMIT = 80;
  const LOAD_STEP = 80;
  const PALETTE_LIMIT = 12;

  const state = {
    itemsAi: [],
    itemsAll: [],
    itemsAllRaw: [],
    statsAi: [],
    totalAi: 0,
    totalRaw: 0,
    totalAllMode: 0,
    allDedup: true,
    allDataLoaded: false,
    allDataUrl: "data/latest-24h-all.json",
    allDataPromise: null,
    siteFilter: "",
    query: "",
    mode: "all",
    sourceStatus: null,
    generatedAt: null,
    briefingItems: [],
    savedEntries: [],
    currentStory: null,
    previousSurprise: "",
    visibleLimit: INITIAL_LIMIT,
    storageAvailable: true,
    paletteItems: [],
    paletteIndex: 0,
  };

  const byId = (id) => document.getElementById(id);
  const els = {
    advancedSummary: byId("advancedSummary"),
    advancedToggle: byId("advancedToggle"),
    allDedupeLabel: byId("allDedupeLabel"),
    allDedupeToggle: byId("allDedupeToggle"),
    allDedupeWrap: byId("allDedupeWrap"),
    briefingList: byId("briefingList"),
    briefingStatus: byId("briefingStatus"),
    coverageStrip: byId("coverageStrip"),
    heroRadarButton: byId("heroRadarButton"),
    heroSignalCount: byId("heroSignalCount"),
    issueDate: byId("issueDate"),
    itemTpl: byId("itemTpl"),
    listTitle: byId("listTitle"),
    loadMoreButton: byId("loadMoreButton"),
    modeAiBtn: byId("modeAiBtn"),
    modeAllBtn: byId("modeAllBtn"),
    modeHint: byId("modeHint"),
    navStatus: byId("navStatus"),
    newsList: byId("newsList"),
    paletteResults: byId("paletteResults"),
    paletteSearchInput: byId("paletteSearchInput"),
    radarButton: byId("radarButton"),
    radarCreature: byId("radarCreature"),
    radarStatus: byId("radarStatus"),
    removeTakeawayButton: byId("removeTakeawayButton"),
    resultCount: byId("resultCount"),
    saveTakeawayButton: byId("saveTakeawayButton"),
    savedList: byId("savedList"),
    searchDialog: byId("searchDialog"),
    searchDialogClose: byId("searchDialogClose"),
    searchInput: byId("searchInput"),
    searchTrigger: byId("searchTrigger"),
    sitePills: byId("sitePills"),
    siteSelect: byId("siteSelect"),
    sourceDetails: byId("sourceDetails"),
    sourceHealth: byId("sourceHealth"),
    stats: byId("stats"),
    storageNotice: byId("storageNotice"),
    storyDialog: byId("storyDialog"),
    storyDialogClose: byId("storyDialogClose"),
    storyDialogHint: byId("storyDialogHint"),
    storyDialogLink: byId("storyDialogLink"),
    storyDialogMeta: byId("storyDialogMeta"),
    storyDialogTitle: byId("storyDialogTitle"),
    takeawayHelper: byId("takeawayHelper"),
    takeawayInput: byId("takeawayInput"),
    takeawayProgress: byId("takeawayProgress"),
    updatedAt: byId("updatedAt"),
  };

  const SOURCE_KINDS = {
    europepmc: { label: "论文", tone: "official" },
    clinicaltrials: { label: "临床试验", tone: "newsletter" },
    official_rss: { label: "机构 / 行业", tone: "blogs" },
    github_projects: { label: "开源项目", tone: "builders" },
    ai_radar_bridge: { label: "AI 行业", tone: "aihub" },
  };

  const TOPIC_LABELS = {
    aging_clock: "年龄时钟", rejuvenation: "年轻化", drug_discovery: "药物发现",
    digital_biomarker: "数字生物标志物", neurodegeneration: "神经退行",
    multi_omics: "多组学", clinical_trial: "临床试验", research_tool: "研究工具",
    aging_mechanism: "衰老机制", industry: "行业信号",
  };

  const SUBJECT_LABELS = {
    human: "人体研究", animal: "动物研究", cell_or_organoid: "细胞 / 类器官",
    computational_or_dataset: "计算 / 数据集", unknown: "对象未知",
  };

  const STAGE_LABELS = {
    peer_reviewed: "同行评议", peer_review_status_unknown: "评议状态未知", preprint: "预印本",
    registered_trial: "注册试验", software_project: "软件项目", secondary_report: "二手报道", unknown: "阶段未知",
  };

  const fmtNumber = (value) => new Intl.NumberFormat("zh-CN").format(Number(value) || 0);

  function fmtTime(value) {
    const date = new Date(value || "");
    if (Number.isNaN(date.getTime())) return "时间未知";
    return new Intl.DateTimeFormat("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(date);
  }

  function fmtDate(value) {
    const date = new Date(value?.length === 10 ? `${value}T00:00:00` : value || "");
    if (Number.isNaN(date.getTime())) return value || "未知日期";
    return new Intl.DateTimeFormat("zh-CN", {
      month: "2-digit",
      day: "2-digit",
    }).format(date);
  }

  function itemTitle(item) {
    return (item?.title_zh || item?.title || item?.title_en || "未命名信号").trim();
  }

  function itemSubTitle(item) {
    const primary = itemTitle(item);
    const secondary = (item?.title_en || "").trim();
    return secondary && secondary !== primary ? secondary : "";
  }

  function itemHaystack(item) {
    return [
      itemTitle(item),
      item?.title_en,
      item?.site_name,
      item?.source,
      item?.source_type,
      item?.topics,
      item?.study_subject,
      item?.publication_stage,
      item?.risk_flags,
      item?.relevance_reason,
    ].filter(Boolean).join(" ").toLocaleLowerCase("zh-CN");
  }

  function sourceKind(siteId) {
    if (String(siteId || "").startsWith("ai_radar_")) return SOURCE_KINDS.ai_radar_bridge;
    return SOURCE_KINDS[siteId] || { label: "来源", tone: "default" };
  }

  function randomValue() {
    if (!window.crypto?.getRandomValues) return Math.random();
    const value = new Uint32Array(1);
    window.crypto.getRandomValues(value);
    return value[0] / 4294967296;
  }

  function emptyNode(message, className = "empty") {
    const node = document.createElement("div");
    node.className = className;
    node.textContent = message;
    return node;
  }

  function safeLink(anchor, value) {
    const url = core.safeHttpUrl(value);
    if (url) {
      anchor.href = url;
      anchor.removeAttribute("aria-disabled");
      return true;
    }
    anchor.removeAttribute("href");
    anchor.setAttribute("aria-disabled", "true");
    return false;
  }

  function setPressed(button, active) {
    if (!button) return;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  }

  function setIssueDate() {
    const now = new Date();
    const readable = new Intl.DateTimeFormat("zh-CN", {
      year: "numeric",
      month: "long",
      day: "numeric",
      weekday: "short",
    }).format(now);
    els.issueDate.textContent = `${readable} · AI LONGEVITY SIGNALS`;
  }

  function readSavedEntries() {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      state.savedEntries = core.parseSavedEntries(raw);
      state.storageAvailable = true;
    } catch {
      state.savedEntries = [];
      state.storageAvailable = false;
    }
  }

  function persistSavedEntries() {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state.savedEntries));
      state.storageAvailable = true;
    } catch {
      state.storageAvailable = false;
    }
    renderSaved();
  }

  function savedEntryFor(item) {
    const id = core.itemIdentity(item);
    return state.savedEntries.find((entry) => entry.id === id) || null;
  }

  function upsertSaved(item, takeaway = "") {
    const url = core.safeHttpUrl(item?.url);
    if (!url) return;
    const entry = {
      id: url,
      url,
      title: itemTitle(item),
      siteName: (item?.site_name || item?.source || "").slice(0, 120),
      takeaway: core.sanitizeTakeaway(takeaway),
      savedAt: Date.now(),
    };
    state.savedEntries = [entry, ...state.savedEntries.filter((saved) => saved.id !== entry.id)].slice(0, 50);
    persistSavedEntries();
  }

  function removeSaved(item) {
    const id = core.itemIdentity(item);
    state.savedEntries = state.savedEntries.filter((entry) => entry.id !== id);
    persistSavedEntries();
  }

  function renderSaved() {
    const progress = core.dailyProgress(state.savedEntries);
    els.takeawayProgress.textContent = `${progress.learned} / ${progress.target}`;
    els.takeawayProgress.classList.toggle("complete", progress.complete);
    els.storageNotice.hidden = state.storageAvailable;
    els.storageNotice.textContent = state.storageAvailable
      ? ""
      : "浏览器已阻止本地存储；本次内容关闭页面后不会保留。";

    els.savedList.replaceChildren();
    if (!state.savedEntries.length) {
      els.savedList.appendChild(emptyNode("还没有收藏。看到值得记住的内容，点“记一句”。", "saved-empty"));
      renderListSaveStates();
      return;
    }

    const fragment = document.createDocumentFragment();
    state.savedEntries.slice(0, 8).forEach((entry) => {
      const article = document.createElement("div");
      article.className = "saved-item";

      const copy = document.createElement("div");
      const meta = document.createElement("p");
      meta.className = "saved-item__meta";
      meta.textContent = entry.siteName || "已收藏";
      const link = document.createElement("a");
      link.className = "saved-item__title";
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = entry.title;
      safeLink(link, entry.url);
      copy.append(meta, link);

      if (entry.takeaway) {
        const takeaway = document.createElement("p");
        takeaway.className = "saved-item__takeaway";
        takeaway.textContent = entry.takeaway;
        copy.appendChild(takeaway);
      }

      const remove = document.createElement("button");
      remove.className = "icon-button icon-button--small";
      remove.type = "button";
      remove.setAttribute("aria-label", `移除收藏：${entry.title}`);
      remove.textContent = "×";
      remove.addEventListener("click", () => {
        state.savedEntries = state.savedEntries.filter((saved) => saved.id !== entry.id);
        persistSavedEntries();
      });

      article.append(copy, remove);
      fragment.appendChild(article);
    });
    els.savedList.appendChild(fragment);
    renderListSaveStates();
  }

  function renderListSaveStates() {
    document.querySelectorAll("[data-story-id]").forEach((button) => {
      const saved = state.savedEntries.some((entry) => entry.id === button.dataset.storyId);
      button.classList.toggle("is-saved", saved);
      button.setAttribute("aria-pressed", String(saved));
      if (button.classList.contains("save-button")) {
        button.textContent = saved ? "已收藏" : "收藏";
      }
    });
    if (state.currentStory) updateStoryDialogState(state.currentStory);
  }

  function updateStoryDialogState(item) {
    const saved = savedEntryFor(item);
    els.removeTakeawayButton.hidden = !saved;
    els.saveTakeawayButton.textContent = saved ? "更新我的收获" : "收藏并保存";
  }

  function openStoryDialog(item, prompt = "读原文，再留下自己的判断。") {
    if (!item || !core.safeHttpUrl(item.url)) return;
    state.currentStory = item;
    const saved = savedEntryFor(item);
    els.storyDialogTitle.textContent = itemTitle(item);
    els.storyDialogMeta.textContent = [item.site_name, item.source, fmtTime(item.published_at || item.first_seen_at)]
      .filter(Boolean)
      .join(" · ");
    els.storyDialogHint.textContent = prompt;
    els.takeawayInput.value = saved?.takeaway || "";
    safeLink(els.storyDialogLink, item.url);
    updateStoryDialogState(item);
    if (!els.storyDialog.open) els.storyDialog.showModal();
  }

  function closeOnBackdrop(dialog, event) {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    const outside = (
      event.clientX < rect.left ||
      event.clientX > rect.right ||
      event.clientY < rect.top ||
      event.clientY > rect.bottom
    );
    if (outside) dialog.close();
  }

  function setStats(payload) {
    const cards = [
      ["全部信息源", fmtNumber(state.totalAllMode)],
      ["双重强相关", fmtNumber(state.totalAi)],
      ["站点", fmtNumber(currentSiteStats().length)],
      ["历史归档", fmtNumber(payload.archive_total)],
    ];
    els.stats.replaceChildren();
    cards.forEach(([label, value]) => {
      const card = document.createElement("div");
      card.className = "stat";
      const key = document.createElement("span");
      key.className = "k";
      key.textContent = label;
      const metric = document.createElement("strong");
      metric.className = "v";
      metric.textContent = value;
      card.append(key, metric);
      els.stats.appendChild(card);
    });
  }

  function siteRows() {
    return Array.isArray(state.sourceStatus?.sites) ? state.sourceStatus.sites : [];
  }

  function renderCoverageCard(label, value, meta, tone = "") {
    const card = document.createElement("article");
    card.className = `coverage-card ${tone}`.trim();
    const labelNode = document.createElement("span");
    labelNode.className = "coverage-label";
    labelNode.textContent = label;
    const valueNode = document.createElement("strong");
    valueNode.textContent = value;
    const metaNode = document.createElement("span");
    metaNode.className = "coverage-meta";
    metaNode.textContent = meta;
    card.append(labelNode, valueNode, metaNode);
    return card;
  }

  function renderCoverageStrip(errorMessage = "") {
    els.coverageStrip.replaceChildren();
    const rows = siteRows();
    const failed = Array.isArray(state.sourceStatus?.failed_sites) ? state.sourceStatus.failed_sites : [];
    const allCount = Number(state.sourceStatus?.items_before_topic_filter || state.totalAllMode || 0);
    const rawCount = Number(state.sourceStatus?.fetched_raw_items || state.totalRaw || allCount);
    const okSites = Number(state.sourceStatus?.successful_sites || rows.filter((row) => row.ok).length);
    const papers = state.itemsAi.filter((item) => item.source_type === "paper").length;
    const projectsAndTrials = state.itemsAi.filter((item) => ["project", "trial"].includes(item.source_type)).length;
    const bridgedSourceCount = new Set(state.itemsAll
      .map((row) => String(row.site_id || ""))
      .filter((siteId) => siteId.startsWith("ai_radar_"))).size;

    const cards = [
      ["源健康", rows.length ? `${fmtNumber(okSites)}/${fmtNumber(rows.length)}` : "加载中", failed.length ? `${failed.length} 个失败源` : (errorMessage || "公开源状态"), failed.length ? "warn" : "ok"],
      ["抓取候选", `${fmtNumber(rawCount)} 条`, "多源公开覆盖池", "signal"],
      ["双重相关", `${fmtNumber(state.totalAi)} 条`, "AI 与生命延续同时达标", "signal"],
      ["旧雷达来源", `${fmtNumber(bridgedSourceCount)} 类`, "保留每个原始信息源身份", "official"],
      ["论文 / 试验 / 项目", `${fmtNumber(papers + projectsAndTrials)} 条`, "生命延续专属采集器", "private"],
      ["全部信息源", `${fmtNumber(allCount)} 条`, "默认去重展示", "aggregate"],
    ];
    cards.forEach((card) => els.coverageStrip.appendChild(renderCoverageCard(...card)));
  }

  function computeSiteStats(items) {
    const map = new Map();
    items.forEach((item) => {
      const id = item.site_id || "unknown";
      if (!map.has(id)) map.set(id, { site_id: id, site_name: item.site_name || id, count: 0, raw_count: 0 });
      const row = map.get(id);
      row.count += 1;
      row.raw_count += 1;
    });
    return [...map.values()].sort((a, b) => b.count - a.count || a.site_name.localeCompare(b.site_name, "zh-CN"));
  }

  function currentItems() {
    if (state.mode === "ai") return state.itemsAi;
    return state.allDedup ? state.itemsAll : state.itemsAllRaw;
  }

  function currentSiteStats() {
    return state.mode === "ai" ? state.statsAi : computeSiteStats(currentItems());
  }

  function getFilteredItems(queryOverride = null) {
    const query = (queryOverride === null ? state.query : queryOverride).trim().toLocaleLowerCase("zh-CN");
    return currentItems().filter((item) => {
      if (state.siteFilter && item.site_id !== state.siteFilter) return false;
      return !query || itemHaystack(item).includes(query);
    });
  }

  function renderAdvancedSummary() {
    const allCount = state.allDedup ? state.totalAllMode : state.totalRaw;
    const okSites = Number(state.sourceStatus?.successful_sites || siteRows().filter((row) => row.ok).length);
    const totalSites = siteRows().length;
    els.advancedSummary.textContent = totalSites
      ? `${okSites}/${totalSites} 源可用 · 全量 ${fmtNumber(allCount)} 条`
      : `全量 ${fmtNumber(allCount)} 条`;
  }

  function renderModeSwitch() {
    setPressed(els.modeAiBtn, state.mode === "ai");
    setPressed(els.modeAllBtn, state.mode === "all");
    els.allDedupeWrap.classList.toggle("show", state.mode === "all");
    els.allDedupeToggle.checked = state.allDedup;
    els.allDedupeLabel.textContent = state.allDedup ? "去重开" : "去重关";
    const count = state.mode === "ai" ? state.totalAi : (state.allDedup ? state.totalAllMode : state.totalRaw);
    els.listTitle.textContent = state.mode === "ai" ? "AI 生命延续强相关" : "全部信息源信号流";
    els.modeHint.textContent = state.mode === "ai"
      ? `AI + 生命延续双重相关 · ${fmtNumber(count)} 条`
      : `旧版 AI雷达全源 + 生命延续专属源 · ${state.allDedup ? "去重开" : "去重关"} · ${fmtNumber(count)} 条`;
    els.heroSignalCount.textContent = fmtNumber(count);
    els.navStatus.textContent = state.mode === "ai"
      ? `${fmtNumber(count)} 条强相关信号在线`
      : `${fmtNumber(count)} 条信息源信号在线`;
    renderAdvancedSummary();
  }

  function chooseSite(value) {
    state.siteFilter = value;
    state.visibleLimit = INITIAL_LIMIT;
    renderSiteFilters();
    renderList();
  }

  function renderSiteFilters() {
    const stats = currentSiteStats();
    const options = document.createDocumentFragment();
    const all = document.createElement("option");
    all.value = "";
    all.textContent = "全部站点";
    options.appendChild(all);
    stats.forEach((row) => {
      const option = document.createElement("option");
      option.value = row.site_id;
      option.textContent = `${row.site_name} (${fmtNumber(row.count)}/${fmtNumber(row.raw_count ?? row.count)})`;
      options.appendChild(option);
    });
    els.siteSelect.replaceChildren(options);
    if (!stats.some((row) => row.site_id === state.siteFilter)) state.siteFilter = "";
    els.siteSelect.value = state.siteFilter;

    const pills = document.createDocumentFragment();
    [{ site_id: "", site_name: "全部", count: currentItems().length }, ...stats].forEach((row) => {
      const button = document.createElement("button");
      button.className = "pill";
      button.type = "button";
      button.classList.toggle("active", state.siteFilter === row.site_id);
      button.setAttribute("aria-pressed", String(state.siteFilter === row.site_id));
      button.textContent = `${row.site_name} ${fmtNumber(row.count)}`;
      button.addEventListener("click", () => chooseSite(row.site_id));
      pills.appendChild(button);
    });
    els.sitePills.replaceChildren(pills);
  }

  function itemMeta(item) {
    return [item.site_name, item.source, fmtTime(item.published_at || item.first_seen_at)].filter(Boolean).join(" · ");
  }

  function evidenceChip(label, tone = "") {
    const chip = document.createElement("span");
    chip.className = `evidence-chip ${tone}`.trim();
    chip.textContent = label;
    return chip;
  }

  function bindStoryButton(button, item, prompt) {
    button.dataset.storyId = core.itemIdentity(item);
    button.addEventListener("click", () => openStoryDialog(item, prompt));
  }

  function renderItemNode(item) {
    const node = els.itemTpl.content.firstElementChild.cloneNode(true);
    const kind = sourceKind(item.site_id);
    node.querySelector(".site").textContent = item.site_name || "未知站点";
    const category = node.querySelector(".category");
    category.textContent = kind.label;
    category.classList.add(`kind-${kind.tone}`);
    node.querySelector(".source").textContent = item.source || "未分区";
    const time = node.querySelector(".time");
    const timeValue = item.published_at || item.first_seen_at;
    time.textContent = fmtTime(timeValue);
    if (timeValue) time.dateTime = timeValue;

    const title = node.querySelector(".title");
    title.textContent = "";
    const primary = document.createElement("span");
    primary.textContent = itemTitle(item);
    title.appendChild(primary);
    const subTitle = itemSubTitle(item);
    if (subTitle) {
      const secondary = document.createElement("span");
      secondary.className = "title-sub";
      secondary.textContent = subTitle;
      title.appendChild(secondary);
    }
    safeLink(title, item.url);

    const evidence = node.querySelector(".evidence-row");
    const topic = TOPIC_LABELS[item.primary_topic] || item.primary_topic;
    if (topic) evidence.appendChild(evidenceChip(topic, "topic"));
    evidence.appendChild(evidenceChip(SUBJECT_LABELS[item.study_subject] || item.study_subject || "对象未知"));
    evidence.appendChild(evidenceChip(STAGE_LABELS[item.publication_stage] || item.publication_stage || "阶段未知"));
    if (Number.isFinite(Number(item.signal_score))) evidence.appendChild(evidenceChip(`信号 ${Math.round(Number(item.signal_score) * 100)}`, "score"));
    (Array.isArray(item.risk_flags) ? item.risk_flags : []).slice(0, 2)
      .forEach((flag) => evidence.appendChild(evidenceChip(flag.replaceAll("_", " "), "risk")));

    const save = node.querySelector(".save-button");
    const note = node.querySelector(".note-button");
    bindStoryButton(save, item, "可以直接收藏，也可以先读原文再回来写下判断。");
    bindStoryButton(note, item, "写下一句话，把刷到的信息变成自己的收获。");
    return node;
  }

  function groupBy(items, keyFn) {
    const map = new Map();
    items.forEach((item) => {
      const key = keyFn(item);
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(item);
    });
    return [...map.entries()].sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0], "zh-CN"));
  }

  function renderSourceGroup(source, items) {
    const section = document.createElement("section");
    section.className = "source-group";
    const header = document.createElement("header");
    header.className = "source-group-head";
    const title = document.createElement("h3");
    title.textContent = source;
    const count = document.createElement("span");
    count.textContent = `${fmtNumber(items.length)} 条`;
    header.append(title, count);
    const list = document.createElement("div");
    list.className = "source-group-list";
    items.forEach((item) => list.appendChild(renderItemNode(item)));
    section.append(header, list);
    return section;
  }

  function renderList() {
    const filtered = getFilteredItems();
    const visible = filtered.slice(0, state.visibleLimit);
    els.resultCount.textContent = state.query
      ? `找到 ${fmtNumber(filtered.length)} 条`
      : `${fmtNumber(filtered.length)} 条`;
    els.newsList.replaceChildren();

    if (!filtered.length) {
      els.newsList.appendChild(emptyNode("没有匹配的信号。换个关键词，或清空站点筛选试试。"));
      els.loadMoreButton.hidden = true;
      return;
    }

    const fragment = document.createDocumentFragment();
    if (state.siteFilter) {
      groupBy(visible, (item) => item.source || "未分区")
        .forEach(([source, items]) => fragment.appendChild(renderSourceGroup(source, items)));
    } else {
      groupBy(visible, (item) => item.site_id || "unknown").forEach(([, siteItems]) => {
        const section = document.createElement("section");
        section.className = "site-group";
        const header = document.createElement("header");
        header.className = "site-group-head";
        const title = document.createElement("h3");
        title.textContent = siteItems[0]?.site_name || "未知站点";
        const count = document.createElement("span");
        count.textContent = `${fmtNumber(siteItems.length)} 条已显示`;
        header.append(title, count);
        const sources = document.createElement("div");
        sources.className = "site-group-list";
        groupBy(siteItems, (item) => item.source || "未分区")
          .forEach(([source, items]) => sources.appendChild(renderSourceGroup(source, items)));
        section.append(header, sources);
        fragment.appendChild(section);
      });
    }
    els.newsList.appendChild(fragment);
    els.loadMoreButton.hidden = visible.length >= filtered.length;
    els.loadMoreButton.textContent = `再看一些（还有 ${fmtNumber(filtered.length - visible.length)} 条）`;
    renderListSaveStates();
  }

  function renderBriefing() {
    const now = Date.parse(state.generatedAt || "") || Date.now();
    state.briefingItems = core.selectBriefingItems(state.itemsAi, 3, now);
    els.briefingList.replaceChildren();
    if (!state.briefingItems.length) {
      els.briefingList.appendChild(emptyNode("今天还没有可用的简报信号。", "briefing-empty"));
      els.briefingStatus.textContent = "暂无条目";
      return;
    }

    const fragment = document.createDocumentFragment();
    state.briefingItems.forEach((item, index) => {
      const article = document.createElement("article");
      article.className = "briefing-card";
      const number = document.createElement("span");
      number.className = "briefing-card__number";
      number.textContent = String(index + 1).padStart(2, "0");
      const copy = document.createElement("div");
      const meta = document.createElement("p");
      meta.className = "briefing-card__meta";
      meta.textContent = itemMeta(item);
      const title = document.createElement("a");
      title.className = "briefing-card__title";
      title.target = "_blank";
      title.rel = "noopener noreferrer";
      title.textContent = itemTitle(item);
      safeLink(title, item.url);
      const action = document.createElement("button");
      action.className = "note-button";
      action.type = "button";
      action.textContent = "读后记一句";
      bindStoryButton(action, item, `三分钟简报第 ${index + 1} 条：先读，再留下自己的判断。`);
      copy.append(meta, title, action);
      article.append(number, copy);
      fragment.appendChild(article);
    });
    els.briefingList.appendChild(fragment);
    els.briefingStatus.textContent = "按双重相关、证据来源和多样性选取";
    renderListSaveStates();
  }

  function surprise() {
    const candidates = getFilteredItems();
    const item = core.pickSurprise(candidates, state.previousSurprise, randomValue());
    if (!item) {
      els.radarStatus.textContent = "当前筛选没有可扫描的链接。";
      return;
    }
    state.previousSurprise = core.itemIdentity(item);
    els.radarStatus.textContent = `捕捉到：${itemTitle(item)}`;
    openStoryDialog(item, "这是雷达从当前结果中随机挑出的信号。决定权仍在你手里。");
  }

  function renderPalette(query = "") {
    state.paletteItems = getFilteredItems(query).filter((item) => core.safeHttpUrl(item.url)).slice(0, PALETTE_LIMIT);
    state.paletteIndex = Math.min(state.paletteIndex, Math.max(0, state.paletteItems.length - 1));
    els.paletteResults.replaceChildren();
    if (!state.paletteItems.length) {
      els.paletteResults.appendChild(emptyNode(query ? "没有匹配结果。" : "今天还没有可搜索的信号。", "palette-empty"));
      return;
    }
    const fragment = document.createDocumentFragment();
    state.paletteItems.forEach((item, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "palette-result";
      button.classList.toggle("active", index === state.paletteIndex);
      button.setAttribute("role", "option");
      button.setAttribute("aria-selected", String(index === state.paletteIndex));
      const title = document.createElement("strong");
      title.textContent = itemTitle(item);
      const meta = document.createElement("span");
      meta.textContent = itemMeta(item);
      button.append(title, meta);
      button.addEventListener("mouseenter", () => {
        state.paletteIndex = index;
        renderPalette(els.paletteSearchInput.value);
      });
      button.addEventListener("click", () => {
        els.searchDialog.close();
        openStoryDialog(item, "从搜索结果中找到的信号。");
      });
      fragment.appendChild(button);
    });
    els.paletteResults.appendChild(fragment);
  }

  function openPalette() {
    if (!els.searchDialog.open) els.searchDialog.showModal();
    els.paletteSearchInput.value = state.query;
    state.paletteIndex = 0;
    renderPalette(state.query);
    window.requestAnimationFrame(() => els.paletteSearchInput.focus());
  }

  function renderMetric(label, value, tone = "") {
    const metric = document.createElement("div");
    metric.className = `health-metric ${tone}`.trim();
    const key = document.createElement("span");
    key.className = "health-label";
    key.textContent = label;
    const result = document.createElement("strong");
    result.textContent = value;
    metric.append(key, result);
    return metric;
  }

  function issueList(title, items) {
    const wrap = document.createElement("div");
    wrap.className = "health-issue";
    const heading = document.createElement("h4");
    heading.textContent = title;
    const list = document.createElement("ul");
    items.slice(0, 6).forEach((item) => {
      const li = document.createElement("li");
      li.textContent = typeof item === "string" ? item : (item.site_name || item.feed_url || item.error || "未知问题");
      list.appendChild(li);
    });
    wrap.append(heading, list);
    return wrap;
  }

  function renderSourceHealth(errorMessage = "") {
    els.sourceHealth.replaceChildren();
    const status = state.sourceStatus;
    if (!status) {
      els.sourceHealth.appendChild(emptyNode(errorMessage || "源状态未生成", "health-empty"));
      renderAdvancedSummary();
      return;
    }
    const sites = Array.isArray(status.sites) ? status.sites : [];
    const failedSites = Array.isArray(status.failed_sites) ? status.failed_sites : [];
    const zeroSites = Array.isArray(status.zero_item_sites) ? status.zero_item_sites : [];
    const grid = document.createElement("div");
    grid.className = "health-grid";
    grid.append(
      renderMetric("内置源", `${fmtNumber(status.successful_sites || 0)}/${fmtNumber(sites.length)}`, failedSites.length ? "warn" : "ok"),
      renderMetric("抓取候选", fmtNumber(status.fetched_raw_items || 0)),
      renderMetric("失败", fmtNumber(failedSites.length), failedSites.length ? "bad" : "ok"),
      renderMetric("生成时间", fmtTime(status.generated_at))
    );
    els.sourceHealth.appendChild(grid);
    if (failedSites.length || zeroSites.length) {
      const issues = document.createElement("div");
      issues.className = "health-issues";
      if (failedSites.length) issues.appendChild(issueList("失败站点", failedSites));
      if (zeroSites.length) issues.appendChild(issueList("零结果站点", zeroSites));
      els.sourceHealth.appendChild(issues);
    } else {
      els.sourceHealth.appendChild(emptyNode("本轮公开源状态正常。", "health-ok"));
    }
    renderAdvancedSummary();
  }

  async function fetchJson(url, label) {
    const response = await fetch(`${url}?t=${Date.now()}`);
    if (!response.ok) throw new Error(`${label}加载失败（HTTP ${response.status}）`);
    return response.json();
  }

  function loadNewsData() {
    return fetchJson("./data/latest-24h.json", "新闻数据");
  }

  async function loadAllModeData() {
    if (state.allDataLoaded) return;
    if (!state.allDataPromise) {
      state.allDataPromise = fetchJson(`./${state.allDataUrl}`, "全量数据")
        .then((payload) => {
          state.itemsAllRaw = payload.items_all_raw || payload.items_all || state.itemsAi;
          state.itemsAll = payload.items_all || state.itemsAi;
          state.totalRaw = payload.total_items_raw || state.itemsAllRaw.length;
          state.totalAllMode = payload.total_items_all_mode || state.itemsAll.length;
          state.allDataLoaded = true;
        })
        .catch((error) => {
          state.allDataPromise = null;
          throw error;
        });
    }
    await state.allDataPromise;
  }

  function loadSourceStatusData() {
    return fetchJson("./data/source-status.json", "源状态");
  }

  function showNewsError(error) {
    els.updatedAt.textContent = "新闻数据加载失败";
    els.navStatus.textContent = "信号离线";
    els.heroSignalCount.textContent = "0";
    els.newsList.replaceChildren(emptyNode(error.message));
    els.briefingList.replaceChildren(emptyNode("数据暂不可用，请稍后刷新。", "briefing-empty"));
    renderCoverageStrip(error.message);
  }

  async function init() {
    setIssueDate();
    readSavedEntries();
    renderSaved();
    renderModeSwitch();

    const [newsResult, statusResult] = await Promise.allSettled([
      loadNewsData(),
      loadSourceStatusData(),
    ]);

    if (newsResult.status === "fulfilled") {
      const payload = newsResult.value;
      state.itemsAi = payload.items_ai || payload.items || [];
      state.itemsAllRaw = payload.items_all_raw || payload.items_all || [];
      state.itemsAll = payload.items_all || [];
      state.statsAi = Array.isArray(payload.site_stats) ? payload.site_stats : computeSiteStats(state.itemsAi);
      state.totalAi = payload.total_items || state.itemsAi.length;
      state.totalRaw = payload.total_items_raw || state.itemsAllRaw.length;
      state.totalAllMode = payload.total_items_all_mode || state.itemsAll.length;
      state.allDataUrl = payload.all_mode_data_url || state.allDataUrl;
      state.allDataLoaded = Boolean(payload.items_all || payload.items_all_raw);
      state.generatedAt = payload.generated_at;

      if (state.mode === "all" && !state.allDataLoaded) {
        try {
          await loadAllModeData();
        } catch {
          state.mode = "ai";
        }
      }

      setStats(payload);
      renderModeSwitch();
      renderSiteFilters();
      renderList();
      renderBriefing();
      renderCoverageStrip();
      els.updatedAt.textContent = fmtTime(state.generatedAt);
      const currentTotal = state.mode === "all" ? state.totalAllMode : state.totalAi;
      els.heroSignalCount.textContent = fmtNumber(currentTotal);
      els.navStatus.textContent = `${fmtNumber(currentTotal)} 条信号在线`;
      els.briefingStatus.textContent = state.briefingItems.length ? els.briefingStatus.textContent : "暂无条目";
    } else {
      showNewsError(newsResult.reason);
    }

    if (statusResult.status === "fulfilled") {
      state.sourceStatus = statusResult.value;
      renderSourceHealth();
      renderCoverageStrip();
    } else {
      renderSourceHealth(statusResult.reason.message);
      renderCoverageStrip(statusResult.reason.message);
    }

  }

  function debounce(callback, delay) {
    let timer = null;
    return (...args) => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => callback(...args), delay);
    };
  }

  els.searchInput.addEventListener("input", debounce((event) => {
    state.query = event.target.value;
    state.visibleLimit = INITIAL_LIMIT;
    renderList();
  }, 220));

  els.siteSelect.addEventListener("change", (event) => chooseSite(event.target.value));

  els.modeAiBtn.addEventListener("click", () => {
    state.mode = "ai";
    state.visibleLimit = INITIAL_LIMIT;
    renderModeSwitch();
    renderSiteFilters();
    renderList();
  });

  els.modeAllBtn.addEventListener("click", async () => {
    state.mode = "all";
    state.visibleLimit = INITIAL_LIMIT;
    renderModeSwitch();
    els.newsList.replaceChildren(emptyNode("正在加载全量更新…"));
    try {
      await loadAllModeData();
      renderModeSwitch();
      renderSiteFilters();
      renderList();
    } catch (error) {
      els.newsList.replaceChildren(emptyNode(error.message));
    }
  });

  els.allDedupeToggle.addEventListener("change", (event) => {
    state.allDedup = Boolean(event.target.checked);
    state.visibleLimit = INITIAL_LIMIT;
    renderModeSwitch();
    renderSiteFilters();
    renderList();
  });

  els.loadMoreButton.addEventListener("click", () => {
    state.visibleLimit += LOAD_STEP;
    renderList();
  });

  els.advancedToggle.addEventListener("click", () => {
    els.sourceDetails.open = true;
    els.sourceDetails.scrollIntoView({ behavior: "smooth", block: "start" });
    window.setTimeout(() => els.sourceDetails.querySelector("summary")?.focus(), 350);
  });

  [els.radarButton, els.heroRadarButton, els.radarCreature].forEach((button) => {
    button.addEventListener("click", surprise);
  });

  els.saveTakeawayButton.addEventListener("click", () => {
    if (!state.currentStory) return;
    upsertSaved(state.currentStory, els.takeawayInput.value);
    els.takeawayHelper.textContent = state.storageAvailable
      ? "已保存在这台设备。"
      : "浏览器阻止了本地保存。";
    updateStoryDialogState(state.currentStory);
  });

  els.removeTakeawayButton.addEventListener("click", () => {
    if (!state.currentStory) return;
    removeSaved(state.currentStory);
    els.takeawayInput.value = "";
    els.takeawayHelper.textContent = "已移除。最多 180 字，只保存在本机。";
  });

  els.takeawayInput.addEventListener("input", () => {
    const length = [...els.takeawayInput.value].length;
    els.takeawayHelper.textContent = `${length} / ${core.MAX_TAKEAWAY_LENGTH} 字，只保存在本机。`;
  });

  els.storyDialogClose.addEventListener("click", () => els.storyDialog.close());
  els.storyDialog.addEventListener("click", (event) => closeOnBackdrop(els.storyDialog, event));
  els.storyDialog.addEventListener("close", () => {
    state.currentStory = null;
    els.takeawayHelper.textContent = "最多 180 字，只保存在本机。";
  });

  els.searchTrigger.addEventListener("click", openPalette);
  els.searchDialogClose.addEventListener("click", () => els.searchDialog.close());
  els.searchDialog.addEventListener("click", (event) => closeOnBackdrop(els.searchDialog, event));
  els.paletteSearchInput.addEventListener("input", (event) => {
    state.paletteIndex = 0;
    renderPalette(event.target.value);
  });
  els.paletteSearchInput.addEventListener("keydown", (event) => {
    if (!state.paletteItems.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      state.paletteIndex = (state.paletteIndex + 1) % state.paletteItems.length;
      renderPalette(event.currentTarget.value);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      state.paletteIndex = (state.paletteIndex - 1 + state.paletteItems.length) % state.paletteItems.length;
      renderPalette(event.currentTarget.value);
    } else if (event.key === "Enter") {
      event.preventDefault();
      const item = state.paletteItems[state.paletteIndex];
      els.searchDialog.close();
      openStoryDialog(item, "从搜索结果中找到的信号。");
    }
  });

  window.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase() === "k") {
      event.preventDefault();
      openPalette();
    }
  });

  init();
})();
