# 慢源质量实证：放弃慢源交付，丢的是什么（2026-10-25）

> 问题来源：在讨论「把尾宽从 1.5s 缩到 0.6s」时，只统计了**省多少秒**和
> **放弃多少次**，没有回答「放弃的那批交付质量如何」。本文用三份可复现的
> 证据把这个缺口补上，并给出结论。

## 一句话结论

**被放弃的那些交付，质量绝大多数比平均更好，其中 84% 来自同一台慢源
（anysearch）；它不是低质源，而是「慢但有效的长尾覆盖源」。为了几十毫秒
去缩全局尾宽，是在拿准确性换速度——不该做。**

## 证据一：离线回放（可复跑）

```bash
PYTHONPATH=scripts python3 scripts/bench_tail_ab.py --sweep 0.6 --quality
```

输入是本地 `usage_log/query.jsonl`（2721 条真实查询）与 `adaptive.db`（7 天窗）。

```
   尾宽(s)  p50(ms)  p90(ms)    总省(s)     放弃交付
    0.60     1487     3265    202.5      225
```

- 225 次放弃，压在 **114 条不同查询**上（≈2 次/查询），不是重复调用抖动；
- 为了等到它们，**多等 p50 2306ms / p90 3883ms**——这不是「最后 100ms」的事；
- 按引擎：anysearch 188（84%）、exa 7、open_meteo 4、juejin 4……

## 证据二：质量画像（口径必须说清）

质量分来自 `query_signals.result_relevance`——**词面覆盖率代理**，衡量「结果和
查询沾不沾边」，**不等于内容正确**。所以要看两列：绝对值 + 相对全库均线。

```
质量口径：result_relevance 词面覆盖代理；全库均线 0.572
engine              次数     相关度代理      相对均线   P75ms
anysearch          188     0.686    +0.114    2381
exa                  7     0.786    +0.214     120
mdn                  1     0.121    -0.450    1538
models_dev           1     0.238    -0.334    2164
skillsmp             1     0.354    -0.217    3538
```

**被放弃最多、多等最久的 anysearch，相关度比全库均线高 0.114（第二梯队，
仅次于 github）。** 真正的低质源是 mdn / crates / models_dev 这类——它们
本来就被自适应学习器降权了，不需要靠尾宽去「顺手放弃」。

> 口径提醒：生产日志实体只存「哪台引擎多慢」，不存每条的 URL/标题，所以
> 「被放弃的那一条具体写了什么」无法从日志逐条还原。证据二是**引擎级**
> 的画像，不是单条的内容鉴定。下面证据三补内容层。

## 证据三：内容层抽查（零成本、可复跑）

同一查询分别「默认路由」与「只留快源」跑两遍，看输出差异：

| 查询 | 默认（含慢源） | 只留快源 |
|---|---|---|
| Claude Skills 课程 价格 | 8 条，3.96s | **0 条**（octen 403） |
| AI 投研 工具 年费 价格 | 8 条，5.98s | **0 条** |
| 上海 地铁 线路图 | 8 条，3.74s | **0 条** |
| kindlegen mac 版本 下载 | 8 条，1.80s | **0 条** |
| Python asyncio best practice | 8 条，2.17s（与快源重叠 6 条） | 8 条，2.66s |

**5 条里 4 条「唯一有结果的是慢源」**。再看 anysearch 单源交付的实际内容
（「AI 投研 工具 年费 价格」第 4 条）：

> 估值 40 亿美元的 AI 投研平台 AlphaSense……**年费一般在 10,000 到 20,000 美元
> 之间，团购有折扣。**

这正是这条查询要的答案，不是标题链接。为它多等 2.3–4.4s 是**付给答案的钱**。

## 所以该改哪里（区分三件事）

| 做法 | 判定 | 理由 |
|---|---|---|
| 缩全局尾宽（1.5s → 0.6s） | ❌ 不做 | 省 202s/2721 条，代价是 225 次高相关度交付 |
| 按源降权「低质慢源」（mdn/crates/models_dev） | ✅ 已有机制 | 自适应学习器已在做，不需要尾宽代劳 |
| 让慢源**不拖住快源**（并行 + 早交付 + 后台补全） | ✅ 已落地 | 见下节 |

第三条是真正该做的：慢源的价值在**覆盖**，不在**同步等待**。把它从「阻塞项」
变成「补齐项」，既拿到它的交付，也不让用户等它。

## 落地（2026-10-25 同日）

`scripts/tail_completion.py`：engine_dispatch 早停弃置引擎时把 (engine,
holder, now_fn) 随 DispatchResult.stranded 外露（cancelled 记账逐位不变），
finalize 移交后台收割——宽限（ARGO_TAIL_COMPLETE_S，默认 3s，0=关）内
完成的：学习器记真实成绩（含 domain/lang 场景标签），交付按 URL 去重合并
写回 L2 combo 缓存；CLI 由 atexit 等宽限（输出已先行），MCP/daemon 常驻
进程自然收割。timeout 弃置不收（引擎确实超窗，补全等于鼓励慢源）。

端到端实证（本机）：「Claude Skills 教程 定价」查询 skillsmp 被弃置
990ms，收割线程等到其 2205ms 完成交付，adaptive 落了一条
`success=1 / lat=2205 / quality=0.167 / domain=skill_search` 的真实成绩——
旧机制下这条记录不存在（cancelled 被 should_record_adaptive 跳过），
慢源的真实表现从没进过学习器。

## 复现

```bash
# 证据一 + 证据二
PYTHONPATH=scripts python3 scripts/bench_tail_ab.py --sweep 0.3,0.6,0.9 --quality
# 证据三（需要联网与密钥）
ARGO_USAGE_LOG=0 python3 -c "
import sys; sys.path.insert(0,'scripts'); import search
for q in ['Claude Skills 课程 价格','上海 地铁 线路图']:
    a=search.super_search(q,n=8,skip_cache=True)
    b=search.super_search(q,n=8,engine='octen',skip_cache=True)
    print(q, len(a.get('results',[])), len(b.get('results',[])))"
```

> 质量口径的边界：`result_relevance` 只看词面覆盖，**不判内容正确性**；
> 要判断「这些结果对不对」，得走 `--verify` 核正文（高后果域会自动标
> `fetch_required`）。本文没有替你做这一步——它需要真实抓取与人工判断。
