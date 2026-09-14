# Signal Radar

Signal Radar 是一个个人使用的高质量信息发现系统。它每天从多个来源发现候选内容，先用低成本信号缩小候选池，再对少量内容进行深度评审，最终只保留真正值得阅读的内容。

它服务于这条长期输入链路：

> Signal Radar → 阅读 → 思考 → 讨论 → Thoughtbase

第一版刻意保持简单：Python 处理采集和排序，Astro 生成静态阅读界面，JSON 保存每日结果，GitHub Actions 负责定时运行。没有数据库、账户、复杂 Agent 框架、向量数据库或微服务。

## 当前能力

- 可扩展来源：RSS / Atom、Hacker News API、可替换的 Web Search Provider
- Brave Search 可选接入；没有密钥时 RSS 与 HN 仍会正常运行
- 标准化、URL 与标题相似度去重、来源优先级合并
- `ai-news`、`product-insight`、`career`、`other` 四类分类
- 基于标题、来源、摘要、时效性和互动数据的 Pre-Ranking
- 只对前 40 条（可配置）候选抓取正文并进行 Deep Review
- 正文抓取失败时回退到 metadata，并标记 `contentAvailability: partial`
- 三套独立评分 Rubric，保留每个 0–5 分子指标，并加权为 0–100
- Must Read / Worth Reading / Signals 阈值与数量限制
- 基于来源与主题的轻量多样性重排
- 默认按约 50% 中文 / 50% 外文进行最终语言平衡，只在达到质量阈值的内容中分配
- 首页、文章详情、关键观点、质疑视角、术语解释与评分拆解
- 非中文文章提供独立的中文核心译文；不永久保存任意网页的完整全文
- 基于 `localStorage` 的 `read`、`worth-it`、`not-worth-it`、`saved`、`thoughtbase` 反馈
- 单来源失败、文章解析失败和 LLM 失败都不会终止整条 Pipeline

仓库自带一份明确标记为 `DEMO REVIEW` 的示例 Daily JSON，因此前端安装后即可浏览。示例内容只用于展示信息结构与界面，不代表实时资讯。

## 项目结构

```text
signal-radar/
├─ collector/
│  ├─ sources/        # RSS、HN、搜索 Provider
│  ├─ fetchers/       # 正文的临时、尽力提取
│  ├─ ranking/        # 分类、去重、预排序、评分、多样性重排
│  ├─ llm/            # Mock 与 OpenAI Deep Review Provider
│  └─ pipeline/       # 每日端到端编排
├─ config/
│  ├─ sources.yaml
│  └─ ranking.yaml
├─ data/
│  ├─ daily/          # 日期 JSON 与 latest.json
│  └─ cache/          # 可丢弃缓存，不进入版本控制
├─ scripts/daily_pipeline.py
├─ src/               # Astro 页面、组件和样式
└─ .github/workflows/daily-radar.yml
```

## 本地运行

需要 Python 3.11+ 和 Node.js 20+。

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
npm install
```

macOS / Linux：

```bash
source .venv/bin/activate
pip install -r requirements.txt
npm install
```

先用离线样例验证完整 Pipeline：

```bash
python scripts/daily_pipeline.py --sample
```

运行前端：

```bash
npm run dev
```

生产构建：

```bash
npm run build
```

静态文件会生成到 `dist/`。

## 环境变量

本地使用时，复制 `.env.example` 为 `.env` 并填入需要的值；Pipeline 会自动读取。GitHub Actions 使用仓库 Secrets / Variables。

```powershell
Copy-Item .env.example .env
```

| 变量 | 必需 | 作用 |
| --- | --- | --- |
| `OPENAI_API_KEY` | 否 | OpenAI 或兼容第三方供应商提供的 API Key |
| `OPENAI_BASE_URL` | 否 | API 根地址，默认 `https://api.openai.com/v1`；第三方通常提供自己的 `/v1` 地址 |
| `OPENAI_MODEL` | 否 | 默认 `gpt-5-mini`；第三方接入时填写供应商实际支持的模型名 |
| `OPENAI_API_STYLE` | 否 | `auto`、`responses`、`chat_completions`；默认自动识别与回退 |
| `OPENAI_STRUCTURED_OUTPUT` | 否 | `auto`、`true`、`false`；供应商不支持 JSON Schema 时会自动回退到普通 JSON |
| `OPENAI_ENABLE_THINKING` | 否 | 混合推理模型的思考开关；Qwen 等模型需要快速生成结构化结果时可设为 `false` |
| `OPENAI_REASONING_EFFORT` | 否 | 推理强度；支持的 Qwen 兼容接口可设为 `none`，其优先级通常高于思考开关 |
| `LLM_PROVIDER` | 否 | `auto`、`openai`；默认 `auto` |
| `LLM_REQUEST_TIMEOUT_SECONDS` | 否 | 单次 LLM 请求超时，默认 60 秒 |
| `LLM_MAX_RETRIES` | 否 | 每种兼容请求的最大尝试次数，默认 2 |
| `LLM_CONSECUTIVE_FAILURE_LIMIT` | 否 | 连续失败多少次后停用本轮 LLM 并回退，默认 2 |
| `BRAVE_SEARCH_API_KEY` | 否 | 配置后启用 Brave Web Search |
| `REQUEST_TIMEOUT_SECONDS` | 否 | 普通网络请求超时，默认 15 秒 |
| `USER_AGENT` | 否 | 文章抓取时的 User-Agent |
| `RADAR_TIMEZONE` | 否 | Daily JSON 的归档时区，默认 `Asia/Shanghai` |

