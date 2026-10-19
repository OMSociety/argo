# argo-dsh

DeepSeek Harness 插件：一行同时挂上 [Argo](https://github.com/taxueseek/argo) 搜索 MCP 和 `wide_research` 并行研究编排。

## 安装

```bash
dsh plugin --profile web add "github:taxueseek/argo#main&path:packages/dsh-plugin"
```

重启 `dsh web` 后生效。本 bundle 提供 **三形态接入**——同一套 argo 检索能力（同引擎、同压缩、同守卫），三种调用通道互为冗余，按宿主能力自动降级：

- **原生一等工具**（默认开）：`argo_search` / `argo_fetch`（`ctx.tools.register`），走 CLI 单发（`--call`）复用 MCP 同一套引擎与守卫，**不依赖 MCP 连接、零常驻 token 开销**；`nativeTools: []` 关闭
- **原生 web seam**（默认开）：注册 `argo` 搜索与抓取两个 provider，宿主内置 `web_search` 路由到 argo 引擎链、`web_fetch` 走 argo 抓取链（HTTP 优先，遇 Cloudflare/JS 渲染自动升级反检测浏览器）；`searchProviderEnabled: false` / `fetchProviderEnabled: false` 时对应 provider 注册但不可选
- **MCP 形态**（按需开）：19 个 `mcp__argo__*` 完整工具面（`argo_search` / `argo_local_search` / `argo_local_read` / `argo_recompute` / `argo_research` / `argo_evidence` / `argo_clarify` / `argo_fetch` / `argo_crawl` / `argo_screenshot` / `argo_pdf` / `argo_social_search` / `argo_article` / `argo_job` / `argo_extract` / `argo_preflight` / `argo_answer` / `argo_watch` / `argo_cite`，与 CLI 能力面对齐）。工具定义每轮注入上下文且压缩清不掉（实测 19 工具 ≈3.7K token/轮），而搜索/抓取高频路径已由原生工具与 web seam 覆盖，故默认不挂载；需要长尾取证能力（screenshot / pdf / social / article / job / evidence / clarify / crawl / local_*）时在 profile patch 中取消 `mcp-argo` 行注释

另有 1 个 `wide_research`：规划互补轨道（`depends_on` 依赖分阶段，默认并行）→ 有界并发子代理取证 → 来源账本（仅 http(s) URL 入账）→ 综合报告；输出自带 `quality_gate_results`（`conclusion_cap`：low/medium/high），`passed=false` 时降级表述、先核验账本来源再下结论。worker 取证工具白名单默认双写 MCP 与原生工具名（allow 语义）——MCP 挂载与否两态自洽：MCP 在时用全量面，缺席时自动落到 `argo_search` / `argo_fetch` 与宿主 `web_search` / `web_fetch`。

日常一问用 `argo_search`；单代理取证用 `argo_research`；多视角对比、要引用账本用 `wide_research`。worker 默认只能调 argo 取证工具，不会再调 `argo_research`（硬保护，用户层放行也无效）。

## web seam 的 pin 必读（漏配会打挂 web_fetch）

宿主 `dsh-web` 的 provider 选择规则：配置 id 优先；都没有且恰好一个可用则选它；**多个可用直接报 `WEB_PROVIDER_AMBIGUOUS`**。web profile 默认挂着官方 http fetch provider（免 key、永远可用），本 bundle 再注册一个就是两个可用——**不 pin 的话 `web_fetch` 整个挂掉**（`web_search` 同理，若 profile 里另有搜索 provider）。故启用 web seam 的 profile 必须在 web 服务行显式指定：

```yaml
- id: web
  config:
    searchProvider: argo    # 已默认启用搜索 seam 时必配
    fetchProvider: argo     # 已默认启用抓取 seam 时必配
```

用户层 `cordis.patch.yml` 同 id 覆盖（同 id + name 匹配才是替换）。`searchProviderEnabled: false` / `fetchProviderEnabled: false` 可整体关掉对应 seam（provider 仍注册但不可选，不影响另一个）。

搜索引擎侧，Firecrawl 等匿名可用引擎 **keyless 免配置即用**（免费层额度），配置了密钥的引擎自动升级为认证请求；缺密钥不阻断路由。

## DeepSeek 官方 key：DSH 凭证服务原生供给

argo 的 `deepseek_search` 引擎（官方 `api.deepseek.com/v1/tools/search`，结果自带 authority 权威分级 / rerank_score 排序分 / 发布时间）与 DSH 官方搜索后端**共用同一把 key**。插件经 DSH 原生凭证 seam 取用，不需要任何手工配置：

```yaml
- id: wide-research
  name: '@taxueseek/argo-dsh'
  config:
    # 默认即 ['DEEPSEEK_API_KEY']，一般无需写这一行
    keyRefs: ['DEEPSEEK_API_KEY']
```

- 解析路径：`ctx.get('credentials').resolve('DEEPSEEK_API_KEY')`，逐次解析——在 web Models 页轮换 key 后，下一跳新连接即生效，无需重启插件（池内连接最长存活 `searchIdleMs`，默认 60s）
- 层级语义与官方后端一致：启动环境变量 > 调用目录 `.env` > `$DSH_HOME/.env` > 凭证服务管理的 `.credentials.yaml`（web Models 页写入的那把）
- 安全：插件不读 key 文件、不落盘、不打日志；key 值只经内存进入 argo 子进程 env，任何输出与错误信息都不含它
- 旧宿主无 credentials 服务时静默跳过：argo 侧该引擎按缺 key 停用，其余 265 个源不受影响
- `keyRefs: []` 可整体关闭转发；后续要转发别的宿主凭证（如 `ARGO_EXA_API_KEY`），把引用名加进数组即可，entry 必须是 POSIX 标识符（apply 期 loud fail）

## 依赖

- Node.js ≥ 18（npx 拉取 argo 包）
- Python 3.9+，`pip install pyyaml`
- DSH 子代理 provider 需支持 `outputSchema`、`depthLimit`（标准 `spawn` 即可）；`toolFilter` 在 alpha.x 上可选，rc.2 已移除该启动期字段，改由插件内的 tool guard 阻止 worker 嵌套调用 `wide_research`
- 已在 DSH 0.2.1-alpha.1 与 0.2.1-rc.2 实测：rc.2 上 `wide_research`（planner → 2 worker → synthesis，passed=true / 14 sources）与原生 `argo_search`（count=3）均真跑通；`dsh web` 启动无 argo 报错。web seam 的 provider 注册随启动通过，headless 无 web 服务，未做实际调用。旧宿主 alpha.x 的 `start` 分支由单测覆盖

## Compatibility（DSH Harness 版本对照）

| argo-dsh | DSH Harness | 说明 |
|----------|-------------|------|
| 2.9.7（当前） | 0.2.1-rc.2（当前，运行中） | 双栈入口 `startActivation({provider, label, request, signal, delivery})`；rc.2 移除 `toolFilter` 启动期字段后由插件内 tool guard 阻止 worker 嵌套调用 `wide_research`；`wide_research` 端到端实测通过（planner → 2 worker → synthesis，passed=true / 14 sources） |
| 2.9.7（当前） | 0.2.1-alpha.1（实测，兼容） | 旧宿主走 `start(provider, request)` 分支，`toolFilter` 启动期字段仍认；该分支由插件单测覆盖，未在 alpha.x 上重跑端到端 |
| 2.9.2 | 0.2.1-alpha.1（实测） | 上一轮适配验证基线；rc.2 的新入口与 tool guard 自 2.9.4 起进入 |

低于 0.2.1 的 Harness 未做验证，不保证可用。

## 自定义（可选）

两行配置 id 分别为 `mcp-argo` 和 `wide-research`。用户层 `cordis.patch.yml` 同 id + name 才是替换：

```yaml
- id: mcp-argo
  name: '@deepseek-ai/dsh-mcp-client'
  config:
    serverName: argo
    transport: stdio
    command: /usr/bin/python3
    args:
      - /path/to/argo/scripts/mcp_server.py

- id: wide-research
  name: '@taxueseek/argo-dsh'
  config:
    defaultWorkers: 6
    maxWorkers: 9
    maxTracks: 9
    # 原生一等工具（可选调整）：默认只注册 argo_search / argo_fetch（高频路径，
    # 零常驻 token 开销）。全部长尾工具（article / job / social_search / pdf /
    # crawl / extract / evidence / clarify / screenshot / preflight / answer /
    # watch / cite / local_search / local_read / recompute，共 16 个，schema
    # 自动派生自 MCP 真源）都可按需追加，例如：
    # nativeTools: ['argo_search', 'argo_fetch', 'argo_pdf', 'argo_article']
    # nativeTools: []                               # 空数组关闭
    # nativeTimeoutMs: 60000                        # 单次进程超时（ms）
    # nativeMaxChars: 24000                         # 返回文本上限（字符）
    # searchProviderEnabled: false                  # 关闭原生 web seam
    childToolAllow:
      - mcp__argo__argo_search
      - mcp__argo__argo_evidence
      - mcp__argo__argo_fetch
      - web_search
      - web_fetch
```

> 注意：`argo_research` 不提供原生单发形态——它是分钟级编排，默认 60s 进程超时会中断研究；深度研究请用 `wide_research`（本 bundle 已注册）或挂载 MCP 形态。

## 卸载

在 DSH 的 Settings → Plugins 管理面板中移除本 bundle，或从 profile `package.json` 的 `dsh.profile.bundles` 中删除 `@taxueseek/argo-dsh` 后重启。
