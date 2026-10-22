<p align="center">
  <img src="assets/readme/hero.svg" width="100%" alt="Argo 阿尔戈：给 Agent 用的搜索与深度研究工具，272 个搜索源，按域按语言选路，输出可吸收的证据">
</p>

<p align="center">
  <strong>中文</strong> ·
  <a href="README.en.md">English</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.es.md">Español</a>
</p>

<p align="center">
  <a href="#这是什么">介绍</a> ·
  <a href="#它和模型自带搜索--ai-搜索--聚合搜索比强在哪">对比</a> ·
  <a href="#问啥像啥">证明</a> ·
  <a href="#它怎么工作">机制</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#能做什么">能力</a> ·
  <a href="#安装与配置">配置</a> ·
  <a href="#最近更新">更新</a>
</p>

<p align="center">
  <img alt="license" src="https://img.shields.io/badge/license-Apache_2.0-blue">
  <img alt="python" src="https://img.shields.io/badge/python-3.9+-green">
  <img alt="version" src="https://img.shields.io/badge/version-2.9.7-informational">
  <img alt="engines" src="https://img.shields.io/badge/engines-272-orange">
  <img alt="mcp" src="https://img.shields.io/badge/MCP-19%20tools-purple">
</p>

> **这是踏雪寻仙 DeepSeek Harness 插件系列的一员**（[dsh-files](https://github.com/taxueseek/dsh-files) 39★ · [dsh-models](https://github.com/taxueseek/dsh-models) 模型选择 + 子代理路由 + 推理层级）。同作者完整技能系列：[session-digger](https://github.com/taxueseek/session-digger) 29★ · [taxue-invest](https://github.com/taxueseek/taxue-invest) 21★ · [taxueskills](https://github.com/taxueseek/taxueskills) 23★ · [taxue-creative-style](https://github.com/taxueseek/taxue-creative-style) 12★

# Argo 阿尔戈：给 Agent 用的搜索与深度研究工具

## 这是什么

**Argo 是一个装在 Agent 里的搜索与深度研究工具，也可以获取相关网页的信息。背后连着 272 个搜索源，覆盖 97 个业务领域，同时支持本地文件的基础搜索能力。在开源搜索项目里，具备非常强大的搜索能力。**

支持配置 API Key 提升搜索质量（配了 Key 的源质量通常更好，没配则自动跳过），也支持免费引擎和本地引擎自动保底。覆盖中英日韩等 18 种语言，支持金融、学术、影视、体育、代码、宏观等垂直场景。

## 子技能

Argo 的能力通过四个子技能（sub-skills）组织，每个子技能是一条独立可用的管线：

| 子技能 | 能力 |
|--------|------|
| **local-search** | 本机文件搜索 + 本地零成本聚合引擎（32 个本地引擎）。搜代码符号、文件名、文档全文、文件结构。可并入网络搜索结果，加一个开关本机命中就并进同一次搜索 |
| **local-seek** | 本地语义搜索（BM25 + 向量混合），搜笔记、记忆、资料库。三层递进：先定位文件、再看上下文、最后精读段落 |
| **ego-search** | 登录态专业搜索。知乎、小红书、公众号等需要登录才能看的内容，用真实浏览器配合登录态去搜。默认关闭，需时开启 |
| **js-run** | 无浏览器执行网页 JS。不开浏览器跑「环境探测 + 纯计算」型网页脚本，单次上下文 P50 约 1ms |

四个子技能覆盖了从「搜本机」到「搜全网」到「搜登录墙后面」的完整链路。大部分场景用 local-search + 联网搜索就够，特殊场景再开 ego-search 和 js-run。

## DSH 插件

Argo 同时是 DeepSeek Harness 的插件，一行命令装好：

```bash
dsh plugin --profile web add "github:taxueseek/argo"
```

装完重启 `dsh web` 即生效。搜索和抓取成为原生一等工具，不依赖 MCP 连接，不占常驻上下文开销。另有 1 个 `wide_research` 并行研究和 19 个 MCP 工具按需开启。完整接入形态见下文。

### 三种调用通道，一套能力

同一个 argo 检索内核（同引擎、同压缩、同守卫）在 DSH 里开三条通道，按宿主能力自动降级、互为冗余：

| 通道 | 默认 | 说明 |
|------|------|------|
| **原生一等工具** | 开 | `argo_search` / `argo_fetch` 等经 `ctx.tools.register` 注册，走 CLI 单发（`--call`）复用 MCP 同一套引擎与守卫，**不依赖 MCP 连接、零常驻 token 开销** |
| **原生 web seam** | 开 | 注册 `argo` 搜索与抓取两个 provider，宿主内置 `web_search` 路由到 argo 引擎链、`web_fetch` 走 argo 抓取链（HTTP 优先，遇 Cloudflare / JS 渲染自动升级反检测浏览器） |
| **MCP 形态** | 按需 | 19 个 `mcp__argo__*` 完整工具面。工具定义每轮注入上下文且压缩清不掉（实测 19 工具 ≈3.7K token/轮），而高频路径已由原生工具与 web seam 覆盖，故默认不挂载；需要长尾取证能力时在 profile patch 中取消 `mcp-argo` 行注释 |

另有 1 个 `wide_research`：规划互补轨道（`depends_on` 依赖分阶段，默认并行）→ 有界并发子代理取证 → 来源账本（仅 http(s) URL 入账）→ 综合报告；输出自带 `quality_gate_results`（`conclusion_cap`：low/medium/high），`passed=false` 时降级表述、先核验账本来源再下结论。worker 取证工具白名单默认双写 MCP 与原生工具名（allow 语义）——MCP 挂载与否两态自洽：MCP 在时用全量面，缺席时自动落到 `argo_search` / `argo_fetch` 与宿主 `web_search` / `web_fetch`。

日常一问用 `argo_search`；单代理取证用 `argo_research`；多视角对比、要引用账本用 `wide_research`。worker 默认只能调 argo 取证工具，不会再调 `argo_research`（硬保护，用户层放行也无效）。

### 自带设置页：六个分区，改完即生效

插件自带浏览器端设置页，两个入口：设置弹窗（`Cmd+,`）左侧一级菜单「Argo」，或 设置 > 插件 > Argo（同一面板的摘要卡片，点开即用）。

<p align="center">
  <img src="assets/readme/settings-tools.webp" width="100%" alt="Argo 设置页「工具」：18 个原生工具的勾选——高频路径默认开 argo_search / argo_fetch，长尾 16 个按需，下方是单次调用超时与返回文本上限">
</p>

<p align="center">
  <img src="assets/readme/settings-engines.webp" width="100%" alt="Argo 设置页「引擎」：argo 本体 28 个行为开关移进面板——缓存 / TF-IDF 重排 / 数值交叉校验 / MinHash 去重 / SERP 守卫与去重阈值，未配置行显示默认态，改完即时生效">
</p>

<p align="center">
  <img src="assets/readme/settings-keys.webp" width="100%" alt="Argo 设置页「密钥」：DeepSeek 官方搜索显示「已配置 · 凭证库」并与宿主 web_search 共用同一把 key；腾讯元宝 / Tavily 等常用引擎 key 可填写、更新、清除，明文不回显">
</p>

| 分区 | 管什么 |
|------|--------|
| **接入** | `web_search` / `web_fetch` seam 开关；引擎入口命令与参数（npx 或本机 `mcp_server.py`）；搜索/抓取超时、正文上限、连接空闲回收、并发连接数 |
| **工具** | 18 个原生一等工具的勾选（默认只开 `argo_search` / `argo_fetch`）；单次调用超时与返回文本上限 |
| **引擎** | argo 本体的行为开关（原环境变量，curated 白名单 28 个：缓存 / TF-IDF 重排 / 数值交叉校验 / MinHash 去重 / SERP 守卫、Jina / 移动端 UA / Parallel 抓取层、语义证据层、对冲宽限与尾宽、引擎启停名单、代理、本机检索根与读取白名单、预热 / 使用日志 / 连接池 / 各类 TTL）。开关类即时生效，数字 / 文本 / 名单类分组保存；未配置行显示 argo 默认态并标注「默认」。授权类开关（可复算执行、内网 URL）刻意不进面板 |
| **密钥** | 常用引擎 key 的填写、更新、清除；显示「已配置 / 未配置 + 来源层（凭证库 / 启动环境 / .env）+ 只读态」，明文不回显；每行可勾选「转发」，等价于把引用名加进 `keyRefs` |
| **研究** | worker / 轨道 / 每轨信源 / token 上限与报告落盘目录 |
| **高级** | worker 工具 allow / deny 名单、凭证转发名单 |

保存即生效（全部为 volatile 配置）：原生工具集合按勾选增删注册，超时、并发、研究上限在下一次调用时读取；引擎开关写成 `argoEnv`（一行一个 `KEY=VALUE`）随 argo 子进程 env 进入，对下一次新建连接生效（池内旧连接按 `searchIdleMs` 回收，默认 60s）。结构性字段（`toolName`、`provider`、`searchProviderId`、`fetchProviderId`）不在设置页，仍走 profile patch，改后需重启。

**密钥安全**：写入 DSH 凭证库（与 Models 页同一处），不写进插件配置、不打日志、不回显明文。凭证服务优先级为**存储文件层 > 启动环境 > 项目 .env > 家目录 .env**：在面板（或 Models 页）保存即覆盖启动环境里的旧值，argo 子进程下一跳新连接用新 key；「清除」只删凭证库里的值，环境变量或 `.env` 提供的 key 会重新露出。设置页只是凭证域的写入口，读取仍由宿主在每次调用时完成。

**DeepSeek 官方 key 原生供给**：argo 的 `deepseek_search` 引擎（官方 `api.deepseek.com/v1/tools/search`，结果自带 authority 权威分级 / rerank_score 排序分 / 发布时间）与 DSH 官方搜索后端**共用同一把 key**。插件经 DSH 原生凭证 seam 取用，不需要任何手工配置：解析路径 `ctx.get('credentials').resolve('DEEPSEEK_API_KEY')`，逐次解析——在 web Models 页轮换 key 后，下一跳新连接即生效，无需重启插件。插件不读 key 文件、不落盘、不打日志；key 值只经内存进入 argo 子进程 env，任何输出与错误信息都不含它。旧宿主无 credentials 服务时静默跳过：argo 侧该引擎按缺 key 停用，其余 271 个源不受影响。

**web seam 的 pin 必读**（漏配会打挂 `web_fetch`）：宿主 `dsh-web` 的 provider 选择规则是「配置 id 优先；都没有且恰好一个可用则选它；**多个可用直接报 `WEB_PROVIDER_AMBIGUOUS`**」。web profile 默认挂着官方 http fetch provider（免 key、永远可用），本 bundle 再注册一个就是两个可用——**不 pin 的话 `web_fetch` 整个挂掉**（`web_search` 同理，若 profile 里另有搜索 provider）。故启用 web seam 的 profile 必须在 web 服务行显式指定：

```yaml
- id: web
  config:
    searchProvider: argo    # 已默认启用搜索 seam 时必配
    fetchProvider: argo     # 已默认启用抓取 seam 时必配
```

`searchProviderEnabled: false` / `fetchProviderEnabled: false` 可整体关掉对应 seam（provider 仍注册但不可选，不影响另一个）。搜索引擎侧，Firecrawl 等匿名可用引擎 **keyless 免配置即用**（免费层额度），配置了密钥的引擎自动升级为认证请求；缺密钥不阻断路由。

> 完整配置项、Compatibility 版本对照表与卸载方式见 [packages/dsh-plugin/README.md](packages/dsh-plugin/README.md)。

## 核心优势

**272 个源，235 个免密钥开箱可用。** 不配任何 API Key 就能跑，免费引擎和本地引擎自动保底。配了 Key 的源质量通常更好，没配则自动跳过。一次安装，全场景可用。

**本地搜索 + 联网搜索一体。** 这是 Argo 独一份的能力。本机文件搜索底层是 rg、mdfind 那套开发者日常工具，搜代码符号、文件名、文档全文、文件结构。加一个开关，本机命中会并进同一次网络搜索结果里，结果上标着来源是本机文件。写东西时记得自己半年前记过一段话但忘了在哪，用这个搜比翻文件夹快。

**双层缓存，热查询约 10ms。** 时效性没那么强的内容（百科类、历史数据这类），第一次查完会进缓存，之后同样的查询直接命中，不再每次都走一遍 API。既省钱也省时间。

**多语言 + 垂直场景。** 实测过 18 种语言，中文、英文和日文能查到当地一手来源。问论文走学术库，问影视走条目库，问代码走问答社区，问行情走金融源。泛泛的问题才走通用搜索。

## 装完就能用

零配置就能跑。三种装法，按你的习惯挑：

**想让 AI 助手自己会搜**，把技能包装进它的技能目录。以后你说「帮我查一下」「核实一下」，它会自己去查。

**想随手试**，用一条 npx 命令即用即走，不用装。

**想让助手常驻着用**，给它挂上 MCP，19 个检索工具随时可用。还有一键注入命令，能给 Claude Code、Cursor 和 Windsurf 自动配好，Codex、OpenCode 和 Cline 也在这个名单里。写配置前会备份，随时能撤。

```bash
# 方式一：一键脚本（推荐本机长期用）
curl -fsSL https://raw.githubusercontent.com/taxueseek/argo/main/scripts/install.sh | bash

# 方式二：npx 即用即走（推荐 Agent 快速挂载）
npx -y github:taxueseek/argo

# 方式三：git clone（开发 / 改源码）
git clone https://github.com/taxueseek/argo.git
```

装完随手试一条：

```bash
argo search "python asyncio error handling"
```

它给你的是 StackOverflow 官方 API 里按社区得分排过序、标了采纳状态的问题，不是一堆 SEO 农场。

想看看自己机器上现在有几个源可用，一条命令就列出来：

```bash
argo search --list-engines
```

## 接入形态

Argo 支持四种接入方式，按你的场景挑：

| 形态 | 适合 | 说明 |
|------|------|------|
| **MCP Server** | Agent 常驻挂载 | 19 个检索工具随时可用，一条命令注入 Claude Code / Cursor / Windsurf / Codex / OpenCode / Cline，写配置前自动备份 |
| **DSH 插件** | DeepSeek Harness 用户 | 一行 `dsh plugin add` 装好，搜索和抓取成为原生一等工具，不依赖 MCP 连接，不占常驻上下文开销；自带六分区设置页，改完即生效 |
| **Skill 文件** | Claude Code / Grok Build / Kimi 等 | 技能包装进 Agent 的技能目录，你说「帮我查一下」「核实一下」，它自己去查 |
| **npx 即用即走** | 快速试一下 | `npx -y github:taxueseek/argo`，不用装，适合临时把 MCP 挂进任意客户端 |

四种形态底层是同一套 Python 代码，CLI 与 MCP 工具一一对应，装哪种都不缺能力。

## 它和「模型自带搜索 / AI 搜索 / 聚合搜索」比，强在哪

> 简单来说：前三种方案解决「**人**找信息」，Argo 解决「**Agent 及搜索核查于一身，具备一条龙的搜索服务**」。差别不在界面，在交付物，给人看的叫总结页或链接清单，给 Agent 的应是能排序、能复核、不撑爆上下文的优质内容，更可靠的搜索信息。

<p align="center">
  <img src="assets/readme/why-better.svg" width="100%" alt="左侧三种默认搜索给人看的结果，右侧 Argo 给 Agent 的可吸收证据 JSON">
</p>

| 维度 | 模型自带搜索 | AI 搜索（总结型） | 聚合搜索 / 搜索引擎 | **Argo** |
|------|------------|-------------------|---------------------|----------|
| 结果形态 | 拼好的长文本 | 给人看的总结页 | SERP 链接清单 | **精简 JSON：证据候选 + 可信度分解** |
| 垂直问题（行情 / 化学式） | 泛搜网页 | 泛搜再总结 | 泛搜网页 | **直连垂直源，直接给答案** |
| 证据可信度 | 无评分 | 无结构化评分 | 无评分 | **selection · absorption · freshness · 共识** |
| 重复查询 | 每次都打网 | 每次都打网 | 靠页面缓存 | **双层缓存（内存 + SQLite），热查询约 10ms** |
| 成本控制 | 不可控 | 单次贵 | 免费但费事 | **预算模式，免费优先，Key 全可选** |
| 多语言 | 随模型走 | 随模型走 | 随引擎走 | **语言检测 + 引擎语言参数 + 多国语言支持** |

> 机制上，Argo 把搜索当成一条**证据管线**：语言检测 → 领域路由 → 多引擎召回 → RRF 融合 → 证据快评，交付的是 Agent 可直接排序、可 `fetch` 复核、不撑爆上下文的材料。工具链不用换，需要换的是「搜索结果应该长什么样」——再往下一层，还有和「再包一层搜索 API 的差别」，那是实现细节的对比。

---

## 2026，检索正在发生什么变化

Agent 干活的量级变了，检索的玩法跟着变了五件事，每一件 Argo 都已经落在代码里：

1. **检索从「给链接」变成「给证据」。** Agent 不看网页排版，它要能排序、能复核、不撑爆上下文的结构化材料——所以 Argo 交付的是带可信度分解的 JSON，而不是 SERP 清单。
2. **上下文成为第一成本。** 一次网页抓取动辄上万 token，Agent 的窗口烧不起。Argo 的 Agent 档单次约 3.7KB，字段集合与字节预算都有检查卡着，升级不会悄悄变胖。
3. **网站开始为 AI 备料。** llms.txt 标准与 `.md` 直出在头部文档站快速铺开——Argo 抓取链第零级自动探测这些 AI 友好变体，命中即跳过整条反爬链；HTTP/TLS 都失败还有 r.jina.ai 阅读器级保底。
4. **免费开放生态够用了。** 政府、学术、标准、安全机构的开放 API + 免 key 引擎，已经能覆盖大多数领域（235 个免配置源）；稀缺免费额度（firecrawl 1000 credits/月、stackexchange 300 次/天）做了「日常补位、关键顶上」的分层，订阅墙不是唯一解。
5. **检索质量从「感觉」到「度量」。** 排序有金标（MRR/nDCG 地板）、融合有增益消融检查、路由有负向控制矩阵——「这版比上版好吗」从此是数字问题，不是玄学。

> 以上五项已经在 v2.9.x 系列里全部落地：272 个源、97 个领域、235 个免配置开箱。逐项细节见 [docs/为什么选择argo.md](docs/为什么选择argo.md) 与 [发布说明](docs/RELEASE_NOTES_v2.9.0.md)。

---

## 问啥像啥

<p align="center">
  <img src="assets/readme/proof-routes.svg" width="100%" alt="四类真实路由：金融、影视、多语言、地理">
</p>

| 你这样问 | 大致会怎样 |
|----------|------------|
| python asyncio error handling | 编程问答域 → StackOverflow/StackExchange 官方 API，带得分与采纳标记 |
| AAPL / 美股盘前 | 美股域，与 A 股分流 |
| 肖申克的救赎 主演 / Inception director | 影视域 → IMDb 等 |
| 梅西 俱乐部 / 库里 球队 | 体育域 → TheSportsDB 等 |
| 埃菲尔铁塔在哪 / where is Eiffel Tower | 地理实体 → OpenStreetMap 等 |
| NASA founding year / 国务院职能 | 组织实体 → Wikidata 等 |
| 周杰伦 专辑 / Taylor Swift album | 媒体域 → iTunes 等 |
| アニメ おすすめ / 한국 영화 추천 | 识别日/韩语 → 语言友好源，少塞中文专用站 |
| 美国 CPI、日本 通胀率 | 宏观数据域；国别分流（本国权威源优先） |
| log4j 漏洞 CVSS / nodejs 22 end of life | 安全域 → NVD 官方；生命周期域 → endoflife.date |
| attention is all you need | 学术域 → arXiv/OpenAlex/CrossRef，元数据与 DOI 直连 |
| 阿司匹林 分子式 | 化学域 → PubChem 类答案 |
| 台积电估值分歧（深度研究） | 拆子问题 + 多源并行，垂直源被 boost |

---

## 它怎么工作

<p align="center">
  <img src="assets/readme/workflow.svg" width="100%" alt="查询 → 语言与域 → 多引擎召回 → RRF → 证据快评 → 统一 JSON">
</p>

```
查询
  ├─ 意图消歧（可选）
  ├─ 查询改写（可选；路由仍看原始意图）
  ├─ 语言检测 + 语言偏好
  ├─ 路由（域规则 + TF-IDF + 预算 + 语言补充源 + 热路径缓存）
  ├─ 多引擎召回（熔断 / 负缓存 / 并行）
  ├─ 空结果分阶恢复（放宽 → 换同族/通用 → 跨语言；防污染）
  ├─ RRF 融合 + 可选精排
  ├─ 证据快评（权威 · 证据密度 · 时效 · 共识）
  └─ 统一 JSON（含 engine_outcomes / recovery / route_reason）
```

### 证据评分（简版）

```
selection  ≈ 域名权威，SERP/跳转链压到很低
absorption ≈ 数字 / 定义 / 对比 / 披露等证据密度
freshness  ≈ 发布时间（会忽略「2015 年以来」这类历史对比年）
综合       ≈ 0.40·selection + 0.35·absorption + 0.15·freshness + 0.10·引擎分
```

结果字段含 `selection`、`absorption`、`credibility_fast`、`evidence_flags` 等，方便 Agent 直接排序。

### Agent 使用纪律（建议）

1. **高后果问题**（持仓、安全、是否属实）：search → 看快评分 → 对 top 结果 `fetch` → 再下结论  
2. **数字**：写清计算方式，冲突时并列，不要硬合并  
3. **搜索结果页 / 跳转链**：不要当正文信源  
4. **社交帖**：当舆情与叙事，不当事实真值  
5. **事实核查**：宁可多一两条分层查询（来源 / 对比 / 主体）

---

## 快速开始

任选一种即可。**以 GitHub 为唯一安装来源**（`npx github:taxueseek/argo` 或 `install.sh` / `install.ps1`），当前推荐 **v2.9.7**。**请勿用 `npm install argo-search`**——npm registry 上那份是**非官方陈旧版 v1.0.1**（非本仓库维护，功能残缺、不随本项目更新）。本包 `package.json` 已设 `private: true` 防止误发布到 npm registry。

**零配置就能跑**：不配 API Key 时走免费引擎 + 本地 `local_*` 引擎；配了 Key 的源质量通常更好，没配则自动跳过。

### 方式一：一键脚本（推荐本机长期用）

macOS / Linux：

```bash
curl -fsSL https://raw.githubusercontent.com/taxueseek/argo/main/scripts/install.sh | bash
```

Windows（PowerShell）：

```powershell
powershell -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/taxueseek/argo/main/scripts/install.ps1 | iex"
# 或下载后执行：
# powershell -ExecutionPolicy Bypass -File scripts/install.ps1
```

装到指定目录、并挂 Skill 入口：

```bash
curl -fsSL https://raw.githubusercontent.com/taxueseek/argo/main/scripts/install.sh \
  | bash -s -- --home "$HOME/.local/share/argo" --link "$HOME/.claude/skills/argo"
```

验证：

```bash
python3 ~/.local/share/argo/scripts/search.py "python asyncio error handling" --json
python3 ~/.local/share/argo/scripts/search.py --list-engines
```

### 方式二：MCP 不装包，直接用 GitHub（推荐 Agent 快速挂载）

需要 **Node.js 18+** 和 **Python 3.9+**，首次执行一次：

```bash
pip3 install pyyaml
```

```bash
npx -y github:taxueseek/argo
```

客户端配置示例（Claude Code / Cursor / Kimi 等）：

```json
{
  "mcpServers": {
    "argo": {
      "command": "npx",
      "args": ["-y", "github:taxueseek/argo"]
    }
  }
}
```

### DeepSeek Harness 一键插件（.dsh-plugin bundle）

在 DeepSeek Harness 里一行安装（两种装法）：

```bash
# 装法 A：19 个 mcp__argo__* 工具（主包自带 bundle，与 MCP 全量相同）
dsh plugin --profile web add "github:taxueseek/argo"

# 装法 B：搜索工具 + wide_research 并行研究调度（子包）
dsh plugin --profile web add "github:taxueseek/argo#main&path:packages/dsh-plugin"
```

重启 `dsh web` 后生效。包结构见 `packages/dsh-plugin/`；同 id `mcp-argo` / `wide-research` 可在用户层 `cordis.patch.yml` 覆盖。装法 B 的 `wide_research` 模块只存在于子包依赖树，主包 patch 不引用它，避免只装主包时 Cordis 解析失败。DSH 0.2.1-alpha.1 与 0.2.1-rc.2 均已实测：rc.2 上 `wide_research`（2 worker，passed=true / 14 sources）与原生 `argo_search`（count=3）真跑通，`dsh web` 启动无 argo 报错；web seam 随启动注册通过（headless 无 web 服务，未做实际调用）。

### 依赖清单（通俗版）

| 依赖 | 必需？ | 干什么用 | 不装会怎样 |
|------|:------:|---------|-----------|
| **PyYAML** | ✅ 必需 | 读配置文件 | 完全跑不起来，安装脚本会自动装 |
| **curl_cffi** | ❌ 可选（v2.7.3 新增） | 模拟浏览器 TLS 指纹，过反爬站（Cloudflare 等） | 反爬站抓取成功率低一些，日常搜索无影响 |
| **rapidfuzz** | ❌ 可选（v2.9.5 新增） | 去重的模糊近重复复核：同文换站后缀/镜像站在 minhash 近似命中带内二次判定 | 跨站同文少合几条，去重召回略降；站后缀归一仍生效 |
| **ddgs CLI** | ❌ 可选 | 本地免 key 搜索的 10 个后端引擎 | 少一批零成本本地搜索源，其余不受影响 |
| **realtime-index CLI** | ❌ 可选 | 实时索引引擎（搜刚发布的内容） | 该引擎自动禁用，显式指定会回退通用引擎 |
| **Chrome** | ❌ 可选 | 页面截图、JS 渲染页、登录态抓取 | 截图工具不可用，其余正常 |
| **pdfplumber / PyMuPDF** | ❌ 可选 | PDF 提取 | argo_pdf 不可用，其余正常 |
| **Playwright** | ❌ 可选 | 截图增强 | 截图工具回退 Chrome CDP，其余正常 |

安装脚本（install.sh）只自动装前两个；其余可选依赖按需 `pip install` 或 `brew install` 即可。
更稳、完全不依赖 Node 的写法：先装脚本（方式一），再指向本机 Python：

```json
{
  "mcpServers": {
    "argo": {
      "command": "python3",
      "args": ["/path/to/argo/scripts/mcp_server.py"]
    }
  }
}
```

Python 路径特殊时：`export ARGO_PYTHON=/path/to/python3`（仅 npx 入口会读）。

### 方式三：git clone（开发 / 改源码）

```bash
git clone https://github.com/taxueseek/argo.git
cd argo
pip3 install pyyaml
bash scripts/install.sh --link ~/.claude/skills/argo   # 可选
python3 scripts/search.py --list-engines
```

---

## 适用平台

| 平台 | 接入方式 | 说明 |
|------|---------|------|
| **Claude Code** | MCP / Skill 链接 | `npx` 或 `mcp_server.py`；也可用 `link_source.py` |
| **Kimi / Grok Build** | MCP Server | 同上 |
| **Cursor / Cline / Continue** | MCP | 支持 MCP 的 IDE 插件均可 |
| **命令行** | `search.py` / `bin/argo` | 脚本、定时任务、人工排查 |
| **Python 项目** | `from search import super_search` | 库调用 |

### 安装后自检

```bash
python3 --version          # 需要 3.9+（Windows 可用 py -3）
python3 -c "import yaml; print('PyYAML OK')"
python3 scripts/search.py --list-engines            # 引擎面与状态总览
python3 scripts/search.py --list-engines --detail   # 逐源状态：配了 key 却没结果，
                                                    # 先看 missing_env 给出的确切变量名
python3 scripts/health_check.py --all               # 真联网探针：验证 key 对端真认（可选）
python3 bin/argo paths --check                      # 本机路径自检（可选）
python3 bin/argo mcp status                         # MCP 注入/连通诊断（可选）
python3 -m pytest tests/test_unit.py -q             # 单测（可选）
```

> MCP 起不来时：`python3 scripts/mcp_diag.py` 会把 stdin 往来记录到
> `~/.kimi/argo_diag.log`。`health_check.py` 是给人用的联网探针，
> `health_probe.py` 写健康库供路由消费——名字相近，职责不同。
> CLI 退出码恒 0（含断网）：成败判断走 JSON 的 `status` / `errors` 字段。

---

## 能做什么

### 七种能力，通俗说

**1. 通用搜索 + 垂直搜索，双管齐下**

日常问题走通用网页搜索；一问到行情、影视、体育、宏观这类「有标准答案」的问题，自动切到垂直源直接给答案，而不是扔给你一堆链接。目前 272 个源（235 个免密钥开箱可用）、97 个业务域，金融 / 宏观 / 影视 / 体育 / 地理 / 组织 / 媒体 / 化学 / 学术 / 代码等都有专门的路。

**2. 缓存：不重复花冤枉钱**

时效性没那么强的内容（百科类、历史数据这类），第一次查完会进缓存，之后同样的查询直接命中，不再每次都走一遍 API。双层缓存（内存 + SQLite），热查询约 10ms 级返回，既省钱也省时间。

**3. 专为 Agent 设计，更省 Token**

产出是「证据候选 + 可信度分解」的精简 JSON，不是长篇网页；MCP 响应可以按需裁剪，snippet 可控，不会撑爆 Agent 的上下文。比常规模型自带的搜索能力更专业、更省 Token。

**4. 深度研究**

把一个笼统的问题拆成多个子问题，多源并行采集，最后给出「还差什么证据」的缺口提示。适合综述、调研这类要全面、要扎实的场景。

**5. 登录态专业搜索（专业模式，默认关闭）**

知乎、小红书、公众号这类要登录才能看的内容，以及 JS 渲染页、反爬页，用真实浏览器配合登录态去搜。默认关闭，需要时开启，依赖 ego lite 和 WebBridge 两个东西，详见下节「登录态专业搜索」。

**6. 时间能力（时间窗 + 方向排序）**

要搜「最近几天刚发布的内容」，用 `--since 7d` 这类时间窗框住发布时间范围，判断新旧不再靠猜。支持引擎（如 `realtime_index`，免 Key 实时索引源、需自装 CLI，结果自带发布时间）把窗口下推给数据源；其余引擎的融合结果会按 `published_at` 最后再剔除明确超窗的条目（宽松策略，无时间字段的保留），返回包带 `time_filtered` 统计，CLI 与 MCP 均支持。`--since 7d` 与「7 天前的绝对日期」等价、共享缓存；`--until 2026-08-01` 含当天。配合 `--sort newest|oldest` 按发布时间重排——找最新动态用 `newest`，找最早出处用 `oldest`。

**7. 在 DSH 里当原生工具用**

装成 DSH 插件后，搜索与抓取是宿主的一等工具，不是外挂的 MCP 连接：`argo_search` / `argo_fetch` 直接可调，宿主的 `web_search` / `web_fetch` 也自动路由到 argo 的引擎链与抓取链。高频路径零常驻 token 开销，长尾取证能力（截图 / PDF / 社交 / 公众号 / 招聘 / 结构化提取 / 证据核验 / 意图消歧 / 站点爬取 / 批量预检 / 变化监控 / DOI 引用 / 本机检索）按需勾选开启。改配置不用碰文件——设置页六个分区改完即生效，密钥写进宿主凭证库、明文不回显。详见上文「DSH 插件」。

### 能力入口速查

| 能力 | 说明 | 入口 |
|------|------|------|
| 统一搜索 | 路由 → 召回 → 融合 → 快评 | `search.py` / `argo_search` |
| 本地文件搜索 | 本机代码/笔记/记忆（非联网） | `argo_local_search` |
| 本地文本预览 | 白名单目录内预览（fail-closed） | `argo_local_read` |
| 可复算 | 受限子进程重算数字（默认拒绝） | `argo_recompute` |
| 深度研究 | 拆子问题、多源采集、缺口提示 | `research.py` / `argo_research` |
| 可信度评估 | 权威 / 证据密度 / 时效 / 交叉验证 | `evidence.py` / `argo_evidence` |
| 证据核验（完整链路） | 高后果问题标记 `fetch_required` + 每条 `fetch_suggested`；`--verify` 一键抓正文核验、回填「核实后证据分」、核实过的链接自动记住 | `search.py --verify 3` / `research.py --verify 3` |
| 意图消歧 | 多义词、品牌碰撞、策略建议 | `clarify.py` / `argo_clarify` |
| 页面抓取 | HTTP 优先，必要时浏览器降级 | `argo_fetch`（`mode=extract` 可结构化） |
| 截图 / PDF | 页面截图、PDF 结构化提取 | `argo_screenshot` / `argo_pdf` |
| 站点爬取 | 列表页批量抓取 | `argo_crawl` |
| 查询操作符 | `site:`/`-site:`/`-词`/`-"短语"`/`"短语"`/`lang:`/`after:`/`before:` 从路由与检索两侧剥离（用法见 references/usage.md） | 查询词内直接写 |
| 结果可信信号 | `authority_level` 离散等级（0-4，≥3 极权威）+ `summary` 摘要档（核验后回填） | 结果字段，`--fields agent` 可见 |
| 社交与舆情 | 微博 / 小红书 / B 站 / Reddit / X 等 | `argo_social_search` |
| 实时索引搜索 | 免 Key 实时索引源，结果带发布时间，适合「最近几天有什么新东西」。**需自装 `realtime-index` CLI**（未安装时该源停用，见 ENGINE_CATALOG 已停用清单；多数查询走其他源不受影响） | `--engine realtime_index` |
| 时间窗过滤 | `--since` / `--until`（`7d` 或 `2026-08-01`）限定发布时间范围；支持引擎下推 + 融合后过滤（`time_filtered`），CLI 与 MCP 均支持 | `--since 7d` |
| 时间方向排序 | `--sort newest\|oldest` 按发布时间重排（最新动态 / 最早出处） | `--sort oldest` |
| 登录态专业搜索 | 知乎 / 小红书等登录墙正文、JS 渲染页、登录站点接口直取 | `sub-skills/ego-search/scripts/ego_search.py`（默认关闭，见下） |
| DSH 原生工具 | 装成 DSH 插件后 `argo_search` / `argo_fetch` 等成为宿主一等工具，走 CLI 单发、零常驻 token 开销 | `dsh plugin add` 后直接调 |
| DSH web seam | 宿主内置 `web_search` / `web_fetch` 路由到 argo 引擎链与抓取链（HTTP 优先，Cloudflare / JS 渲染自动升级浏览器） | 插件默认注册，profile 里 pin `searchProvider` / `fetchProvider` |
| DSH 设置页 | 接入 / 工具 / 引擎 / 密钥 / 研究 / 高级 六分区，改完即生效；密钥进宿主凭证库、明文不回显 | 设置弹窗 `Cmd+,` → 左侧「Argo」 |

### 预算模式

| 模式 | 适合 | 行为 |
|------|------|------|
| `fast` | 简单问题、要速度 | 免费引擎优先，跳过付费精排 |
| `auto` | 默认日常 | 成本感知，质量与花费折中 |
| `deep` | 调研、综述 | 质量优先，可多用引擎 |
| `budget` | 额度紧 | 配额控制，用完降级 |

### 当前大致能力（v2.9.7）

Argo 干的事，一句话能说完：把一个问题按领域和语言分给合适的源，取回结果后按可信度排个序，交回给 Agent 的是能排序、能复核的材料。搜索、抓取、核验、本机文件检索走同一条管线，19 个 MCP 工具和 CLI 命令一一对应，装哪种形态都不缺能力。另有几个单点命令随用随取：argo tweet 打包 X 帖子，argo auth 管登录态，argo job 聚合招聘信息。

装成 DSH 插件后，这些能力直接变成宿主的原生工具：高频的搜索与抓取默认就开，长尾取证能力在设置页里按需勾选，argo 本体的 28 个行为开关（缓存、重排、去重、守卫、代理、TTL 等）也从环境变量搬进了面板。密钥写进宿主凭证库，明文不回显，改完即生效。

最近几个版本各修了一类问题。

v2.9.7 修的是三个老毛病。DSH 宿主里的 AI 要读一个网址时，走的是宿主自带的抓取，短链跳转和 JS 挑战页经常直接失败，argo 的抓取链根本用不上；这版把宿主的读网址接到 argo 上，这类页面从失败变成成功，普通页面没有变化。路由候选池里原先混着 18 个「只能显式指定」的引擎，万一被自动选中，唯一的付费引擎就会悄悄扣费；如今候选池里没有它们，要用必须写明白。引擎每成功一次，熔断器都要加锁重写一次磁盘；健康状态下这版已经零文件开销，多个引擎的记账也合并成一笔事务。开源协议同时从 MIT 换成了 Apache-2.0，公司商用更放心。

这之后 DSH 插件又补了一层：设置页从五个分区扩到六个，「引擎」分区把 argo 本体的行为开关收进面板（原先只能改环境变量），密钥页能看出每个 key 来自凭证库、启动环境还是 .env，工具勾选、超时、并发、研究上限全部改完即生效。取消信号也贯通到了连接建立阶段——AI 中途喊停，正在拉起的 argo 子进程会被立刻杀掉，不再空等超时。

v2.9.6 做的是查询指令和传输层。搜「site:github.com 某某」这类查询，指令有时被当成普通词，有时解析了也不过滤；现在有统一的契约层，路由和缓存只认剥掉指令后的查询，site: 真正执行过滤并进缓存键，两次搜索不会串味。传输上，以前每次 POST 都重新付一次 TLS 握手，三百到五百毫秒；连接复用之后，常驻的 MCP 进程每笔查询都省这笔钱。这版还接入了官方 DeepSeek 搜索，按次计费，不进日常组合。

v2.9.5 补的是汇率和去重。问「人民币兑美元汇率」，查询会在宏观域空转一圈，最后给个百科词条，1.4 秒也没有答案；专属汇率域建起来后，675 毫秒直接给即期汇率和每日快讯。去重加了站后缀归一和模糊复核两层，标题带分隔符的官方文档不再被误杀到后排。

v2.9.4 修的是显式选引擎的场景。用 --engine X 指定引擎时，缓存有效期原先一刀切；补上域判定之后，缓存按域走，没有备选引擎时也不再同引擎空跑一次。

逐版本细节见「最近更新」，各版发布说明在 docs/。
---

## 引擎与路由

当前配置 **272** 个源（**235** 个免密钥开箱可用）、**97** 个业务域（以 `config.yaml` 与 `--list-engines` 为准）。

### 直连与垂类（节选）

| 引擎 | 场景 | 成本倾向 |
|------|------|----------|
| anysearch / duckduckgo | 通用 / 技术 | 免费 |
| sina_quote / tencent_quote / eastmoney | A 股行情 / 资金 | 免费 |
| finviz / seeking_alpha | 美股与海外金融 | 视配置 |
| imdb / itunes / thesportsdb | 影视 / 音乐 / 体育 | 免费为主 |
| local_openstreetmap / wikidata / wikipedia | 地理 / 组织 / 百科 | 免费 |
| arxiv / semantic_scholar / openalex | 学术 | 免费为主 |
| pubchem / gbif / rfc_editor | 化学 / 物种 / 标准 | 免费 |
| github / stackoverflow / pypi / npm | 代码与包 | 视配置 |
| byted / bocha / octen / yuanbao | 中文网页 / AI 搜索 | API / 低成本 |
| hkex / shfe / cfets / defillama / gleif | 港股公告 / 上期所 / 人民币中间价 / DeFi / 法人标识 | 免费 |
| zhihu / wechat_sogou | 中文观点 / 公众号 | API / 免费 |
| tavily / exa | 国际 / 语义 | 付费或额度 |
| stackexchange / doi / endoflife / nvd / flk_law | 问答官方 API / 论文元数据 / 生命周期 / 漏洞 / 法规原文 | 免费 |
| twitter / reddit / xiaohongshu / bilibili / weibo | 社交 UGC | 免费（部分需登录） |

### 本地零成本层（`local_*`）

不依赖独立的 SearXNG 服务。主路径用进程内 HTML / RSS / JSON 解析（如 `local_bing`、`local_sogou`、`local_google`、`local_arxiv` 等）。**多语言查询**时，路由会按语种动态改写引擎语言参数（例如 Bing `setlang`），并参与 RRF 融合。

### 登录态专业搜索（ego-search，默认关闭）

普通搜索拿不到知乎、小红书、微博、公众号等**需要登录**的内容，也常抓不回来 JS 渲染页 / 反爬页。ego-search 用**真实浏览器**去做这类搜索：继承登录态、抓登录墙后的正文、在已登录站点直接调接口取数据（如知乎搜索接口）。

**默认关闭**，需要时开启（在 argo 目录下运行）：

```bash
python3 sub-skills/ego-search/scripts/ego_search.py enable
```

常用命令：`python3 sub-skills/ego-search/scripts/ego_search.py status`（查看状态）、`... disable`（关闭）、`search` / `fetch` / `api`（分别对应浏览器搜索、抓正文、调站点接口）。

**依赖**（装好其中一个就能用，两个都装更好）：

| 依赖 | 官方项目 | 是什么 | 什么时候用 |
|------|----------|--------|-----------|
| **ego lite** | [lite.ego.app](https://lite.ego.app/) | 专门给 Agent 用的浏览器应用（仅 macOS），初始化后提供 `ego-browser` 命令 | 默认首选：独立空间，不抢你正在用的浏览器标签 |
| **WebBridge** | [Kimi WebBridge 官方帮助中心](https://www.kimi.com/zh-cn/help/kimi-webbridge/kimi-webbridge-introduction) | 浏览器扩展桥，复用 Chrome / Edge 里已登录的会话 | ego lite 没装，或想直接沿用日常登录态时 |

登录态搜到的结果**不写**公共搜索缓存（避免污染共享缓存），需要融合时用 `merge` 命令把常规结果和登录态结果放一起分析。

### 本机配置覆盖层（`config.local.yaml`）

`config.yaml` 是随 argo 一起发版的**公共配置**。本机状态（某个引擎账户欠费要临时停用、本机路径、本机调优）不该写进去——写了就会随升级推给所有用户。本机覆盖层解决这件事：复制示例文件，只写要改的键。

```bash
cp config.local.yaml.example config.local.yaml
```

```yaml
# 例：本机临时停用某引擎（路由自动改用别的源）
engines:
  parallel:
    enabled: false
    disabled_reason: "本机账户欠费，路由走 parallel_free；充值后删掉这段"
```

- **深度合并**：只写要改的键，不用整份抄引擎声明（`engines.parallel.enabled: false` 只翻一个布尔，其余字段原样保留）。
- **优先级最高**：`config.yaml` → `engines/*.yaml` 外置声明 → `config.local.yaml`。
- **改完立即生效**：进程内缓存与跨进程磁盘缓存都认它。
- **不进公开仓**：`config.local.yaml` 已在 `.gitignore` 里，不会被提交或推送。
- **损坏不影响使用**：文件写坏时静默忽略，退化为只用 `config.yaml`。
- **派生件不含本机状态**：`engine_registry.yaml` / `quota_profiles.json` 等随仓发布的派生文件按公共配置生成，本机跑 `sync_backends` 不会把本地状态写进公开仓。

不想用时删掉或改名即可，`config.yaml` 的行为完全不受影响。

---

## 使用示例

### 金融

```bash
python3 scripts/search.py "贵州茅台股价" --explain
# 典型：命中 stock_query → 行情快照源
```

### 学术

```bash
python3 scripts/search.py "transformer attention mechanism paper" --json
# domain 常为 academic，引擎组合含 arxiv 等
```

### 研究与核验

```bash
python3 scripts/research.py "2026 公募基金二季报 持仓结构" --depth deep --json

python3 scripts/search.py "同一查询" --json | \
  python3 scripts/evidence.py "同一查询" --stdin --json
```

### MCP 工具一览（19）

| 工具 | 用途 |
|------|------|
| `argo_search` | 统一搜索 |
| `argo_local_search` | 本地文件搜索（非联网） |
| `argo_local_read` | 白名单本地文本预览（fail-closed） |
| `argo_recompute` | 受限子进程可复算（默认拒绝，需授权） |
| `argo_research` | 深度研究（含 social-sentiment 模式） |
| `argo_evidence` | 可信度评估 |
| `argo_clarify` | 意图消歧 |
| `argo_fetch` | 智能抓取（`mode=extract` 结构化提取） |
| `argo_crawl` | 站点爬取 |
| `argo_screenshot` | 页面截图 |
| `argo_pdf` | PDF 提取 |
| `argo_social_search` | 多平台社交搜索（`mode=sentiment` 舆情聚合） |

---

## 安装与配置

### 环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.9+（命令行与 MCP 核心） |
| 依赖 | `pip install pyyaml`（仅此一个硬依赖） |
| 可选增强 | `pip install curl_cffi`（TLS 指纹伪造，MIT 许可）。装上后对指纹检测型反爬站（Cloudflare 等）免起浏览器即可抓取；缺失时自动降级，核心功能不受影响 |
| Node.js | **仅**在使用 `npx` 入口时需要 18+ |
| SearXNG | 不需要（内置本地引擎替代） |

### API Key（全部可选）

不配置则跳过对应引擎，免费引擎自动保底。**请用环境变量**，不要把真实 Key 写进仓库或贴到 Issue。

```bash
# 推荐（提升搜索质量）
export TAVILY_API_KEY="你的密钥"
export BOCHA_API_KEY="你的密钥"
export METASO_API_KEY="你的密钥"
export ZHIHU_ACCESS_SECRET="你的密钥"

# 可选
export BRAVE_API_KEY="你的密钥"
export FELO_API_KEY="你的密钥"
export GITHUB_TOKEN="你的密钥"
export WEB_SEARCH_API_KEY="你的密钥"
export ANYSEARCH_API_KEY="你的密钥"
export OCTEN_API_KEY="你的密钥"
export ARGO_KEENABLE_API_KEY="你的密钥"   # 可选；Keenable 免费体验期
```

`config.yaml` 里只写 `{ENV_NAME}` 占位，不会提交明文密钥。

### 缓存

默认 SQLite 路径见 `config.yaml` 的 `cache.db_path`（一般为 `~/.cache/unified-search/cache.db`）。

| 类型 | 大致 TTL |
|------|----------|
| 金融 | 约 5 分钟 |
| 新闻 / 实时 | 约 10–15 分钟 |
| 通用 | 约 1 小时 |
| 研究 / 常青 | 约 2–24 小时 |
| 空结果 | 很短（避免把失败固化） |

### 常见问题

**不配 API Key 能用吗？**  
能。内置大量本地零成本引擎和免费 API 源，不配 Key 时自动走免费路径。

**安装脚本和 npx 有什么区别？**  
安装脚本适合固定装在本机、改配置、挂 Skill；npx 适合快速把 MCP 挂进 Agent。两者底层同一套 Python 代码。

**如何确认引擎是否正常？**  
`python3 scripts/search.py --list-engines`，或加 `--explain`。

**会不会在仓库里复制多份代码？**  
不会。推荐「一份源文件 + 符号链接」。用 `link_source.py`，不要 rsync 多副本。

---

## CLI 常用参数

```
python3 scripts/search.py [选项] 查询词

  --engine, -e       引擎，默认 auto
  --max-results, -n  条数，默认 5
  --depth, -d        fast | balanced | deep
  --mode             fast | auto | deep | budget
  --no-cache         跳过缓存
  --explain          打印路由说明
  --json             JSON 输出
  --timeout, -t      超时秒数
  --list-engines     列出引擎
```

---

## 设计取舍

1. **先服务 Agent 吸收，再谈链接数量。**
2. **免费与本地优先，付费可选增强。**
3. **失败要可观测**：空结果、超时、熔断分开标，不静默吞掉。
4. **配置驱动扩引擎**，`config.yaml` 为唯一来源。
5. **唯一来源安装**：链接入口、不 rsync 多副本。
6. **不把社交当真理库**；社交内容适合扩维与舆情，不适合单独当真值。

---

## 适用场景

- Claude Code / Grok Build / Codex / Kimi 等 **Agent 的搜索后端**
- **多语言、多领域**日常问答：中英日韩等 + 金融 / 影视 / 体育 / 学术 / 代码
- 脚本与流水线里需要 **可复现、可缓存** 的检索
- 事实核查、金融公开信息、实体与公开资料的 **多源对照**

不太适合单独承担：平台内高级互动定榜、需要长期养服务的最大召回聚合器（已用内嵌本地引擎替代外挂 SearXNG 主路径）。

---

## 目录结构（简）

```
argo/
├── README.md                # 中文介绍（默认）
├── README.en.md             # English
├── README.ja.md             # 日本語
├── README.ko.md             # 한국어
├── README.es.md             # Español
├── SKILL.md
├── package.json             # npx 入口
├── bin/argo.js              # Node 启动 MCP
├── bin/argo                 # Python CLI
├── config.yaml              # 引擎与域配置（来源）
├── assets/readme/           # README 视觉资源
├── backends/
├── mcp/                     # 多客户端 MCP 注入配置（clients.yaml）
├── scripts/                 # search / research / mcp / install …
├── sub-skills/local-search/
├── sub-skills/ego-search/      # 登录态专业搜索（默认关闭，开启命令见正文）
├── tests/
└── docs/                    # 含 ENGINE_CATALOG.md（搜索源使用文档，生成）
```

---

## 最近更新

### 未发布（下一版）：元宝搜索 + 免 key 三源 + 结构化失败清单 + DSH 设置页「引擎」分区

**搜索内核**

- **腾讯元宝搜索接入（`yuanbao`）**：中文一手 / 官方口径源（实测「三星堆的由来」10 条里 8 条来自人民日报 / 新华网 / 国家文物局等），与 bocha / byted 的「门户 + 自媒体」构成互补；默认 2000 次 / 月按次额度。进中文通用域第 2 位做**权威源对冲**——当月 bocha / octen / byted 三个主力同时被排除时，同 6 个中文查询对拍 anysearch 中位 2664ms、日期覆盖 0%，yuanbao 中位 699ms、日期覆盖 96%。key 用 `ARGO_YUANBAO_API_KEY`（腾讯官方名 `TENCENTCLOUD_WSA_APIKEY` 也认）
- **免 key 通道扩三源**：`tavily_free`（官方 keyless 模式）、`keenable_free`（匿名端点）、`exa`（匿名回退）——不配任何 key 的开箱可用面再扩，前两个进通用兜底链
- **结构化失败清单（`failures`）**：失败不再只有一行给人看的文本，按来源和类别标出「可重试 / 换源 / 去配 key」和处置建议，Agent 能直接照着做；结果同时带 `meta.uncertainty` 综合可信度（low / medium / high）
- **输出信任边界**：网页正文自带的 `<untrusted-web-content>` 标记会被剥离，响应统一带 `content_trust: "untrusted"`，防网页内容冒充系统指令
- **新源五个**：港股公告（hkex）、上期所行情（shfe）、人民币中间价（cfets）、DeFiLlama、GLEIF 法人标识
- **本机配置覆盖层 `config.local.yaml`**：本机状态（临时停用某引擎、本机路径、调优）不再写进随版发布的公共 `config.yaml`——深度合并、改完即生效、不进公开仓、写坏静默忽略
- **文章元数据与正文链接**：`argo fetch --include-links`（MCP 同名参数 `include_links`）在抓正文时一并给出文章元数据与正文内链接

**DSH 插件**

- **设置页第六个分区「引擎」**：argo 本体的 28 个行为开关从环境变量搬进面板（缓存 / TF-IDF 重排 / 数值交叉校验 / MinHash 去重 / SERP 守卫、Jina / 移动端 UA / Parallel 抓取层、语义证据层、对冲宽限与尾宽、引擎启停名单、代理、本机检索根与读取白名单、预热 / 使用日志 / 连接池 / 各类 TTL）。经新 volatile 配置 `argoEnv`（一行一个 `KEY=VALUE`）随 argo 子进程 env 生效；名字走 `ARGO_ENV_SPECS` 白名单，白名单外 apply 期 loud fail，防拼写静默失效。开关类即时生效，数字 / 文本 / 名单类分组保存；未配置行显示 argo 默认态并标注「默认」。授权类开关（可复算执行、内网 URL）刻意不进面板
- **密钥页来源层可见**：显示「已配置 / 未配置 + 来源层（凭证库 / 启动环境 / 项目 .env / 家目录 .env）+ 只读态」，非 file 层提示保存后将覆盖；`DEEPSEEK_API_KEY` 标注与宿主 `web_search` 共用；`fetchMaxChars` 保存时截断到 argo 工具 schema 上限 50000，消除「显示值与实效不符」
- **取消信号贯通连接建立**：`acquireMcp` 在连接建立阶段认取消——abort 即杀子进程并以 `WEB_ABORTED` 收摊，不再空等超时；取消信号同时贯通单发兜底
- **修复**：证据去重不再吞大小写；旧宿主缺 `effect` 不再炸激活；`saveKey` / `setForward` / `toggleTool` 改读实时快照，修连续操作的竞态丢更新；`describe` 响应乱序防护，只认最新一次请求的响应

### v2.9.7：架构收口——DSH web_fetch 占位 + explicit_only 契约 + 状态态统一（License 转 Apache-2.0）

- **License 变更**：MIT → Apache License 2.0（专利授权明示、商用更安心；其余不变）
- **DSH 插件 web_fetch 占位**：宿主 web_fetch 此前作为「读这个 URL」的默认路径完全绕开 argo，现注册 fetch provider 走 argo_fetch 链（HTTP 优先，遇 Cloudflare / JS 渲染自动升级反检测浏览器）；与 search provider 同构的双路执行——常驻 MCP 池优先、传输层故障才回退 CLI 单发，工具级错误与超时不重发（那两类表示调用已跑完，重发只会双倍引擎调用与配额）；失败分五类（超时 / 被挡 / 空结果 / 通用 / 取消）各带可行动文案；新增配置 `fetchProviderEnabled` / `fetchProviderId` / `fetchTimeoutMs`（默认 25000）/ `fetchMaxChars`（默认 50000），默认全开、留逃生口；实测跨源跳转（短链、协议升级、跳转壳）与 JS 挑战页从宿主结构性失败变为 argo 成功，普通静态页质量不降
- **explicit_only 契约收口**：`config._routable_filter` 此前只过滤黑白名单 / 密钥 / 拉黑，不过滤 explicit_only，18 个显式专用引擎（含唯一 `cost_tier=paid` 的 deepseek_search）躺在 enabled 候选池里，TF-IDF 注入、catch-all、backfill、兜底等六条路径全能选中——此前没爆只因语料没词条，补一条 auto 档就会并行调起付费引擎扣费；现在候选池唯一生产者处过滤，`tests/test_explicit_only_gate.py` 锁死三契约（注入不带入 / 候选池排除 / 显式 `--engine` 照常单发）
- **状态态契约统一**：熔断器在健康 closed 态且计数为 0 时内存短路（零文件锁零重写磁盘），基于 `(st_mtime_ns, st_size)` 感知跨进程变更；adaptive 记账 `MAX(created_at)` 合入单条聚合 SQL，新增 `batch()` 上下文管理器把多引擎记账并为单次事务；配额耗尽记录生效凭证指纹、换新 key 自动解锁；route 缓存遇 combo 引擎耗尽或旧耗尽引擎恢复时自动失效重算；`is_engine_routable` 单一准入谓词收口 backfill / tfidf / breaker_filter 的五层过滤
- **调度与传输**：auto / deep 档也剔除配额硬耗尽引擎（fail-open 兜底）；对冲等待窗收窄、早停判据放宽（Wave-1 跨引擎累计达标即停，不启 Wave-2）；POST 连接池打通（anysearch 省 ~320ms / octen 省 ~561ms 每次）+ MCP 预连接；天气域补 `early_stop_min_results: 1`
- **子技能热路径减法**：js-run 用 MiniRacer 原生 timeout 替 SIGALRM，根治 crawl / research / mcp 工作线程调用必抛 `ValueError: signal only works in main thread` 的崩溃；local-seek 重排免每次 O(N) 读盘与 JSON 解析；local-search 复用 registry 免双份 YAML 解析；ego-search auto 下按需短路探测
- **验证**：插件单测 71 passed；argo 全量回归 4264 passed / 28 skipped；pre-commit 七道 123 passed；fetch 链对普通页不回归、跨源跳转与 JS 挑战由失败转成功

### v2.9.6：DeepSeek Search 接入 + 查询操作符契约 + 传输层去重付费 + 路由快照门

- 新引擎 `deepseek_search`（官方 `api.deepseek.com/v1/tools/search`）默认启用：无 `DEEPSEEK_API_KEY` 时路由自动跳过、其余 265 源不受影响；实测延迟 445-510ms（anysearch 1.7-4.5s / exa 3.7s），authority 权威分级 / rerank_score / 发布时间为三引擎中唯一全覆盖，ja/ko/es 多语言与 anysearch 持平；按次计费，不进域 combo，显式 `--engine deepseek_search` 为主路径；DSH 宿主经原生凭证 seam 与官方后端共用同一把 key（web Models 页轮换后下一跳生效，不落盘不打日志）
- 修复 `--since/--until` 对 deepseek_search 静默无效（入 TIME_CAPABLE_ENGINES）
- 新增 `query_operators.py` 查询操作符契约层：`site:` / `-site:` / `-词` / `-"短语"` / `lang:` / `after:` / `before:` 从五种散落形态收敛为结构化 operators；路由、缓存、查询理解只认剥掉指令后的 clean_query；`site:` / `-site:` 真正后置过滤执行（子域匹配、多站点 OR，过滤数进 `site_filtered`），操作符并入结果缓存键避免互串
- `evidence.py`：新增 Agent 档双层摘要 `summary` 字段（借鉴 DeepSeek Search 摘要语义）
- 传输层去重付费：POST 走连接池复用（实测同连接第二次请求省 320ms（anysearch）/ 561ms（octen）），含失效重借与响应体读干才还池；MCP 预连接；配额耗尽与死负缓存收口
- 路由：octen 进通用兜底链第二位与 TF-IDF 对冲位（anysearch 抖动窗口 p90 3273→1614ms、max 6266→1928ms、错误 9→0；健康窗口中位无差，定位为尾部保险），`ARGO_GENERAL_FALLBACK_LEGACY=1` 逃生开关退回旧序
- 修复 RRF 口径隔离名次衰减：同引擎所有结果同分（实测 anysearch 5 条均 0.017213），输出退化为按引擎权重整段拼接；新增测试锁「同引擎内分数严格递减」
- 修复 Bing ck/a 跳转壳不还原导致聚合层整批滤掉结果（近 7 天 40.2% 空结果）：离线 base64url 解码还原真链，零网络
- 修复 TF-IDF 领队组合拼出 `['anysearch','anysearch']` 并发跑两遍（双倍配额且 wasted_ms 记 0）：200 条真实查询重放，重复 combo 1→0
- 搜索改进：失败负缓存、Nitter 故障转移、口径隔离、X Article 提取、查询词回声守卫（早停拒收 + 恢复链换引擎）
- 工程化：新增 `scripts/pre-commit` 快门禁（static_lint / module_size_gate / usage_doc / consistency / routing_snapshot / context_budget + engine_catalog，实测 ~12s）；路由决策快照门把路由翻转变成可 diff 的 golden（三处标注集并集 115 条，只比对 domain 与 kind 不被环境噪声假红）；口径注册表同步测试锁「表里的引擎名必须真实注册」
- DSH 插件适配 DSH 0.2.1-rc.2：运行时入口双栈（`startActivation({provider, label, request, signal, delivery})` 新 / `start(provider, request)` 旧），rc.2 移除 `toolFilter` 后由插件内 tool guard 阻止 worker 嵌套调用 `wide_research`；rc.2 上 `wide_research`（planner → 2 worker → synthesis，passed=true / 14 sources）与原生 `argo_search`（count=3）端到端实测通过；0.2.1-alpha.1 兼容分支由单测覆盖；插件单测 46→50
- DSH 环境版本：**DSH 0.2.1-rc.2（当前运行中，端到端实测）+ DSH 0.2.1-alpha.1（兼容，start 旧分支单测覆盖）**；对照表见 `packages/dsh-plugin/README.md` 的 Compatibility 小节

### v2.9.5：汇率查询专域 + 去重双轨 + 排序误杀修复 + daemon 多检出隔离

- `config.yaml`：新增 `fx_query` 域——「人民币/美元 汇率、中间价、离岸」类查询不再落进宏观域空转后兜底百科词条，改为即期汇率 + 每日中间价快讯（实测 675ms，改前 1411ms 且答非所问）
- `search_rank.py`：去重补两层判据——标题站后缀归一（零依赖）+ rapidfuzz 模糊近重复复核（仅近似命中带内启用；`ARGO_DEDUP_FUZZY=0` 关闭，未安装则自动回退纯 minhash）
- 修复：精排降级时的标题分隔符误杀——含 `|` / `_` / `——` 的标题一律 ×0.6，官方文档被压 40%；无 Bocha Key 的用户每条 auto/deep 查询都在受益（判据收敛到 rank_signals 单一实现）
- `query_understanding.py`：否定理解补「不是X」（疑问句式「是不是」不误判为否定）
- `daemon.py`：socket/pid/指针等落盘名字按检出目录隔离——多 worktree/clone 互抢 daemon、互杀进程、「改了不生效」三类故障根除
- 新增可选依赖 rapidfuzz（`pip install rapidfuzz`；install.sh 自动安装，缺失不影响核心功能）

### v2.9.4：显式引擎域归因 + 恢复链止损 + 门禁同步

- `route.py`：显式 `--engine X` 时补 `match_domains` 域判定，修复缓存 TTL 一刀切 general
- `recovery.py`：显式单引擎无备选时跳过 L1 同引擎空跑，减少无意义 RTT
- `config.yaml`：`org_entity` 加 unless 股东尽调词；`fund_query` 加 unless 政策法规词
- `mcp_launch.sh`：`set -a` 收窄到 `. "$ENV_FILE"` 单行
- `sub-skills/local-search/`：引擎注册表层收口与 search_v3 质量提升
- 门禁同步：module_size_gate / ENGINE_CATALOG / domain_profiles.json 基准对齐

### v2.9.3：X 帖子完整打包 + 浏览器登录态车道 + 本地链质速双修

- **新增**：`argo tweet`——一条命令打包 X 帖子正文、串/引用/转发与互动数据；默认纯文本不下载媒体，`--out` 落四件套（post.md/raw.json/manifest.json/CHECKLIST.md），`--media` 按需下载图片/视频；主帖失败原因随产物可见不静默
- **新增**：`argo auth` 浏览器登录态车道——`login/status/logout` 管理站点持久浏览器 profile，扫码一次即可抓取需登录页面；cookie 只存 Chrome 自身加密存储、argo 不读取不导出，登录态结果标记 `login_state_used` 并拒绝入公共缓存（`ARGO_AUTH_FETCH` 开启）
- **更准**：本地中文链搜狗/百度跳转壳无会话解析成真实直链（保留结果 1→5 条）；意图门误锁修复（「教程」类查询不再被锁死单引擎）；火车票表格行身份 URL 治漏斗压缩（候补 10→1 修为如实 10→10）
- **更快**：共识宽限自适应（首引擎交足即放行，英文分发 ~3.0s→2.2-2.5s）；本地长尾够数早停；本地图片指纹 mmap 矩阵点积（77k 张 158ms→3.9ms，默认关 `ARGO_LOCAL_IMAGE=1`）；agent 消费自动瘦身 + markdown 内容协商，MCP 每调用固定开销 −32%
- **更多源**：43 个无域引用引擎接入对应领域；route_lang 语言路由；3 个零 key 金融源；`--academic-deep` 一键学术多源深挖；火车票中转+经停查询
- **更稳**：js-run 车道接入 fetch 链第一级（重试带 Chrome 指纹）；jsrun Session 泄漏与退避预算修复；超时收紧（redskill 60→15s）与声明策略三分组收口

### v2.9.2：DSH 0.2.1-alpha.1 适配验证 + 路由与守卫一批修复 + js-run 子技能

- **更兼容**：DSH 插件已在最新版 DSH 0.2.1-alpha.1 实测启用，原生一等工具 / web_search seam / wide_research 三形态照常工作；`argo mcp inject` 新增 WorkBuddy，一键注入覆盖到第 7 宿主
- **更准**：TF-IDF 弱证据辅源化（低分语义推荐不再抢占主路由）；死源地板 + 熔断槽位回填；配额耗尽引擎与主路由 / 恢复链隔离；serp_guard 修复网盘分享链连坐误杀、主流门户权威分归位
- **更快**：engines / evidence 全栈惰性导入（默认路径 import 量 −50%）；准入存在集合短路（open 次数 261 → 99）
- **更稳**：MCP 入口守卫与数值参数守卫收口（null arguments、TOML 多 env 键、timeout / max_chars 共 11 处裸 `int()` 换类型守卫）；local-seek 四类假阴性收口（v1.4.0）
- **新增**：`sub-skills/js-run` 子技能（v0 骨架）——不开浏览器跑「环境探测 + 纯计算」型网页 JS，单次上下文 P50 ≈ 1ms

### v2.9.1：内容质量优化 + 对抗内容农场 + 适配最新版本

- **更干净**：优化了内容质量评估，提升了对抗内容农场的能力——搜索结果里低质、批量生成的内容会被更有效地识别和过滤
- **更兼容**：适配了最新版本，确保与当前环境无缝协作
- **更稳定**：本地搜索新增自身安装树守卫，避免搜索结果被自身源码污染

### v2.9.0：搜索源优化 + 插件与 CLI 持平 + 多语言小语种

- **更全**：搜索源 237 → 253（免配置 198 → 219），新增 14 个小语种本地新闻源、CORE 开放获取全文源、TinEye 反搜图、Bing RSS 稳定出口等；百度与搜狗两个常青源修活
- **更对齐**：CLI 18 个命令与 MCP 19 个工具一一对应，插件与 CLI 搜索能力首次完全持平
- **更多语言**：新增 14 个小语种源（泰/阿拉伯/希伯来/希腊/印地/越南/土耳其/印尼等），按查询语言自动配源
- **更快**：导入链 −79%，重排序 n=200 场景 33ms→1.5ms，缓存命中率从六成到基本不 miss
- **更可信**：配额写路径跨进程安全修复，早停结果不再误标超时，`argo stats` 让搜索质量有了自己的账本

### v2.8.9：输出减重 + 检索更全更快 + 外媒与核查源 5 个

- **更省**：默认输出 −66%（同一段结果不再重复写三遍）；重复查询 −30%（路由决策缓存）；慢网轮等待 −36%（主源卡过 0.8 秒自动补发备选源）
- **更全**：召回 +35%、抓取时延 −30%；正文结构保真 0/6 → 6/6（标题、列表、表格不再被压平）；中文内容不再被系统性判为低质
- **新增**：搜索源 235 → 237（免配置开箱 194 → 198，全部免密钥——卫报、France 24、德国之声，声明核查 FactCheck.org / Full Fact 美英两口径）；死源 gdelt 下线
- **更可信**：六处「数字互相矛盾」的记账缺陷修复；六格漏斗让「搜到 0 条」能定位塌在哪一层；离线重跑对比工具让改动效果当天可验证；详见 [发布说明](docs/RELEASE_NOTES_v2.8.9.md)

### v2.8.8：真实用户问题修复 + 全面提速 + 搜索源 235 个

- **修复**：按推荐名配密钥后引擎静默失效（#12）；抓取链不走代理，GitHub 等站点必然失败（#13）——现在 `ARGO_PROXY`、config 按域规则、标准代理环境变量都生效，`NO_PROXY` 尊重
- **提速**：命令冷启动 2.1s → 0.55s；配置跨进程缓存 50–82ms → 16–18ms；每次搜索自带各阶段耗时与预算账单，慢在哪不用猜（`--no-timing` 可关）
- **新增**：搜索源 218 → 235（免配置开箱 184 → 194，全部免密钥：国内热榜、安全漏洞、学术开放获取、技能目录、Agent 搜索）、`argo answer` 直答、`argo watch` 网页观察、CLI 与 MCP 工具面对齐
- **更稳**：三平台惯例路径（新增 `argo paths` 自省）、支持 Python 3.9、静默故障如实记账；详见 [发布说明](docs/RELEASE_NOTES_v2.8.8.md)

### v2.8.7：数据源扩充到 218 个 + 一批修复

- **数据源扩充**：168 → 218 个源、72 → 89 个领域（新增 StackExchange 问答、DOI 论文元数据、漏洞情报、产品生命周期等官方源），抓取链新增三条拿正文直出通道
- **一批修复**：多引擎路由、零结果自动换源、中文重定向、本地搜索降级等；详见 [发布说明](docs/RELEASE_NOTES_v2.8.7.md)

### v2.8.6：检索提速 + 多源分工

- 引擎竞速、知乎三源分工、多语言与学术分发放宽、死源显形检查

### v2.8.5：DSH 插件工具原生化 + MCP 默认关闭 + Windows 兼容

- **DSH 插件工具原生化**：`argo_search` / `argo_fetch` 以原生一等工具注册，默认可用，不依赖 MCP 连接；schema 从 `mcp_tools.py` 唯一来源自动生成，两侧零漂移；除 `argo_research` 外 13 个工具都可经 `nativeTools` 按需启用
- **MCP 默认关闭**：DSH 三形态接入（MCP 按需挂载 / 原生工具默认入口 / web_search seam），平时零常驻 token 开销，要完整 19 工具面时一条 profile patch 打开
- **Windows 全平台兼容**（社区贡献 PR #11）：临时路径走系统 temp、GBK 编码修复、`python3`/`python` 运行时解析、symlink 无权限自动退化 junction、新增 PowerShell 一键安装 `install.ps1`
- **配额自愈完整链路**：远端配额耗尽（HTTP 200 藏错误）自动识别、路由排除该引擎切备用源，周期结束自动回归，无需人工改配置
- **抓取全局 deadline**：`ARGO_FETCH_DEADLINE_S`（默认 60s）封顶降级链总耗时；429/503 停止信号尊重服务器指示；tinyfish 免费渲染层 + `.md` 变体探测命中即跳过反爬链

### v2.8.4：本地数据融合 + 多客户端 MCP 一键接入

- **深度研究能吃你本地的数据了**：以前 `argo research` 只吃网页，现在工作包能带 `file_inputs`（你的一手 CSV / XLSX / 文献，登记哈希、内容不入账）+ `recompute`（可复算执行器，安全地重算数字并和检索对账，对不上就提示）
- **挂 MCP 不再手改配置**：`argo mcp inject` 一条命令把 argo 注入 Claude Code / Cursor / Windsurf / Codex / OpenCode / Cline（原子写 + 自动备份 + 可还原）
- **简单问题不被拖成多轮**：查询归一化（全角→半角、版本号拆斜杠）+ 复杂度门控（低复杂度查询不放行高价多源）+ 社交/平台检索语法优先 + 丢了一个中文引擎会继续看备选
- **多接一个免费搜索源 Keenable**（免费体验期、量较大，到期出问题直接停用即可）
- **安全加固**：recompute 封死外部进程出网、主机路径全部改为安装感知（不再写死 `~/.agents` 这类）、修了一处会把用户引向陈旧 npm 包的安装提示

> 完整变更见下表与各版[发布说明](docs/)。

---

## 版本记录

| 版本 | 说明 |
|------|------|
| **v2.9.7** | **架构收口 + DSH web_fetch 占位 + License 转 Apache-2.0**：MIT → Apache License 2.0；DSH 宿主 web_fetch 占位走 argo_fetch 链（HTTP 优先、JS 挑战升级浏览器，双路执行、错误不重发、失败五分类）；18 个 explicit_only 引擎从路由候选池剔除（堵住 auto 档误调付费引擎的扣费口子）；熔断健康短路、adaptive 单事务记账、配额换 key 自动解锁、route 缓存耗尽失效；auto/deep 剔除硬耗尽引擎 + 早停放宽 + POST 连接池打通；js-run 修非主线程崩溃。 |
| **v2.9.6** | **DeepSeek Search 接入 + 查询操作符契约 + 传输层去重付费 + 路由快照门**：新引擎 `deepseek_search` 默认启用（无 key 自动跳过；445-510ms，authority/rerank_score/发布时间唯一全覆盖，时间窗真生效；DSH 经原生凭证 seam 共用 key）；`site:`/`-site:`/`-词`/`lang:`/`after:`/`before:` 收敛为操作符契约层并真正后置过滤 + 入缓存键；POST 连接池复用（省 320-561ms/次）+ MCP 预连接；octen 进兜底与对冲位（p90 3273→1614ms，`ARGO_GENERAL_FALLBACK_LEGACY=1` 逃生）；修复 RRF 名次衰减与 Bing 跳转壳（40.2% 空结果）；新增 pre-commit 快门禁与路由决策快照门；DSH 插件适配 0.2.1-rc.2 双栈 + alpha.1 兼容单测。 |
| **v2.9.5** | **汇率查询专域 + 去重双轨 + 排序误杀修复 + daemon 多检出隔离**：新增 `fx_query` 域（汇率/中间价 675ms 出即期+快讯，改前百科词条）；去重补站后缀归一（零依赖）+ rapidfuzz 模糊复核（可选、`ARGO_DEDUP_FUZZY` 可控、缺失回退）；修复标题分隔符 ×0.6 误杀（官方文档回前排）；否定补「不是X」；daemon 落盘名字按检出目录隔离。 |
| **v2.9.4** | **显式引擎域归因 + 恢复链止损 + 门禁同步**：`--engine X` 补 `match_domains` 域判定修复缓存 TTL 一刀切；单引擎无备选跳过 L1 空跑；`config.yaml` 域规则增强（org_entity/fund_query unless 词）；`mcp_launch.sh` 环境变量导出收窄；local-search 引擎注册表层收口与质量提升；门禁同步。 |
| **v2.9.3** | **X 帖子完整打包 + 浏览器登录态车道 + 本地链质速双修**：新增 `argo tweet`（正文/串/引用/转发/媒体按需打包，`--out` 四件套）；新增 `argo auth` 浏览器登录态车道（站点持久 profile，cookie 只存 Chrome 加密存储，登录态结果不入公共缓存）；本地中文链搜狗/百度跳转壳无会话解析（保留 1→5 条）+ 共识宽限自适应（英文分发 ~3.0s→2.2-2.5s）；js-run 接入 fetch 链第一级（Chrome 指纹重试）；火车票中转+经停（漏斗 10→1 修为如实 10→10）；`--academic-deep` 一键学术深挖；43 引擎领域接线 + 3 零 key 金融源 + 意图门误锁修复；本地图片指纹 158ms→3.9ms；agent 消费瘦身（MCP 固定开销 −32%）。 |
| **v2.9.2** | **DSH 0.2.1-alpha.1 适配验证 + 路由/守卫一批修复 + js-run 子技能**：DSH 插件三形态在最新版 DSH 0.2.1-alpha.1 实测启用；`argo mcp inject` 补 WorkBuddy 覆盖到第 7 宿主；TF-IDF 弱证据辅源化、死源地板 + 熔断槽位回填、配额耗尽引擎路由隔离、serp_guard 连坐误杀修复；engines/evidence 惰性导入（import −50%）与准入存在集合短路（open 261→99）；MCP 入口与数值参数守卫收口；新增 js-run 子技能（无浏览器跑网页 JS，P50 ≈1ms）。 |
| **v2.9.1** | **内容质量优化 + 对抗内容农场 + 适配最新版本**：优化内容质量评估，提升对低质批量生成内容的识别与过滤能力；适配最新版本确保无缝协作；本地搜索新增自身安装树守卫，避免结果被自身源码污染。 |
| **v2.9.0** | **搜索源优化 + 插件与 CLI 持平 + 多语言小语种**：搜索源 237→253（免配置 198→219），新增 14 个小语种新闻源、CORE 全文源、TinEye 反搜图、Bing RSS 等；百度与搜狗修活；CLI 18 命令与 MCP 19 工具一一对应；导入链 −79%、重排序 33ms→1.5ms、缓存命中率大幅提升；配额写路径跨进程安全修复；新增 `argo stats` 本地使用日志。详见 [发布说明](docs/RELEASE_NOTES_v2.9.0.md) |
| **v2.8.9** | **输出减重 + 检索更全更快 + 5 个外媒与核查源**：默认输出 15.5KB→5.2KB（−66%，同一份结果不再写三遍，`--envelope` 可开完整版）；路由决策缓存让重复查询 −30%；慢网轮 dispatch −36%（串行域主源超 0.8s 自动补发备选源）；取数链路五轮优化（召回 +35%、抓取时延 −30%、长尾 P90 −8%）+ 正文结构还原（标题/列表/表格保真 0/6→6/6）+ 中文质量分偏差修复；新增卫报 / France 24 / 德国之声 / FactCheck.org / Full Fact 五个免密钥源（235→237、开箱 194→198、域 90→92），gdelt 死源下线；六处「看起来对、量起来错」的自洽缺陷修复 + 六格漏斗归因 + 离线重跑对比工具（`scripts/replay_eval.py`）+ 部署形态门禁与场景阈值契约。详见 [发布说明](docs/RELEASE_NOTES_v2.8.9.md) |
| **v2.8.8** | **真实用户报障修复（#12 密钥别名静默失效、#13 抓取链不走代理）+ 全面提速 + 搜索源 218 → 235**：统一出口调度（`ARGO_PROXY` / 按域规则 / 标准代理变量，全程尊重 `NO_PROXY`）；16 处密钥读取统一走别名链；命令冷启动 2.1s→0.55s、配置跨进程缓存 50–82ms→16–18ms、QPP 平坦分早停、`--list-engines --detail` 瘦身 152KB→51KB；新增直答 `argo answer` 与网页观察 `argo watch`，14 个免密钥源（国内热榜与生活 / 安全漏洞 / 学术开放获取 / 技能目录 / Agent 搜索），69 引擎补归类（`web_general` 兜底 41%→20%，新增 security 领域）；三平台惯例路径（`argo paths` 自省）+ Python 3.9 + 有界并发让超时真正生效；search.py 拆模块 3351→2526 行、相关性回归金标 22 引擎、静态缺陷与输出契约门禁。详见 [发布说明](docs/RELEASE_NOTES_v2.8.8.md) |
| **v2.8.7** | **218 源 / 89 域 + 取信技巧三通道 + 路由触发纪律 + macro 零结果修复**：批次七/八/九累计 50 个新源（法条/标准/安全情报/学术/新闻/文娱/能源交通/法律政务），stackexchange 与 doi 引擎；抓取链第零级 llms.txt 与 `.md` 直出探测、新增 r.jina.ai 阅读器级；`--engine` 逗号多引擎修复、tfidf 计算方式与 route_reason、负向路由控制矩阵、排序金标与融合增益消融检查；中国宏观查询国家统计局前置、全域零结果恢复链放行 L3、救援引擎如实记账。详见 [发布说明](docs/RELEASE_NOTES_v2.8.7.md) |
| **v2.8.6** | **hedged 竞速 + 知乎三源分工 + 声明式语言分发 + 可达性门 + 学术检索协议**：首引擎宽限窗竞速（快引擎只付 1 次调用）、zhihu 全网搜/个人数据接入与防饿死、子查询语言/学术分发（英文源与 17 学术源接入研究采集）、引擎语言元数据与可达性检查（死源显形）、geo 尾链 −56%、学术检索查询构造协议。详见 [发布说明](docs/RELEASE_NOTES_v2.8.6.md) |
| **v2.8.5** | **DSH 插件工具原生化 + MCP 默认关闭 + Windows 兼容 + 配额自愈 + 抓取 deadline**：`argo_search`/`argo_fetch` 原生一等工具默认可用（CLI 单发与 MCP 同引擎同守卫，schema 唯一来源生成 + 漂移检查）；DSH 三形态接入、MCP 按需挂载默认关；Windows 全平台兼容（临时路径 / GBK / 解释器解析 / junction / `install.ps1`，PR #11）；配额自愈完整链路（200 业务错误封套识别 + 路由排除 + 周期自愈）；抓取降级链全局 deadline（`ARGO_FETCH_DEADLINE_S`）+ tinyfish 渲染层 + `.md` 变体探测；密钥热读与状态目录唯一来源。详见 [发布说明](docs/RELEASE_NOTES_v2.8.5.md) |
| **v2.8.4** | **本地数据融合 + 多客户端 MCP 接入 + 结构化搜索增强 + Keenable**：深度研究 L1 本地一手数据入账（`file_inputs` 白名单 + `recompute` 可复算执行器 + `local_sources`，`no_primary_sources` 计入本地一手）；`argo mcp inject` 多客户端 MCP 一键注入/诊断/还原（`mcp/clients.yaml` 声明式来源）；结构化搜索增强（查询归一化 + 检索变体 + 复杂度门控 + social 域优先 + TF-IDF 检索修复 + `--include-local`）；接入 Keenable 通用网页搜索（L1 声明式 HTTP，免费体验期）；安全加固（recompute 封死 `subprocess`/`os.system` 出网通道 + 主机路径单来源化）。详见 [发布说明](docs/RELEASE_NOTES_v2.8.4.md) |
| **v2.8.3** | **多语言路由修复 + anysearch 进程化 + weighted RRF**：anysearch 从 subprocess 改为进程内 builder（省 python 启动开销 + `HttpClient.post` UA 轮换/重试/退避）；weighted RRF 新增动态可靠性因子（weakest-link 弱源降权，论文 2508.01405）；多语言路由修复——ja/ko 查询返回目标语言（韩语/日语），欧语言（德法西意）走 anysearch 返回目标语言，中文内容/金融/技术引擎双层过滤（域命中 + TF-IDF），Bing `mkt` 市场码 + 语言偏好软排序。详见 [发布说明](docs/RELEASE_NOTES_v2.8.3.md) |
| **v2.8.2** | **Windows 全平台 + 证据语义统一**：移除 npm `os` 限制；全链路 UTF-8 防线（`PYTHONUTF8` + `-X utf8` + JSON `read_bytes`）根治 GBK 崩溃；工具探测改 `shutil.which`；Chrome/Edge 自动发现；Ctrl+C 干净退出。主包新增 `dsh.bundle` 声明（`dsh plugin add github:taxueseek/argo` 即得 MCP 工具）；npm 包补 `engines/`、`data/`。`wide_research` 输出新增 `quality_gate_results` 检查 + `depends_on` 分阶段 + SSRF 防线 + 研究递归硬保护；深度研究协议化（机器产 dossier、Agent 写判断稿，`--work-packages` 分阶段取证）。详见 [发布说明](docs/RELEASE_NOTES_v2.8.2.md) |
| **v2.8.0** | **证据完整链路 + 求职 v3 + 天气双源**：搜索输出自带证据门控（高后果问题标 `fetch_required`、每条结果标 `fetch_suggested`、`--verify` 一键核验回填「核实后证据分」、核实过的链接自动记住下次搜索直接显示已核实）；`argo job` 求职搜索 v3（结构化字段 + 增量监控 + 指纹去重 + Ashby ATS / 北京高校源）；天气双源并行（wttr.in + Open-Meteo，地理编码 + 空气质量）；新增 Parallel / You.com 通用引擎；health_check 崩溃修复 + 日韩股票查询错配修复。详见 [发布说明](docs/RELEASE_NOTES_v2.8.0.md) |
| **v2.7.3** | **本轮修复 + 引擎激活**：引擎层 HttpClient 接入（UA 轮换 / 重试 / 重定向跟随，arxiv 从 5s 超时空返回变为 2s 内 10 条有效结果）；TF-IDF 强语义注入激活 25 个垂直引擎（marginalia / open_meteo / usda / gov_policy / cnii 等，此前有 profile 但永远选不中）；env 占位缺失过滤（github 无 token 从 401 恢复匿名 API）；70 域 TTL 全覆盖（金价/快讯/行情缓存从 1 小时缩短到 5-15 分钟）；垂直源中英双语覆盖（worldbank / eurostat 英文国家与指标名，实测 China GDP / US inflation / Japan population 全部命中）；快讯类引擎触发词放行（「快讯」不再被当关键词滤空）；百科条目页直接命中保底（moegirl 等搜索跳转条目页不再空结果）；熔断 empty 语义修复（查询无结果不误判引擎故障）；国际引擎中文查询 URL 编码修复（18 处）；唯一来源文档修正（engines/specs/ 外置目录）。详见 [发布说明](docs/RELEASE_NOTES_v2.7.3.md) |
| **v2.7.2** | **登录态专业搜索**：新增 ego-search 子技能（默认关闭，开启方法与依赖见上「登录态专业搜索」节）；搜索保底 / 多意图路由 / 统一健康视图；日韩文查询不再混入中文引擎、显式语言指定生效；MCP 服务拆三模块；具备安全防护（登录态结果与公共缓存隔离、URL 安全检查）。详见 [发布说明](docs/RELEASE_NOTES_v2.7.2.md) |
| **v2.7.1** | **安全加固 + 路由修复**：SSRF 防护（URL 白名单 + IP 段检查）；路由健康状态语义漂移根因修复（只对 `local_*` 做健康判定）；深度研究 local_first 浪费修复；配置清理（唯一来源）。详见 [发布说明](docs/RELEASE_NOTES_v2.7.1.md) |
| **v2.7.0** | **垂直结构化模态卡**：内建 `bocha` / `bocha_ai` 原生引擎，`modal_card` 域统一识别火车票 / 油价 / 贵金属 / 万年历 / 星座 / 手机 / 汽车 / 挂号等实时卡片；`bocha` web 解析缺陷修复。详见 [发布说明](docs/RELEASE_NOTES_v2.7.0.md) |
| **v2.6.2** | 合并独立改进线：网络环境感知 / 加权 RRF + 语义缓存 / 自适应引擎禁用 / 内容安全 + 查询变体 / 三大垂直引擎 / 日韩域路由补全；含 v2.6.1 路由修复。详见 [发布说明](docs/RELEASE_NOTES_v2.6.2.md) |
| **v2.6.1** | v2.6.0 修复版：路由误伤修复（`capital of` 不再抢 fact_check）；版本同步。详见 [发布说明](docs/RELEASE_NOTES_v2.6.1.md) |
| **v2.6.0** | **多语言搜索**（检测 / 引擎参数 / 跨语言回退）；影视·体育·地理·组织·媒体等垂直补全；recovery 防污染；能力族与矩阵回归；约 120+ 源。详见 [发布说明](docs/RELEASE_NOTES_v2.6.0.md) |
| **v2.5.1** | 金融/宏观/化学等垂直答案源加厚；引擎分层 + combo 预算；[v2.5.1 说明](docs/RELEASE_NOTES_v2.5.1.md) |
| **v2.5.0** | 安装脚本 + npx；查询改写与路由拆开；路由热路径缓存；MCP 紧凑响应 |
| **v2.4.0** | 路由低分回退与社交误吸过滤；缓存 depth / 柔性命中；熔断与负缓存；`engine_outcomes` |
| **v2.2–v2.3** | 证据两阶段、中文信源表、content_signals、fetch 栈、引擎扩充 |
| **v2.1** | 社交引擎层（多平台 UGC） |
| **v1.x** | 统一命名为 Argo，多引擎路由与双层缓存成型 |

更细说明见 `docs/RELEASE_NOTES_v2.7.0.md` 与 `docs/OPTIMIZATION_ROADMAP_v2.4.md`。

---

## 贡献

欢迎提 Issue 与 Pull Request。改路由或证据逻辑时，请尽量补对应测试：

```bash
python3 -m pytest tests/test_unit.py tests/test_multilingual.py -q
python3 scripts/regression_p0p1.py --offline
python3 scripts/matrix_search_eval.py --offline
python3 scripts/ab_eval_p0p1.py   # 可选，含在线实测
```

提交前请确认：不含真实 API Key、本机绝对路径、账号 cookie 等敏感信息。本机 Skill 路径请写在 `installs.local.yaml`（已忽略）。

## License

Apache License 2.0 © 2026 [taxueseek](https://github.com/taxueseek)

<p align="center">
  <a href="https://github.com/oil-oil/beautify-github-readme"><img src="assets/readme/made-with-beautify.svg" width="300" alt="README made with beautify-github-readme"></a>
</p>

---

> 好的搜索不是让你看得更多，是让你更敢下结论——以及知道什么时候还不该下结论。

---

## 生态联动：与 Invest 系列投资技能集成

本引擎的财经垂直源（`eastmoney`、`nbs_stats`、`jin10`、`nbs`、`fred`、`eurostat`、`finviz` 等）已接入 [invest 系列投资技能](https://github.com/taxueseek/taxue-invest)。

invest-cli 通过 `info`（`invest-cli info <词> --engine eastmoney`）与 `intent macro` 直接复用 argo 的财经 / 宏观 / 资讯取数，用于环节配额、低成本、多源数据，与 invest-cli 的结构化数据层（Wind / 盈米 / 东财 / yfinance / 天天基金）协同。

> 最新版已完成 argo 数据与 invest 系列技能（v2.0.5）的集成。