当 `OPENAI_API_KEY` 缺失时，Pipeline 使用确定性的 Metadata Reviewer，真实采集仍会运行且不会产生 API 费用；页面会明确显示 `METADATA REVIEW`。设置 `LLM_PROVIDER=openai` 但未设置密钥时，该错误会被记录，流程会安全降级到 Metadata Review。

真实 LLM 层兼容 OpenAI Responses API 和 Chat Completions API。官方地址默认优先使用 Responses；第三方地址默认优先使用兼容范围更广的 Chat Completions。若供应商不支持严格 JSON Schema，系统会自动改用普通 JSON 输出。最终分数仍由本地评分权重计算，避免模型自行改变 Rubric。

第三方供应商的典型配置如下（具体地址和模型名以供应商文档为准）：

```dotenv
OPENAI_API_KEY=第三方供应商提供的密钥
OPENAI_BASE_URL=https://供应商域名/v1
OPENAI_MODEL=供应商支持的模型名
OPENAI_API_STYLE=auto
OPENAI_STRUCTURED_OUTPUT=auto
```

`OPENAI_BASE_URL` 应填写 API 根地址，不要在末尾添加 `/chat/completions` 或 `/responses`。若自动模式不能正确判断，可明确设置 `OPENAI_API_STYLE=chat_completions` 或 `OPENAI_API_STYLE=responses`。

## 添加 RSS / Atom 来源

编辑 `config/sources.yaml`，在 `sources` 中增加：

```yaml
- name: Example Research Blog
  url: https://example.com/feed.xml
  type: rss
  category: product-insight
  priority: high
  language: en
```

支持的 `category`：`ai-news`、`product-insight`、`career`、`other`。

支持的 `priority`：`high`、`medium`、`low`。优先级只参与候选阶段，不会直接替代 Deep Review。

来源只出现在配置中，不需要修改业务代码。

## 配置 Web Search Provider

搜索入口由 `WebSearchProvider` 抽象。第一版实现 `BraveSearchProvider`，通过 `BRAVE_SEARCH_API_KEY` 读取密钥。

搜索词和预设分类位于 `config/sources.yaml`：

```yaml
web_search:
  provider: brave
  enabled: true
  max_results_per_query: 8
  queries:
    - query: AI product management deep analysis case study
      category: product-insight
```

要增加其他搜索服务，实现 `collector/sources/web_search.py` 中的 `WebSearchProvider.search()`，返回统一的 `title`、`url`、`snippet` 等字段即可。不要让新的 Provider 泄漏到分类或排序逻辑中。

## 运行 Daily Pipeline

联网运行一次：

```bash
python scripts/daily_pipeline.py
```

指定归档日期：

```bash
python scripts/daily_pipeline.py --date 2026-09-13
```

每次运行会写入：

- `data/daily/YYYY-MM-DD.json`
- `data/daily/latest.json`
- `data/errors/YYYY-MM-DD.jsonl`（仅在有非阻塞错误时生成，不提交）

Pipeline 不会把抓取到的完整正文写入磁盘；正文只在当前进程内用于评审。

## 调整推荐规则

所有阈值、数量、候选池大小、去重相似度和评分权重都在 `config/ranking.yaml`。

默认规则：

- Must Read：`finalScore >= 88`，最多 3 条
- Worth Reading：`finalScore >= 78`，最多 5 条
- Signals：AI 新闻独立选择，默认阈值 64，最多 10 条
- 最终总量：最多 8 条，并尽量保持中文与外文各半
- 同一来源与同一首要主题默认每档最多 2 条

系统不会为了凑满数量降低阈值。

## GitHub Actions

`.github/workflows/daily-radar.yml` 每天北京时间约 07:00（UTC 23:00）运行，也支持手动触发。它会：

1. 安装 Python 和 Node.js 依赖
2. 运行 Daily Pipeline
3. 构建 Astro，确保新 JSON 能生成页面
4. 仅在 `data/daily` 发生变化时提交结果

在仓库设置中按需增加：

- Secret：`OPENAI_API_KEY`
- Secret：`BRAVE_SEARCH_API_KEY`
- Variable：`OPENAI_BASE_URL`
- Variable：`OPENAI_MODEL`
- Variable：`OPENAI_API_STYLE`
- Variable：`OPENAI_STRUCTURED_OUTPUT`

没有搜索密钥不会影响 RSS / HN；没有 OpenAI 密钥会使用 Mock Review。若你不希望自动提交 JSON，可以删除工作流中的 `Save new digest` 步骤，改由部署平台直接构建。

## 部署 Astro 前端

这是纯静态 Astro 项目，任何能托管 `dist/` 的平台都可以部署，例如 GitHub Pages、Cloudflare Pages、Netlify 或 Vercel。

通用配置：

- Build command：`npm run build`
- Output directory：`dist`
- Node.js：20+

如果部署平台在独立构建任务中运行，确保最新的 `data/daily/latest.json` 已经存在于仓库或在构建前先执行 Daily Pipeline。

## 反馈数据与未来推荐

浏览器反馈保存在 `signal-radar:feedback:v1`：

```json
{
  "article-id": {
    "read": true,
    "worth-it": true,
    "not-worth-it": false,
    "saved": true,
    "thoughtbase": false
  }
}
```

`worth-it` 与 `not-worth-it` 在界面中互斥。未来接入推荐算法时，可把这份结构同步到持久层，计算 Top 3 与最终推荐的实际 precision；当前 MVP 不上传任何个人反馈。

## 验证目标

Signal Radar 的核心指标不是抓取量，而是高质量推荐的 Precision：

- 每天最终推荐中，至少 5 篇主观上“值得读”
- Top 3 Must Read 中，至少 2 篇值得完整精读

先持续记录 `worth-it` / `not-worth-it`，再根据实际误判调整来源、Rubric 和阈值；不要因为某一天内容少就扩大范围。
