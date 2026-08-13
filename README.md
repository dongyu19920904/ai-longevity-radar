# 爱窝啦 AI生命延续学雷达

独立的 AI × 长寿研究信号雷达。每小时从公开论文数据库、临床试验注册库、研究机构 RSS、GitHub 项目和通用 AI 雷达公开 JSON 抓取候选，并用可解释的“双相关”规则筛选。

- 网站：<https://radar.aibioo.cn/>
- AI生命延续学日报：<https://news.aibioo.cn/>
- 通用 AI 雷达：<https://radar.aivora.cn/>
- 爱窝啦主站：<https://www.aivora.cn/>

## 独立边界

这个仓库拥有自己的抓取、评分、归档、测试、GitHub Actions 和 GitHub Pages 部署。它不会读取 AI生命延续学日报的私有数据，也不会依赖日报构建成功。日报只通过外链和以下公开 JSON 渐进接入：

- `data/latest-24h.json`：24 小时双相关信号。
- `data/briefing-lite.json`：最多 8 条的轻量摘要。
- `data/source-status.json`：各采集器健康状态。
- `data/topic-stats.json`：主题、研究对象和证据阶段统计。

公开 JSON 使用 `bio-radar-v1` schema。新增字段可以向后兼容地加入；破坏性变更必须升级 schema 版本。

## 数据管线

```mermaid
flowchart LR
  A["Europe PMC"] --> F["独立抓取"]
  B["ClinicalTrials.gov"] --> F
  C["机构与行业 RSS"] --> F
  D["GitHub 研究项目"] --> F
  E["通用 AI 雷达公开 JSON"] --> F
  F --> G["实体去重"]
  G --> H["AI 相关评分"]
  H --> I["生命延续相关评分"]
  I --> J["证据与风险标签"]
  J --> K["公开 JSON + 静态站"]
  K --> L["AI生命延续学日报渐进接入"]
```

DOI、PMID、NCT 编号和 GitHub `owner/repo` 优先作为实体键；普通页面使用去跟踪参数后的规范化 URL。单一采集器失败不会阻断其他来源，仍在 24 小时窗口内的归档记录会继续保留。

## 评分边界

条目必须同时达到 AI 与生命延续相关阈值才进入默认视图。输出还会标注研究对象、发表阶段、证据类型和风险提示。这里的“高分”表示交叉主题信号较强，不表示治疗有效、适用于人类或具备临床价值。

完整说明见 [methodology.html](methodology.html) 和 [docs/SOURCE_COVERAGE.md](docs/SOURCE_COVERAGE.md)。

## 本地验证

Windows 环境按项目约定把临时目录和工具缓存放到 `D:\CodexCache`：

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q -p no:cacheprovider
node --test tests/frontend-core.test.cjs tests/frontend-contract.test.cjs
python scripts/update_longevity_radar.py --output-dir data --window-hours 24 --archive-days 21
python -m http.server 8080
```

## 安全与隐私

- 只使用无需登录的公开来源。
- 不提交 token、Cookie、私有 OPML、邮箱内容或个人健康数据。
- 前端只允许 `http` / `https` 链接，不使用抓取内容写入 `innerHTML`。
- 本站是研究信息索引，不提供医学建议、诊断或治疗指导。

## 许可

[MIT](LICENSE)
