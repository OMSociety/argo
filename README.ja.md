<p align="center">
  <img src="assets/readme/hero.svg" width="100%" alt="Argo アルゴ：Agent のための検索と深掘り調査ツール、264 の検索ソース、ドメインと言語で経路を選び、吸収できる証拠を出力">
</p>

<p align="center">
  <a href="README.md">中文</a> ·
  <a href="README.en.md">English</a> ·
  <strong>日本語</strong> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="README.es.md">Español</a>
</p>

<p align="center">
  <a href="#これは何か">紹介</a> ·
  <a href="#モデル内蔵検索--ai-検索--横断検索より強い点">比較</a> ·
  <a href="#聞き方に合わせたルーティング">証明</a> ·
  <a href="#仕組み">仕組み</a> ·
  <a href="#クイックスタート">導入</a> ·
  <a href="#できること">機能</a> ·
  <a href="#インストールと設定">設定</a> ·
  <a href="#最近の更新">更新</a>
</p>

<p align="center">
  <img alt="license" src="https://img.shields.io/badge/license-Apache_2.0-blue">
  <img alt="python" src="https://img.shields.io/badge/python-3.9+-green">
  <img alt="version" src="https://img.shields.io/badge/version-2.9.7-informational">
  <img alt="engines" src="https://img.shields.io/badge/engines-264-orange">
  <img alt="mcp" src="https://img.shields.io/badge/MCP-19%20tools-purple">
</p>

> **これは taxueseek の DeepSeek Harness プラグイン群のひとつ**（[dsh-files](https://github.com/taxueseek/dsh-files) 39★）。同作者のスキルシリーズ：[session-digger](https://github.com/taxueseek/session-digger) 29★ · [taxue-invest](https://github.com/taxueseek/taxue-invest) 21★ · [taxueskills](https://github.com/taxueseek/taxueskills) 23★ · [taxue-creative-style](https://github.com/taxueseek/taxue-creative-style) 12★

# Argo アルゴ：Agent のための検索と深掘り調査ツール

## これは何か

**Argo は Agent に組み込んで使う検索・深掘り調査ツールで、関連するウェブページの情報も取得できます。背後には 264 の検索ソースがあり、95 の業務ドメインをカバーし、ローカルファイルの基本的な検索も備えています。オープンソースの検索プロジェクトの中では、非常に強力な検索能力を持っています。**

API Key を設定すれば検索品質を上げられます（Key を設定したソースは品質が良いことが多く、未設定なら自動でスキップ）。無料エンジンとローカルエンジンによる自動バックストップにも対応しています。中英日韓など 18 言語をカバーし、金融・学術・映像・スポーツ・コード・マクロなどの垂直シーンに対応します。

## サブスキル

Argo の能力は四つのサブスキル（sub-skills）で構成され、各サブスキルは独立して使えるパイプラインです：

| サブスキル | 能力 |
|--------|------|
| **local-search** | ローカルファイル検索 + ローカルゼロコスト集約エンジン（32 のローカルエンジン）。コードシンボル、ファイル名、ドキュメント全文、ファイル構造を検索できます。ネット検索結果に統合でき、スイッチひとつでローカルのヒットを同じ検索に混ぜられます |
| **local-seek** | ローカル意味検索（BM25 + ベクトルのハイブリッド）で、ノート・記憶・資料庫を検索。三層の段階：まずファイルを特定し、次に文脈を見て、最後に段落を精読します |
| **ego-search** | ログイン状態での専門検索。知乎、小红书、公众号などログインしないと見られない内容を、実ブラウザとログイン状態で検索します。既定はオフで、必要なときに有効化します |
| **js-run** | ブラウザなしでウェブ JS を実行。ブラウザを開かずに「環境探査 + 純計算」型のウェブスクリプトを走らせ、1 回あたりのコンテキストは P50 約 1ms |

四つのサブスキルは「ローカルを検索する」から「ウェブ全体を検索する」、さらに「ログインウォールの向こうを検索する」までをカバーします。ほとんどの場面は local-search + ネット検索で足り、特殊な場面で ego-search と js-run を有効にします。

## DSH プラグイン

Argo は DeepSeek Harness のプラグインでもあり、一行のコマンドでインストールできます：

```bash
dsh plugin --profile web add "github:taxueseek/argo"
```

インストール後に `dsh web` を再起動すれば有効になります。検索と取得がネイティブの一等ツールになり、MCP 接続に依存せず、常駐コンテキストのオーバーヘッドもありません。ほかに `wide_research` の並列リサーチが 1 つ、MCP ツールが 19 あり、必要に応じて有効化できます。接続形態の全体像は後述します。

## 主な強み

**264 のソース、うち 227 はキー不要ですぐ使える。** API Key を一切設定しなくても動き、無料エンジンとローカルエンジンが自動でバックストップします。Key を設定したソースは品質が良いことが多く、未設定なら自動でスキップされます。一度インストールすれば、あらゆる場面で使えます。

**ローカル検索とネット検索が一体。** これは Argo ならではの能力です。ローカルファイル検索の土台は rg や mdfind といった開発者が日常的に使うツールで、コードシンボル、ファイル名、ドキュメント全文、ファイル構造を検索します。スイッチひとつで、ローカルのヒットが同じネット検索結果に混ざり、結果には出所がローカルファイルであることが表示されます。半年ほど前に書いた一節を思い出したが場所がわからない、というときに、フォルダを巡回するより速く見つかります。

**二層キャッシュで、ホットクエリは約 10ms。** 鮮度がそれほど重要でない内容（百科事典系、過去データなど）は、一度検索するとキャッシュに入り、同じクエリはそのままヒットして毎回 API を叩きません。コストも時間も節約できます。

**多言語 + 垂直シーン。** 実測で 18 言語に対応し、中国語・英語・日本語は現地の一次ソースにたどり着けます。論文は学術ライブラリ、映像は項目ライブラリ、コードは Q&A コミュニティ、相場は金融ソースへ。曖昧な質問だけが汎用検索に回ります。

## インストールしてすぐ使う

設定ゼロで動きます。インストール方法は三つ、好みに合わせて選んでください：

**AI アシスタント自身に検索させたいなら**、スキルパッケージをそのスキルディレクトリに入れます。以後「ちょっと調べて」「事実確認して」と言えば、自分で検索します。

**気軽に試したいなら**、npx コマンド一行でその場で使えて、インストール不要です。

**アシスタントに常駐させたいなら**、MCP を載せれば 19 の検索ツールがいつでも使えます。ワンコマンド注入も用意しており、Claude Code、Cursor、Windsurf に自動で設定でき、Codex、OpenCode、Cline も対象です。設定を書く前にバックアップを取るので、いつでも戻せます。

```bash
# 方法 1：ワンコマンドスクリプト（本機で長期利用に推奨）
curl -fsSL https://raw.githubusercontent.com/taxueseek/argo/main/scripts/install.sh | bash

# 方法 2：npx で即時利用（Agent への素早いマウントに推奨）
npx -y github:taxueseek/argo

# 方法 3：git clone（開発 / ソース変更）
git clone https://github.com/taxueseek/argo.git
```

インストール後に一つ試してみてください：

```bash
argo search "python asyncio error handling"
```

返ってくるのは、StackOverflow の公式 API からコミュニティスコア順に並べ、採用済みかどうかを示した質問です。SEO ファームの山ではありません。

自分のマシンで今いくつのソースが使えるか見たいときは、コマンド一つで一覧できます：

```bash
argo search --list-engines
```

## 接続形態

Argo は四つの接続方式をサポートします。場面に合わせて選んでください：

| 形態 | 向き | 説明 |
|------|------|------|
| **MCP Server** | Agent への常駐マウント | 19 の検索ツールがいつでも使え、コマンド一つで Claude Code / Cursor / Windsurf / Codex / OpenCode / Cline に注入。設定を書く前に自動バックアップ |
| **DSH プラグイン** | DeepSeek Harness ユーザー | `dsh plugin add` 一行でインストールでき、検索と取得がネイティブの一等ツールになる。MCP 接続に依存せず、常駐コンテキストのオーバーヘッドもない |
| **Skill ファイル** | Claude Code / Grok Build / Kimi など | スキルパッケージを Agent のスキルディレクトリに入れる。「ちょっと調べて」「事実確認して」と言えば自分で検索する |
| **npx 即時利用** | さっと試したい | `npx -y github:taxueseek/argo`。インストール不要で、任意のクライアントに一時的に MCP を載せるのに向く |

四つの形態は土台が同じ Python コードで、CLI と MCP ツールは一対一に対応し、どれを入れても能力は欠けません。

## モデル内蔵検索 / AI 検索 / 横断検索より強い点

> 要するに：前三者は **人** が情報を探すためのもの。Argo は **Agent** が検索と検証を一本でやるためのもの。差は UI ではなく成果物——人向けの要約ページやリンク一覧対、Agent が並べ替え・再検証でき、文脈を膨らませない証拠。

<p align="center">
  <img src="assets/readme/why-better.svg" width="100%" alt="左：人向けの 3 種の既定検索。右：Agent が吸収できる Argo の証拠 JSON">
</p>

| 次元 | モデル内蔵検索 | AI 検索（要約型） | 横断検索 / 検索エンジン | **Argo** |
|------|----------------|-------------------|-------------------------|----------|
| 結果の形 | つなぎ合わせた長文 | 人向け要約ページ | SERP リンク一覧 | **コンパクト JSON：証拠候補 + 信頼度分解** |
| 垂直の問い（相場 / 化学式） | 汎用ウェブ | 汎用ウェブして要約 | 汎用ウェブ | **垂直ソース直結、答え型** |
| 証拠の信頼度 | スコアなし | 構造化スコアなし | スコアなし | **selection · absorption · freshness · 合意** |
| 同じクエリ | 毎回ネットワーク | 毎回ネットワーク | ページキャッシュ | **二層キャッシュ（メモリ + SQLite）、ホットクエリ約 10ms** |
| コスト制御 | 制御不能 | 1 回が高い | 無料だが手間 | **予算モード、無料優先、Key はすべて任意** |
| 多言語 | モデル任せ | モデル任せ | エンジン任せ | **言語検出 + エンジン言語パラメータ + 多言語ルーティング** |

> 仕組みとして Argo は検索を **証拠パイプライン** として扱う：言語検出 → ドメイン経路 → 多エンジン召回 → RRF 融合 → 証拠速評。Agent が並べ替え、`fetch` で核验し、文脈に収まる材料を返す。

---

## 2026 年、検索で何が変わったか

1. **リンクから証拠へ。** エージェントには並べ替え可能・検証可能・コンテキストに収まる構造化データが必要 — Argo は信頼度内訳付き JSON を返す。
2. **コンテキストが第一コスト。** エージェントプロファイルは 1 回約 3.7KB、フィールドとバイト予算はゲートで固定。
3. **サイトは AI 向け資料を備え始めた。** llms.txt と `.md` 直出しが主要ドキュメントサイトに普及 — フェッチチェーンはレベル 0 で自動探知、r.jina.ai リーダーもfallback。
4. **無料オープン生態系で足りる。** 政府・学術・標準・セキュリティの公開 API とキーレス エンジンで大部分をカバー（227 ソースが無設定）。
5. **品質は測定可能。** ランキング金標・融合利得アブレーション・負のルーティング制御。

> v2.9.3 はこの全てを実装：264 ソース / 95 ドメイン / 227 無設定。

---

## 聞き方に合わせたルーティング

<p align="center">
  <img src="assets/readme/proof-routes.svg" width="100%" alt="4 つの実ルート：金融・映像・多言語・地理">
</p>

| こう聞くと | だいたいこう動く |
|------------|------------------|
| python asyncio error handling | プログラミング QA ドメイン → StackOverflow/StackExchange 公式 API、スコアと採答マーカー付き |
| AAPL / 米株プレマーケット | 米株ドメイン、A 株と分離 |
| 肖申克的救赎 主演 / Inception director | 映像ドメイン → IMDb など |
| 梅西 俱乐部 / 库里 球队 | スポーツ → TheSportsDB など |
| 埃菲尔铁塔在哪 / where is Eiffel Tower | 地理エンティティ → OpenStreetMap など |
| NASA founding year / 国务院职能 | 組織 → Wikidata など |
| 周杰伦 专辑 / Taylor Swift album | メディア → iTunes など |
| アニメ おすすめ / 한국 영화 추천 | 日/韓を検出 → 言語に合うソース、中国語専用サイトを避ける |
| 米国 CPI、日本 インフレ率 | マクロ；国別振り分け（自国の一次ソース優先） |
| log4j CVSS / nodejs 22 end of life | セキュリティ → NVD 公式；ライフサイクル → endoflife.date |
| attention is all you need | 学術 → arXiv/OpenAlex/CrossRef のメタデータと DOI リンク |
| 阿司匹林 分子式 | 化学 → PubChem 系 |
| 台積電バリュエーション議論（深掘り） | サブ問題分割 + 並列ソース、垂直を boost |

---

## 仕組み

<p align="center">
  <img src="assets/readme/workflow.svg" width="100%" alt="クエリ → 言語とドメイン → 多エンジン → RRF → 証拠 → 統一 JSON">
</p>

```
クエリ
  ├─ 意図の曖昧さ解消（任意）
  ├─ クエリ書き換え（任意；ルーティングは元の意図を見る）
  ├─ 言語検出 + 言語嗜好
  ├─ ルート（ドメイン規則 + TF-IDF + 予算 + 言語補完 + ホットパスキャッシュ）
  ├─ 多エンジン召回（ブレーカ / 負キャッシュ / 並列）
  ├─ 空結果の段階復旧（緩和 → 同族/汎用 → 言語横断；汚染防止）
  ├─ RRF 融合 + 任意リランク
  ├─ 証拠の速評（権威 · 密度 · 鮮度 · 合意）
  └─ 統一 JSON（engine_outcomes / recovery 含む）
```

### 証拠スコア（簡易）

```
selection  ≈ ドメイン権威。SERP / リダイレクト殻は大きく減点
absorption ≈ 数字 / 定義 / 比較 / 開示などの証拠密度
freshness  ≈ 公開時刻（「2015 年以来」のような歴史比較年は無視）
総合       ≈ 0.40·selection + 0.35·absorption + 0.15·freshness + 0.10·エンジン分
```

結果には `selection`、`absorption`、`credibility_fast`、`evidence_flags` などが付き、エージェントが直接並べ替えできます。

### エージェント利用の規律（推奨）

1. **高影響の問い**（ポジション、安全、真偽）：search → 速評を見る → top を `fetch` → 結論  
2. **数字**：计算方式（定義・範囲）を明示し、矛盾は並列表示、無理に合成しない  
3. **SERP / リダイレクト**：本文ソースにしない  
4. **SNS**：世論・物語として扱い、事実の真値にしない  
5. **ファクトチェック**：ソース / 比較 / 主体など層化したクエリを足す

---

## クイックスタート

どれか 1 つで十分です。**インストールの来源は GitHub のみ**（`npx github:taxueseek/argo` または `install.sh`）、現在推奨 **v2.9.7**。**`npm install argo-search` は使わないでください**——npm registry 上のそれは**非公式の古い v1.0.1**（本リポジトリ外、機能不足、更新されない）。本パッケージは `private: true` で npm 誤公開を防ぎます。

**ゼロ設定で動く**：API Key なしなら無料エンジン + ローカル `local_*`。Key があるソースは品質が上がりやすく、無いものは自動スキップ。

### 方法一：インストールスクリプト（本機長期利用向け）

```bash
curl -fsSL https://raw.githubusercontent.com/taxueseek/argo/main/scripts/install.sh | bash
```

ホームと Skill リンク指定：

```bash
curl -fsSL https://raw.githubusercontent.com/taxueseek/argo/main/scripts/install.sh \
  | bash -s -- --home "$HOME/.local/share/argo" --link "$HOME/.claude/skills/argo"
```

確認：

```bash
python3 ~/.local/share/argo/scripts/search.py "python asyncio error handling" --json
python3 ~/.local/share/argo/scripts/search.py --list-engines
```

### 方法二：GitHub から MCP（エージェントへ即接続）

**Node.js 18+** と **Python 3.9+** が必要。初回：

```bash
pip3 install pyyaml
```

```bash
npx -y github:taxueseek/argo
```

クライアント設定例（Claude Code / Cursor / Kimi など）：

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

より安定・Node 不要：方法一で入れた後、ローカル Python を指す：

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

Python が特殊なパスのとき：`export ARGO_PYTHON=/path/to/python3`（npx 入口のみ参照）。

### DeepSeek Harness 一行プラグイン

DeepSeek Harness では 2 通り：

```bash
# A：mcp__argo__* ツール 19 個（メインパッケージ bundle、MCP 全量と同じ）
dsh plugin --profile web add "github:taxueseek/argo"

# B：検索ツール + wide_research 並列研究オーケストレーション（サブパッケージ）
dsh plugin --profile web add "github:taxueseek/argo#main&path:packages/dsh-plugin"
```

インストール後に `dsh web` を再起動。詳細は `packages/dsh-plugin/`。

### 方法三：Release ソースパッケージ

[Releases](https://github.com/taxueseek/argo/releases) から最新の **`argo-x.y.z.tar.gz`** を入手（`x.y.z` は最新リリース番号に読み替え）：

```bash
tar -xzf argo-x.y.z.tar.gz
cd argo-x.y.z
pip3 install pyyaml
python3 scripts/search.py "Python asyncio" --json
python3 scripts/mcp_server.py
```

### 方法四：git clone（開発 / ソース改変）

```bash
git clone https://github.com/taxueseek/argo.git
cd argo
pip3 install pyyaml
bash scripts/install.sh --link ~/.claude/skills/argo   # 任意
python3 scripts/search.py --list-engines
```

### 方法五：Skill ディレクトリへ（シンボリックリンク、単一来源）

```bash
python3 scripts/link_source.py --to ~/.claude/skills/argo
python3 scripts/link_source.py --to ~/.agents/skills/argo

cp installs.local.yaml.example installs.local.yaml
python3 scripts/link_source.py
python3 scripts/link_source.py --check
```

### 方法六：Python ライブラリとして

```python
import sys
sys.path.insert(0, "/path/to/argo/scripts")
from search import super_search

result = super_search("Python asyncio", n=5, mode="fast")
for item in result["results"]:
    print(item["title"], item.get("credibility_fast"), item["url"])
```

```bash
# bin/argo を PATH に入れた場合
argo search "Python asyncio"
argo research "2026 公募ファンド保有構造"
argo evidence "検証したい主張"
```

---

## 対応プラットフォーム

| プラットフォーム | 接続 | 説明 |
|------------------|------|------|
| **Claude Code** | MCP / Skill | `npx` または `mcp_server.py`；`link_source.py` 可 |
| **Kimi / Grok Build** | MCP Server | 同上 |
| **Cursor / Cline / Continue** | MCP | MCP 対応 IDE プラグイン |
| **CLI** | `search.py` / `bin/argo` | スクリプト、cron、手動調査 |
| **Python プロジェクト** | `from search import super_search` | ライブラリ呼び出し |

### インストール後チェック

```bash
python3 --version          # 3.9+ が必要
python3 -c "import yaml; print('PyYAML OK')"
python3 -m pytest tests/test_unit.py -q   # 任意
python3 scripts/search.py --list-engines
```

---

## できること

| 機能 | 説明 | 入口 |
|------|------|------|
| 統合検索 | ルート → 召回 → 融合 → 速評 | `search.py` / `argo_search` |
| ローカルファイル検索 | 本機のコード/ノート/記憶（非ネット） | `argo_local_search` |
| ローカルテキストプレビュー | ホワイトリスト内プレビュー（fail-closed） | `argo_local_read` |
| 再計算 | 制限付きサブプロセスで数値再計算（既定拒否） | `argo_recompute` |
| 深掘り調査 | サブ問題、多ソース、ギャップ提示 | `research.py` / `argo_research` |
| 信頼度評価 | 権威 / 密度 / 鮮度 / 交差検証 | `evidence.py` / `argo_evidence` |
| 意図の曖昧さ解消 | 多義語、ブランド衝突、戦略提案 | `clarify.py` / `argo_clarify` |
| ページ取得 | HTTP 優先、必要ならブラウザ | `argo_fetch`（`mode=extract` で構造化） |
| スクショ / PDF | 画面キャプチャ、PDF 構造抽出 | `argo_screenshot` / `argo_pdf` |
| サイトクロール | 一覧ページの一括取得 | `argo_crawl` |
| クエリ演算子 | `site:` / `-site:` / `-語` / `-"句"` / `"句"` / `lang:` / `after:` / `before:` をルーティングと検索の両側から剥離（詳細は references/usage.md） | クエリに直接記述 |
| 信頼シグナル | `authority_level` 離散等級（0-4、≥3 で極めて権威）+ `summary` Agent 档要約（検証後に逆填み） | 結果フィールド、`--fields agent` で表示 |
| SNS / 世論 | 微博 / 小红书 / B 站 / Reddit / X など | `argo_social_search` |

### 予算モード

| モード | 向き | 振る舞い |
|--------|------|----------|
| `fast` | 簡単な問い、速度優先 | 無料エンジン優先、有料リランク省略 |
| `auto` | 日常デフォルト | コストと品質の折衷 |
| `deep` | 調査・総説 | 品質優先、エンジン増可 |
| `budget` | 枠が厳しい | クォータ制御、使い切ると劣化 |

### 現時点の能力概要（v2.9.7）

Argo のやることを一行で言うと、質問を領域と言語で適切なソースに振り分け、返ってきた結果を信頼度で並べ、エージェントには並べ替えられ検証できる素材を渡す。検索・取得・証拠確認・ローカルファイル検索は同じパイプラインを流れ、19 個の MCP ツールは CLI コマンドと一対一で対応するので、どの形态で入れても能力は欠けない。単独コマンドもいくつかある：argo tweet は X 投稿をまとめ、argo auth はログイン状态を管理し、argo job は採用情報を集約する。全ソースの費用・键・状态は docs/ENGINE_CATALOG.md に清单されている：264 ソース、227 無設定、95 ドメイン。

最近四版本が、それぞれ一类の問題を直した。

v2.9.7 が直したのは三つの古い毛病。DSH 宿主内の AI が URL を読むとき、宿主自身の取集を使っていたため、短链ジャンプや JS チャレンジページは构造的に失败しがちで、argo の取得链は出番がなかった；この版で宿主の読込が argo を流れるようになり、そうしたページは失败から成功に変わり、普通のページは変わらない。路由候选池には 18 个の明示専用エンジンが混在し、自动选択されれば唯一の有料エンジンが密かに课金される风险があった；今は候选池になく、使うには明示が必要。エンジンが成功するたびに熔断器がファイル锁でディスクを书き换えていた；健全状态ではファイル开销がゼロになり、复数エンジンの记账も一件のトランザクションにまとまる。License は MIT から Apache-2.0 に変わり、商用での利用は安心感が増した。

v2.9.6 が担当したのはクエリ演算子と传输层。「site:github.com 某某」式のクエリは、演算子が普通の语として扱われたり、解析するだけで过滤されなかったりした；契约层ができて、路由とキャッシュは剥いたクエリだけを认识し、site: は真の后置フィルタとして実行されキャッシュキーにも入るので、二回の検索が混ざらない。传输层では、POST のたびに TLS ハンドシェイク（320〜561 ms）を再支払いしていた；接続プール化で、常驻の MCP プロセスは毎回の质问でそれを省ける。この版で公式 DeepSeek 検索も入り、従量课金で日常の combo には入らない。

v2.9.5 で加わったのは为替と重複排除の浄化。「人民币/美元 汇率」と寻ねると、宏观ドメインを回って百科词条に着地し、1.4 秒で答えなしだった；为替専用域ができて 675 msで即期レートと毎日のニュースを返す。重複排除に站后缀归一と fuzzy 复核が加わり、标题に区分式のある公式ドキュメントが后方に压されることがなくなった。

v2.9.4 が直したのは明示エンジン指定の経路。--engine X を指定するとキャッシュ TTL が一刀切だった；域判定が入って TTL は域に従い、予备エンジンがなければ同エンジンの空跑もしない。

版ごとの详细は「最近更新」に、各版のリリースノートは docs/ にある。
---

## エンジンとルーティング

設定上は **264** ソース（うち **227** はキー不要）、**95** ドメイン（`config.yaml` と `--list-engines` が基準）。

### 直結・垂直（抜粋）

| エンジン | 用途 | コスト傾向 |
|----------|------|------------|
| anysearch / duckduckgo | 一般 / 技術 | 無料 |
| sina_quote / tencent_quote / eastmoney | A 株 / 資金 | 無料 |
| finviz / seeking_alpha | 米株・海外金融 | 設定次第 |
| imdb / itunes / thesportsdb | 映像 / 音楽 / スポーツ | 主に無料 |
| local_openstreetmap / wikidata / wikipedia | 地理 / 組織 / 百科 | 無料 |
| arxiv / semantic_scholar / openalex | 学術 | 主に無料 |
| pubchem / gbif / rfc_editor | 化学 / 種 / 標準 | 無料 |
| github / stackoverflow / pypi / npm | コードとパッケージ | 設定次第 |
| byted / bocha / metaso / octen | 中国語ウェブ / AI 検索 | API / 低コスト |
| zhihu / wechat_sogou | 中国語意見 / 公式アカウント | API / 無料 |
| tavily / felo / exa | 国際 / 意味検索 | 有料または枠 |
| twitter / reddit / xiaohongshu / bilibili / weibo | SNS UGC | 無料（一部ログイン） |

### ローカルゼロコスト層（`local_*`）

独立した SearXNG は不要。主経路はプロセス内 HTML / RSS / JSON 解析（`local_bing`、`local_sogou`、`local_google`、`local_arxiv` など）。**多言語クエリ**ではエンジンの言語パラメータ（例：Bing `setlang`）を動的に書き換え、RRF 融合に参加します。

---

## 使用例

### 金融

```bash
python3 scripts/search.py "python asyncio error handling" --explain
# 典型：stock_query → 相場スナップショット
```

### 学術

```bash
python3 scripts/search.py "transformer attention mechanism paper" --json
# domain は academic になりやすく、arxiv などを含む
```

### 研究と検証

```bash
python3 scripts/research.py "2026 公募ファンド第2四半期 保有構造" --depth deep --json

python3 scripts/search.py "同一クエリ" --json | \
  python3 scripts/evidence.py "同一クエリ" --stdin --json
```

### MCP ツール一覧（12）

| ツール | 用途 |
|--------|------|
| `argo_search` | 統合検索 |
| `argo_local_search` | ローカルファイル（非ネット） |
| `argo_local_read` | ホワイトリスト内テキストプレビュー（fail-closed） |
| `argo_recompute` | 制限付きサブプロセス再計算（既定拒否、要認可） |
| `argo_research` | 深掘り研究（social-sentiment モード含む） |
| `argo_evidence` | 信頼度評価 |
| `argo_clarify` | 意図の曖昧さ解消 |
| `argo_fetch` | スマート取得（`mode=extract` で構造化） |
| `argo_crawl` | サイトクロール |
| `argo_screenshot` | 画面キャプチャ |
| `argo_pdf` | PDF 抽出 |
| `argo_social_search` | 多プラットフォーム SNS（`mode=sentiment`） |

---

## インストールと設定

### 環境要件

| 項目 | 要件 |
|------|------|
| Python | 3.9+（CLI と MCP コア） |
| 依存 | `pip install pyyaml`（唯一のハード依存） |
| Node.js | **`npx` 入口のみ** 18+ |
| SearXNG | 不要（内蔵ローカルエンジン） |

### API Key（すべて任意）

未設定なら該当エンジンをスキップし、無料がバックストップ。**環境変数を使い**、本物の Key をリポジトリや Issue に書かないでください。

```bash
# 推奨（品質向上）
export TAVILY_API_KEY="your_key"
export BOCHA_API_KEY="your_key"
export METASO_API_KEY="your_key"
export ZHIHU_ACCESS_SECRET="your_key"

# 任意
export BRAVE_API_KEY="your_key"
export FELO_API_KEY="your_key"
export GITHUB_TOKEN="your_key"
export WEB_SEARCH_API_KEY="your_key"
export ANYSEARCH_API_KEY="your_key"
export OCTEN_API_KEY="your_key"
export ARGO_KEENABLE_API_KEY="your_key"   # 任意；Keenable 無料体験
```

`config.yaml` には `{ENV_NAME}` プレースホルダのみ。平文の秘密はコミットしません。

### キャッシュ

既定 SQLite は `config.yaml` の `cache.db_path`（通常 `~/.cache/unified-search/cache.db`）。

| 種別 | おおよその TTL |
|------|----------------|
| 金融 | 約 5 分 |
| ニュース / リアルタイム | 約 10–15 分 |
| 一般 | 約 1 時間 |
| 研究 / 常緑 | 約 2–24 時間 |
| 空結果 | ごく短い（失敗を固定しない） |

### FAQ

**API Key なしで使える？**  
使えます。ローカル無料エンジンと無料 API が多く、未設定時は自動で無料経路。

**インストールスクリプトと npx の違いは？**  
スクリプトは本機固定・設定変更・Skill 接続向き。npx は MCP を素早く載せる向き。コアは同じ Python。

**エンジン確認は？**  
`python3 scripts/search.py --list-engines`、または `--explain`。

**コードが複数コピーされる？**  
しません。`link_source.py` で単一来源 + シンボリックリンクを推奨。rsync 複製はしない。

---

## CLI よく使う引数

```
python3 scripts/search.py [options] クエリ

  --engine, -e       エンジン、既定 auto
  --max-results, -n  件数、既定 5
  --depth, -d        fast | balanced | deep
  --mode             fast | auto | deep | budget
  --no-cache         キャッシュを飛ばす
  --explain          ルーティング説明を表示
  --json             JSON 出力
  --timeout, -t      タイムアウト秒
  --list-engines     エンジン一覧
```

---

## 設計の取捨

1. **エージェントが吸収できることを先に、リンク数は後。**  
2. **無料とローカルを先に、有料は任意の上乗せ。**  
3. **失敗は観測可能に**：空結果 / タイムアウト / ブレーカを分け、黙って飲み込まない。  
4. **設定駆動でエンジン拡張**、`config.yaml` が単一来源。  
5. **単一来源インストール**：リンクし、rsync しない。  
6. **SNS を真理庫にしない**；拡張と世論向きで、単独の真値には不向き。

---

## 向いている用途

- Claude Code / Grok Build / Codex / Kimi など **エージェントの検索バックエンド**  
- **多言語・多領域**の日常 Q&A：中英日韓 + 金融 / 映像 / スポーツ / 学術 / コード  
- **再現可能・キャッシュ可能**なスクリプトとパイプライン  
- ファクトチェック、公開金融情報、エンティティの **多ソース対照**

単独で向きにくいもの：プラットフォーム内の高度なエンゲージメント順位付け、長期運用の最大召回アグリゲータ（外付け SearXNG 主経路は内蔵ローカルエンジンに置換済み）。

---

## ディレクトリ（簡易）

```
argo/
├── README.md                # 中国語（既定）
├── README.en.md             # English
├── README.ja.md             # 日本語
├── README.ko.md             # 한국어
├── README.es.md             # Español
├── SKILL.md
├── package.json             # npx 入口
├── bin/argo.js              # Node MCP 起動
├── bin/argo                 # Python CLI
├── config.yaml              # エンジンとドメイン（来源）
├── assets/readme/           # README ビジュアル
├── backends/
├── mcp/                     # 多クライアント MCP 注入の来源（clients.yaml）
├── scripts/                 # search / research / mcp / install …
├── sub-skills/local-search/
├── sub-skills/ego-search/      # ログイン態の専門検索（既定オフ）
├── tests/
└── docs/
```

---

## 最近の更新

### v2.9.7: アーキテクチャ收口——DSH web_fetch シーム + explicit_only 契約 + 状態契約統一（License を Apache-2.0 へ）

- **License 変更**：MIT → Apache License 2.0（特許許諾が明示され、商用でより安全；他は不変）
- **DSH プラグイン web_fetch シーム**：宿主の web_fetch は「この URL を読む」既定経路として完全に argo を迂回していたが、fetch provider を登録し argo_fetch 链を流れるように（HTTP 优先、Cloudflare / JS レンダリング時は反检测ブラウザへ自動升级）；search provider と同构の双路実行——常駐 MCP プール优先、传输层故障时のみ CLI 単发にフォールバック、ツールレベルエラーとTimeoutは再送しない（呼び出しは既に完了しており、再送は引擎呼び出しと配额を倍にするだけ）；失败は五类（Timeout / ブロック / 空结果 / 一般 / キャンセル）に分类し行动可能な文案を付与；新设定 `fetchProviderEnabled` / `fetchProviderId` / `fetchTimeoutMs`（既定 25000）/ `fetchMaxChars`（既定 50000）は既定全开・逃げ口付き；实测：クロスオリジンジャンプ（短链、协议アップグレード、リダイレクト殻）と JS チャレンジ页が宿主の构造的失败から argo 成功へ、普通の静止页は品质不変
- **explicit_only 契约の收口**：`config._routable_filter` は環境白黒リスト / 键 / 拉黑だけを滤し explicit_only を滤していなかったため、18 个の明示专用引擎（唯一の有料 `deepseek_search` を含む）が enabled 候选池に寝たまま、TF-IDF 注入・catch-all・backfill・兜底など六つの経路全てが选択できた——语料に词条がなかっただけで、一条追加すれば auto 档で有料引擎を并行呼び出して课金される；候选池の唯一生产者一处で滤し、`tests/test_explicit_only_gate.py` が三契约（注入不带入 / 候选池排除 / 明示 `--engine` は通常単发）をロック
- **状態契约の统一**：熔断器は健全 closed 态で计数 0 のときメモリ短路（ファイル锁ゼロ・ディスク书き换えゼロ）、`(st_mtime_ns, st_size)` でクロスプロセス变更を感知；adaptive 记账は `MAX(created_at)` を単条集约 SQL に统合し、`batch()` コンテキストマネージャで多引擎记账を単一トランザクションに；配额耗尽は生效凭证の指纹を记録し新 key 交换时に自动アンロック；route キャッシュは combo 引擎耗尽・旧耗尽引擎の恢复時に自动无效再计算；`is_engine_routable` 单一准入谓词が backfill / tfidf / breaker_filter の五层滤过を收口
- **调度と传输**：auto / deep 档も配额ハード耗尽引擎を除外（fail-open 兜底）；ヘッジ待机窗を狭め、早停判定を缓和（Wave-1 のクロス引擎累计达标で停止、Wave-2 を起动しない）；POST 接続プール开通（anysearch 约 320ms / octen 约 561ms を毎回节约）+ MCP 事前接続；気象ドメインに `early_stop_min_results: 1` を追加
- **子スキル热路径减法**：js-run は SIGALRM を MiniRacer ネイティブ timeout に替换し、crawl / research / mcp の作业スレッドから呼ぶと必ず `ValueError: signal only works in main thread` で落ちるクラッシュを根治；local-seek の再顺は毎回 O(N) 读盘と JSON 解析を解消；local-search は registry を复用し双重 YAML 解析を解消；ego-search は auto 下で探査を必要时短路
- **検証**：プラグイン単测 71 passed；argo 全量回归 4264 passed / 28 skipped；pre-commit 七门 123 passed；fetch 链の対撮で普通页は非退行、クロスオリジンジャンプと JS チャレンジは失败→成功

### v2.9.6: DeepSeek Search エンジン + クエリ演算子契約 + 传输層の接続プール + ルーティングスナップショット門

- 新エンジン `deepseek_search`（公式 `api.deepseek.com/v1/tools/search`）がデフォルト有効：`DEEPSEEK_API_KEY` がない場合のみ自動スキップ、他の 265 ソースには影響なし；実測 445-510ms（anysearch 1.7-4.5s / exa 3.7s）、authority 権威階層 / rerank_score / 公開時刻の三者中唯一の全項目カバー、ja/ko/es 多言語は anysearch と同等；従量課金、ドメイン combo には入らず、明示 `--engine deepseek_search` が主経路；DSH ホストはネイティブ認証情報 seam で公式バックエンドと同じ key を共用（web Models ページでのキー交替は次のホップから効く、保存もログもされない）
- 修正：`--since/--until` が deepseek_search に効いていなかった（TIME_CAPABLE_ENGINES に追加）
- 新規 `query_operators.py` クエリ演算子契約層：`site:` / `-site:` / `-語` / `-"句"` / `lang:` / `after:` / `before:` が五つの散在形態から構造化演算子に収束；路由・キャッシュ・クエリ理解は命令を剥いだ clean_query のみを認識；`site:` / `-site:` が真の後置フィルタを実行（サブドメイン一致、複数サイト OR、フィルタ数は `site_filtered` に）、演算子は結果キャッシュキーに投入され串線を防止
- `evidence.py`：Agent 档二層概要 `summary` フィールドを新設（DeepSeek Search の概要 semantics を参考）
- 传输層の二重払い排除：POST がプール接続を再利用（実測 同一接続の 2 回目で anysearch 320ms / octen 561ms 節約）、貸出失敗時の再試行と読み切り后才還却つき；MCP 事前接続；クォータ耗尽と死んだ負キャッシュの收口
- 路由：octen が一般フォールバック鎖の 2 番目と TF-IDF ヘッジ枠に入る（anysearch じらし窓 p90 3273→1614ms、max 6266→1928ms、エラー 9→0；健全窓では中央値差なし、尾部保険と定位）、逃げスイッチ `ARGO_GENERAL_FALLBACK_LEGACY=1`
- RRF 口径隔離の名次減衰を修正：同一エンジンの全結果が同点（実測 anysearch 5 件とも 0.017213）、出力が「エンジン权重でのブロック連結」に退化；「同一エンジン内で厳密単調減少」を鎖る新テスト
- Bing ck/a リダイレクト殻が還元されず聚合層が結果を丸ごと濾過していた問題を修正（直近 7 日 40.2% 空結果）：オフライン base64url 復号で真リンクを還元、ゼロネットワーク
- TF-IDF リーダー combo が `['anysearch','anysearch']` を二重実行していた問題を修正（クォータ二倍で wasted_ms は 0 記録）：200 件の実クエリ再演、重複 combo 1→0
- 検索改善：失敗負キャッシュ、Nitter フェイルオーバ、口径隔離、X Article 抽出、クエリエコー防衛（早停拒収 + 回復鎖のエンジン切替）
- 工学化：`scripts/pre-commit` 快门禁を新設（static_lint / module_size_gate / usage_doc / consistency / routing_snapshot / context_budget + engine_catalog、実測 ~12s）；ルーティング決定スナップショット門が路由の反転を diff 可能な golden に変える（三つの注釈集合の和、115 クエリ、domain と kind のみ比較で環境ノイズによる誤赤なし）；口径レジストリ同期テストが「表のエンジン名は実登録必須」をロック
- DSH プラグインは DSH 0.2.1-rc.2 対応：実行時入口のデュアルスタック（`startActivation({provider, label, request, signal, delivery})` 新 / `start(provider, request)` 旧）、rc.2 で `toolFilter` 削除後はプラグイン内 tool guard が worker の `wide_research` 入れ子呼び出しを阻止；rc.2 上で `wide_research`（planner → 2 worker → synthesis、passed=true / 14 sources）とネイティブ `argo_search`（count=3）の端到端実測通過；0.2.1-alpha.1 互換分枝は単測カバー；プラグイン単測 46→50
- DSH 環境バージョン：**DSH 0.2.1-rc.2（現行・稼働中、端到端実測済み）+ DSH 0.2.1-alpha.1（互換、旧 start 分枝は単測カバー）**；対応表は `packages/dsh-plugin/README.md` の Compatibility 節

### v2.9.5: 為替専用ドメイン + 二層重複排除 + 順位誤殺修正 + チェックアウト別 daemon 隔離

- `config.yaml`: 新ドメイン `fx_query` —「人民元/米ドル レート、中心相場、オフショア」系のクエリはマクロ域の空回りを経て百科事典項目に落ちることはなく、生レート + 毎日の中心相場ニュースを返す（実測 675ms、修正前は 1411ms かつ的外れ）
- `search_rank.py`: 重複排除を二層に — タイトルのサイト suffix 正規化（ゼロ依存）+ rapidfuzz ファジー近重复チェック（近似命中帯内のみ起動；`ARGO_DEDUP_FUZZY=0` で切断、未インストールなら純 minhash に自動フォールバック）
- 修正: 劣化リランク時のタイトル区切り誤殺 — `|` / `_` / `——` を含むタイトルは一律 ×0.6 で公式ドキュメントが 40% 圧下されていた；Bocha キーなしの auto/deep クエリ全部が影響（判定は rank_signals の単一実装に収束）
- `query_understanding.py`: 否定理解に「不是X」を追加（疑問形「是不是」は否定と誤判定しない）
- `daemon.py`: socket/pid/ポインタ等のオンディスク名をチェックアウト別に隔離 — マルチ worktree/clone による daemon の奪い合い・誤殺・「変更が効かない」の三故障を根絶
- 新規オプション依存 rapidfuzz（`pip install rapidfuzz`；install.sh が自動導入、未インストールでもコア機能に影響なし）

### v2.9.4: 明示的エンジンドメイン帰属 + 回復チェーン遮断 + ゲート同期

- `route.py`: `--engine X` で `match_domains` を補完しキャッシュ TTL 一般化を修正
- `recovery.py`: 単一エンジンでフォールバックなしの場合 L1 空実行をスキップ
- `config.yaml`: `org_entity` に株主盡職調査語を追加；`fund_query` に政策法規語を追加
- `mcp_launch.sh`: `set -a` を `. "$ENV_FILE"` 一行に收窄
- `sub-skills/local-search/`: エンジンレジストリ層の閉鎖と search_v3 品質向上
- ゲート同期: module_size_gate / ENGINE_CATALOG 整合

### v2.9.3：X 投稿の完全パッケージ + ブラウザログイン状態車道 + ローカルチェーンの質・速度修正

- **新規**：`argo tweet` — 1 コマンドで指定 X 投稿の全文・スレッド/引用/リポスト・インタラクションデータをパッケージ；デフォルトはテキストのみ、`--out` で 4 ファイル一式（post.md/raw.json/manifest.json/CHECKLIST.md）、`--media` で画像/動画を必要時にダウンロード；失敗理由は成果物に可視
- **新規**：`argo auth` ブラウザログイン状態車道 — `login/status/logout` でサイト別永続ブラウザプロファイルを管理；QR を一度スキャンすればログイン必須ページも取得可能；Cookie は Chrome 自身の暗号化ストレージにのみ保存され argo は読み出さず、ログイン状態の結果は `login_state_used` を付けて共有キャッシュから除外（`ARGO_AUTH_FETCH` で有効化）
- **精度**：中国語ローカルチェーンが Sogou/Baidu のリダイレクト殻をセッションなしで実 URL に解決（保持結果 1→5 件）；インテントゲート誤ロック修正（「チュートリアル」系クエリが単一エンジンに固定されなくなる）；鉄道のテーブル行識別 URL により候補ファンネル圧縮（10→1）を実態どおり 10→10 に修復
- **速度**：コンセンサス猶予の適応化（最初に十分届けたエンジンで放行；英語ディスパッチ ~3.0s→2.2-2.5s）；ローカルロングテールの早期打ち切り；ローカル画像フィンガープリントを mmap 行列積に（77k 枚 158ms→3.9ms、既定無効 `ARGO_LOCAL_IMAGE=1`）；エージェント消費の自動スリム化 + markdown 内容ネゴシエーション、MCP 呼び出しごとの固定オーバーヘッド −32%
- **ソース**：ドメイン参照のない 43 エンジンを各ドメインに配線；route_lang 言語ルーティング；キー不要の金融ソース 3 件追加；`--academic-deep` ワンフラグ学術マルチソース；鉄道乗り継ぎ・経停クエリ
- **安定性**：js-run を fetch チェーンの第一車道に接線（Chrome フィンガープリント再試行）；jsrun セッション漏洩とバックオフ予算を修復；タイムアウト引き締め（redskill 60→15s）と宣言ポリシー三分割

### v2.9.2：DSH 0.2.1-alpha.1 の適合検証 + ルーティング/ガード修正 + js-run サブスキル

- **互換性**：DSH プラグインを最新の DSH 0.2.1-alpha.1 で実検証 — ネイティブ第一級ツール / web_search seam / wide_research の三形態がすべて動作；`argo mcp inject` に WorkBuddy を追加し、7 番目のホストまで対応
- **精度**：TF-IDF 弱証拠の補助源降格、死源フロア + サーキットブレーカー枠の再充填、 quota 枯渇エンジンの分離、serp_guard の誤検知修正
- **速度と安定性**：engines/evidence の遅延インポート（import 量 −50%）、アドミッション存在集合ショートカート（open 261 → 99）、MCP 入口/数値引数ガード；新サブスキル `sub-skills/js-run`（ブラウザなしでウェブ JS を実行、P50 ≈ 1ms）

### v2.9.1：コンテンツ品質の最適化 + コンテンツファーム対策 + 最新環境への適合

- **クリーン**：コンテンツ品質評価を最適化し、コンテンツファーム対策を強化 — 検索結果の低品質・大量生成コンテンツをより効果的に識別・フィルタリング
- **互換性**：最新バージョンに適合し、現在の環境とシームレスに連携
- **安定性**：ローカル検索に自身のインストールツリーのガードを追加 — 検索結果が argo 自身のソースコードで汚染されないように

### v2.9.0：ソース最適化 + プラグインと CLI の対等化 + 少数言語

- **充実**：ソース 237 → 253（無設定 198 → 219）。14 の少数言語ローカルニュース源、CORE オープンアクセス全文源、TinEye 逆画像検索、Bing RSS の安定出口などを追加；百度と捜狗（Sogou）の二つの常緑源を復活
- **整列**：CLI 18 コマンドと MCP 19 ツールが一対一対応 — プラグインと CLI の検索能力が初めて完全に対等に
- **多言語**：14 の少数言語源（タイ/アラビア/ヘブライ/ギリシャ/ヒンディー/ベトナム/トルコ/インドネシアなど）を追加し、クエリ言語に応じて自動配源
- **高速**：インポートチェーン −79%、n=200 再ランキング 33ms → 1.5ms、キャッシュ命中率は約六割からほぼミスなしに
- **信頼性**：クォータ書き込みパスのプロセス間安全性を修正、早期停止の結果がタイムアウトと誤記されなくなり、`argo stats` で検索品質が自身の帳簿を持つ

### v2.8.9：出力スリム化 + 検索の高速・充実化 + 海外メディアとファクトチェック源 5 個

- **軽量化**：デフォルト出力 −66%（同じ結果を三度書かない）；同一クエリ −30%（ルーティング決定キャッシュ）；低速回線の待ち時間 −36%（主源が 0.8 秒超えたら自動でバックアップ源を追加起射）
- **充実**：リコール +35%、取得レイテンシ −30%；本文構造の保真 0/6 → 6/6（見出し・リスト・表が潰れなくなった）；中国語コンテンツが系統的に低品質判定されなくなる
- **追加**：ソース 232 → 237（キー不要 194 → 198、全て無料 — The Guardian、France 24、DW、ファクトチェック FactCheck.org / Full Fact の米英両口）；死源 gdelt を廃止
- **信頼性**：数字が相互に矛盾する六つの記帳欠陥を修正；六段ファネルで「0 件」がどの層で潰れたか特定可能；オフライン再生ツールで変更効果を当日検証。詳細は [リリースノート](docs/RELEASE_NOTES_v2.8.9.md)

### v2.8.8：実ユーザー報告の修正 + 全面高速化 + ソース 232 個

- **修正**：推奨名でキーを設定してもエンジンが黙って 0 件になる問題（#12）、取得チェーンがプロキシを通らず GitHub 等が必ず失敗する問題（#13）——`ARGO_PROXY`・config のドメイン別ルール・標準プロキシ変数がすべて有効になり、`NO_PROXY` を尊重
- **高速化**：コマンド冷起動 2.1s → 0.55s；設定のプロセス間キャッシュ 50–82ms → 16–18ms；毎回の検索に各段の所要時間と予算消費を出力し、どこが遅いか推測不要（`--no-timing` で無効化）
- **新規**：ソース 218 → 232（設定不要で使えるのは 184 → 194、すべてキー不要：中国系トレンド・セキュリティ脆弱性・オープンアクセス学術・スキルディレクトリ・Agent 検索）、直答 `argo answer`、Web 観測 `argo watch`、CLI/MCP ツール面の整列
- **安定性**：三 OS の慣例パス（`argo paths` 自己点検を追加）、Python 3.9 対応、沈黙していた劣化を正直に記帳。詳細は [リリースノート](docs/RELEASE_NOTES_v2.8.8.md)

### v2.8.7：ソースを 218 に拡充 + 修正一括

- **ソース拡充**：168 → 218 ソース、72 → 89 ドメイン（StackExchange Q&A、DOI メタデータ、脆弱性情報、製品ライフサイクルなど公式ソースを追加）、本文取得の直出チャネルを 3 本追加
- **修正一括**：マルチエンジンルーティング、ゼロ結果時のフォールバック、中国語リダイレクト、ローカル検索の劣化など。詳細は [リリースノート](docs/RELEASE_NOTES_v2.8.7.md)

### v2.8.6：検索の高速化 + 多ソース分担

- エンジンレーシング、知乎三ソース分担、言語/学術ディスパッチ拡大、死源ゲート

### v2.8.5：DSH プラグインツールのネイティブ化 + MCP 既定オフ + Windows 対応

- **プラグインツールのネイティブ化**：`argo_search` / `argo_fetch` がネイティブの一等ツールとして登録され、MCP 接続なしで既定使用可能；スキーマは唯一の来源 `mcp_tools.py` から自動生成され、両側で零ドリフト；`argo_research` 以外の 18 ツールは `nativeTools` で随時有効化可能
- **MCP 既定オフ**：3 形態の接続（随時マウントの MCP / 既定入口のネイティブツール / web_search seam）；普段は常駐トークン消費ゼロ、14 ツール全量が必要なときは profile patch 1 枚で開く
- **Windows 互換**（コミュニティ PR #11）：一時パスはシステム temp、GBK エンコード修正、`python3`/`python` の実行時解決、symlink は権限なしで junction にフォールバック、PowerShell 一括インストール `install.ps1` を追加
- **クォータ自己修復**：HTTP 200 に隠れたリモートクォータ枯渇を検出し、ルーティングがそのエンジンを除外してバックアップ源へ切替、次クォータ期間で自動復帰
- **フェッチ全体 deadline**：`ARGO_FETCH_DEADLINE_S`（既定 60s）でフォールバック連鎖の総時間を上限化；429/503 の停止シグナルを尊重；tinyfish レンダリング + `.md` 変体プローブ

### v2.8.4：ローカルデータ融合 + ワンコマンド MCP 接続

- **深掘り研究が手元データを食べられる**：作業パッケージに `file_inputs`（手元の CSV / XLSX / 文献。ハッシュだけ登記、中身は入れない）+ `recompute`（サンドボックス再計算。食い違いはフラグ）
- **MCP 接続は手で設定をいじらない**：`argo mcp inject` が Claude Code / Cursor / Windsurf / Codex / OpenCode / Cline に書く（アトミック書き込み + バックアップ + 復元）
- **簡単なクエリは安いまま**：正規化 + 複雑さゲート + SNS/プラットフォーム構文優先 + 中国語エンジンを捨てても候補を見続ける
- **Keenable** を無料体験のウェブ検索源として追加
- **セキュリティ**：recompute は外部プロセスの出網を遮断；ホストパスはインストール感知

> 詳細は下表と各版の[リリースノート](docs/)。

---

## 更新履歴

| 版 | 内容 |
|----|------|
| **v2.9.7** | **アーキテクチャ收口 + DSH web_fetch シーム + License を Apache-2.0 へ**：MIT → Apache License 2.0；宿主 web_fetch が argo_fetch 链を流れる（HTTP 优先、JS チャレンジでブラウザ升级、双路実行、ツールエラーは再送せず、失败五分类）；18 个の explicit_only 引擎を路由候选池から除外（auto 档での误课金口を闭塞）；熔断健全短路、adaptive 単一トランザクション记账、配额 key 交换時の自动アンロック、route キャッシュ耗尽无效；auto/deep のハード耗尽除外 + 早停缓和 + POST 接続プール；js-run が非メインスレッドクラッシュを修正。 |
| **v2.9.6** | **DeepSeek Search エンジン + クエリ演算子契約 + 传输層の接続プール + ルーティングスナップショット門**: 新エンジン `deepseek_search` デフォルト有効（key なしで自動スキップ；445-510ms、authority/rerank_score/公開時刻の唯一の全カバー、時間窓が真に効く；DSH はネイティブ認証 seam で key 共用）；`site:`/`-site:`/`-語`/`lang:`/`after:`/`before:` が演算子契約層に収束し真の後置フィルタ + キャッシュキー投入；POST 接続プール（1 回あたり 320-561ms 節約）+ MCP 事前接続；octen がフォールバックとヘッジ枠に（p90 3273→1614ms、逃げスイッチ `ARGO_GENERAL_FALLBACK_LEGACY=1`）；RRF 名次減衰と Bing リダイレクト殻（40.2% 空結果）を修正；pre-commit 快门禁とルーティングスナップショット門を新設；DSH プラグインは 0.2.1-rc.2 デュアルスタック + alpha.1 単測カバー。 |
| **v2.9.5** | **為替専用ドメイン + 二層重複排除 + 順位誤殺修正 + チェックアウト別 daemon 隔離**: 新ドメイン `fx_query`（レート/中心相場を 675ms で生レート+日次ニュース、修正前は百科事典）；重複排除にサイト suffix 正規化（ゼロ依存）+ rapidfuzz ファジーチェック（オプション、`ARGO_DEDUP_FUZZY`、フォールバック付き）を追加；区切り ×0.6 誤殺を修正（公式ドキュメントが前列に）；否定に「不是X」を追加；daemon 名をチェックアウト別に隔離。 |
| **v2.9.4** | **明示的エンジンドメイン帰属 + 回復チェーン遮断 + ゲート同期**: `--engine X` で `match_domains` を補完しキャッシュ TTL 一般化を修正；単一エンジンでフォールバックなしの場合 L1 空実行をスキップ；`config.yaml` ドメインルール強化；`mcp_launch.sh` 環境変数エクスポートを收窄；ローカル検索エンジンレジストリ層の閉鎖と品質向上；ゲート同期。 |
| **v2.9.3** | **X 投稿の完全パッケージ + ブラウザログイン状態車道 + ローカルチェーンの質・速度修正**：新規 `argo tweet`（全文/スレッド/引用/リポスト/メディアを必要時にパッケージ、`--out` で 4 ファイル一式）；新規 `argo auth` ブラウザログイン状態車道（サイト別永続プロファイル、Cookie は Chrome の暗号化ストレージのみ、ログイン状態の結果は共有キャッシュ除外）；中国語ローカルチェーンが Sogou/Baidu リダイレクト殻をセッションなしで解決（保持 1→5）+ コンセンサス猶予適応化（英語ディスパッチ ~3.0s→2.2-2.5s）；js-run を fetch チェーン第一車道に接線（Chrome フィンガープリント再試行）；鉄道乗り継ぎ・経停クエリ（ファンネル 10→1 を実態どおり 10→10 に修復）；`--academic-deep` ワンフラグ学術深掘り；43 エンジンのドメイン配線 + キー不要金融ソース 3 件 + インテントゲート誤ロック修正；ローカル画像フィンガープリント 158ms→3.9ms；エージェント消費スリム化（MCP 固定オーバーヘッド −32%）。 |
| **v2.9.2** | **DSH 0.2.1-alpha.1 の適合検証 + ルーティング/ガード修正一括 + js-run サブスキル**：DSH プラグインの三形態を最新 DSH 0.2.1-alpha.1 で実検証；`argo mcp inject` に WorkBuddy を追加し 7 番目のホストまで対応；TF-IDF 弱証拠の補助源降格、死源フロア + サーキットブレーカー枠の再充填、クォータ枯渇エンジンのルーティング分離、serp_guard の巻き込み誤検知修正；engines/evidence 遅延インポート（import −50%）とアドミッション存在集合ショートカート（open 261→99）；MCP 入口と数値引数ガードの収口；js-run サブスキル新規追加（ブラウザなしでウェブ JS、P50 ≈1ms）。 |
| **v2.9.1** | **コンテンツ品質の最適化 + コンテンツファーム対策 + 最新バージョン適合**：コンテンツ品質評価を最適化し、低品質な大量生成コンテンツの識別・フィルタリング能力を向上；最新バージョンに適合しシームレスに連携；ローカル検索に自身のインストールツリーガードを追加し、結果が自身のソースで汚染されるのを防止。 |
| **v2.9.0** | **ソース最適化 + プラグインと CLI の対等化 + 多言語少数言語**：ソース 237→253（無設定 198→219）。14 の少数言語ニュース源、CORE 全文源、TinEye 逆画像検索、Bing RSS など追加；百度と捜狗を復活；CLI 18 コマンドと MCP 19 ツールが一対一対応；インポートチェーン −79%、再ランキング 33ms→1.5ms、キャッシュ命中率大幅向上；クォータ書き込みパスのプロセス間安全修正；`argo stats` ローカル使用ログを新規追加。詳細は [リリースノート](docs/RELEASE_NOTES_v2.9.0.md) |
| **v2.8.9** | **出力スリム化 + 検索の高速・充実化 + 海外メディアとファクトチェック源 5 個**：デフォルト出力 15.5KB→5.2KB（−66%、`--envelope` で完全封筒を復元）；ルーティング決定キャッシュで同一クエリ −30%；低速回線のディスパッチ −36%（直列ドメインは 0.8 秒超過で自動ヘッジ）；取得チェーン五輪の刷新（リコール +35%、レイテンシ −30%、ロングテール P90 −8%）+ 本文構造の復元（見出し/リスト/表の保真 0/6→6/6）+ CJK 品質スコア修正；キー不要新源 The Guardian RSS / France 24 / DW / FactCheck.org / Full Fact（232→237、キー不要 194→198、ドメイン 90→92）、死源 gdelt 廃止；自己整合性欠陥六箇所を修正 + 六段ファネル帰属 + オフライン再生ツール（`scripts/replay_eval.py`）+ ポリシー後デプロイ門禁とシナリオ閾値契約。詳細は [リリースノート](docs/RELEASE_NOTES_v2.8.9.md) |
| **v2.8.8** | **実ユーザー報告の修正（#12 キー別名の無言失敗、#13 プロキシ非対応の取得）+ 全面高速化 + ソース 218 → 232**：出口ディスパッチを統一（`ARGO_PROXY` / ドメイン別ルール / 標準プロキシ変数、`NO_PROXY` を尊重）；キー読み取り 16 箇所を別名チェーンに統一；コマンド冷起動 2.1s→0.55s、設定キャッシュ 50–82ms→16–18ms、QPP 平坦度ゲート早停、`--list-engines --detail` を 152KB→51KB に圧縮；直答 `argo answer` と Web 観測 `argo watch` を追加、キー不要ソース 14 個（中国系トレンド・ライフスタイル／セキュリティ脆弱性／オープンアクセス学術／スキルディレクトリ／Agent 検索）、69 エンジンの分類を補正（`web_general` フォールバック比率 41%→20%、security ドメイン新設）；三 OS 慣例パス（`argo paths`）+ Python 3.9 + 有界並列でタイムアウトを実効化；search.py をモジュール分割 3351→2526 行、22 エンジンの関連性ゴールデン、静的欠陥・出力契約門禁。詳細は [リリースノート](docs/RELEASE_NOTES_v2.8.8.md) |
| **v2.8.7** | **218 ソース / 89 ドメイン + 本文直出 3 チャネル + ルーティング発火規律 + macro ゼロ結果修正**：バッチ 7/8/9 で累計 50 の新ソース（法令／規格／セキュリティ情報／学術／ニュース／エンタメ／エネルギー交通／法務行政）、stackexchange と doi エンジン；取得チェーン第 0 段に llms.txt と `.md` 直出プローブ、r.jina.ai リーダー段を追加；`--engine` カンマ複数指定の修正、tfidf 计算方式と route_reason、負方向ルーティング制御マトリクス、ランキング金標と融合利得アブレーション門禁；中国マクロ照会は国家統計局を前置、全域ゼロ結果リカバリが L3 を解放、救援エンジンを正直に記帳。詳細は [リリースノート](docs/RELEASE_NOTES_v2.8.7.md) |
| **v2.8.6** | **hedged 競速 + 知乎三源分担 + 宣言的言語ディスパッチ + 到達性ゲート + 学術検索プロトコル**：先頭エンジンに猶予窓を設けた競速（速いエンジンは呼び出し 1 回で済む）、zhihu の全网検索／個人データ接続と餓死防止、サブクエリの言語・学術ディスパッチ（英語源と 17 の学術源を研究収集に接続）、エンジン言語メタデータと到達性ゲート（死に源の可視化）、geo 尾部 −56%、学術検索クエリ構築プロトコル。詳細は [リリースノート](docs/RELEASE_NOTES_v2.8.6.md) |
| **v2.8.5** | **DSH プラグインツールのネイティブ化 + MCP 既定オフ + Windows 互換 + クォータ自己修復 + フェッチ deadline**：`argo_search`/`argo_fetch` がネイティブ一等ツールで既定可用（CLI 単発は MCP と同エンジン同ガード、スキーマ単一来源 + ドリフト門禁）；3 形態接続、MCP は随時マウント既定オフ；Windows 互換（temp パス / GBK / インタプリタ解決 / junction / `install.ps1`、PR #11）；クォータ自己修復ループ（200 業務エラー封筒検出 + ルート除外 + 周期自己修復）；フェッチ全体 deadline（`ARGO_FETCH_DEADLINE_S`）+ tinyfish レンダリング + `.md` 変体プローブ；ホットリロード env と状態ディレクトリ単一来源。[リリースノート](docs/RELEASE_NOTES_v2.8.5.md) |
| **v2.8.4** | **ローカルデータ融合 + 多クライアント MCP 注入 + 構造化検索 + Keenable**：研究 L1 の手元一次データ（`file_inputs` + `recompute` + `local_sources`）；`argo mcp inject`（宣言的 `mcp/clients.yaml`）；クエリ正規化 / 変体 / 複雑さゲート / SNS 構文優先 / TF-IDF 修正 / `--include-local`；Keenable（無料体験）；セキュリティ強化。[リリースノート](docs/RELEASE_NOTES_v2.8.4.md) |
| **v2.8.3** | **多言語ルーティング修正 + プロセス内 anysearch + weighted RRF**：ja/ko が対象言語を返す；独仏西伊は anysearch；weakest-link 降権（論文 2508.01405）。[リリースノート](docs/RELEASE_NOTES_v2.8.3.md) |
| **v2.8.2** | **Windows + 証拠セマンティクス統一**：npm `os` 制限撤去；GBK クラッシュ対策の UTF-8；メインパッケージ `dsh.bundle`；`wide_research` 品質門禁。[リリースノート](docs/RELEASE_NOTES_v2.8.2.md) |
| **v2.8.0** | **証拠クローズドループ + 求人 v3 + 天気双源**：`fetch_required` / `--verify`；`argo job`；wttr.in + Open-Meteo；Parallel / You.com。[リリースノート](docs/RELEASE_NOTES_v2.8.0.md) |
| **v2.7.3** | エンジン層 HttpClient；TF-IDF で 25 垂直を活性化；70 ドメイン TTL；垂直の中英。[リリースノート](docs/RELEASE_NOTES_v2.7.3.md) |
| **v2.7.2** | ログイン態の専門検索（ego-search、既定オフ）；日韓クエリが中国語エンジンに混ざらない。[リリースノート](docs/RELEASE_NOTES_v2.7.2.md) |
| **v2.7.1** | SSRF 強化 + ルーティング健全性の意味修復。[リリースノート](docs/RELEASE_NOTES_v2.7.1.md) |
| **v2.7.0** | **垂直構造化モーダルカード**：内蔵 `bocha` / `bocha_ai` ネイティブエンジン、`modal_card` ドメインで列車チケット / ガソリン価格 / 貴金属 / 万年カレンダー / 星座 / 電話番号 / 車両 / 病院予約などのリアルタイムカードを統一認識；`bocha` web 解析の欠陥を修正。詳細は [リリースノート](docs/RELEASE_NOTES_v2.7.0.md) |
| **v2.6.2** | 独立した改良ラインを統合：ネットワーク環境認識 / 加重 RRF + セマンティックキャッシュ / 適応型エンジン無効化 / コンテンツセーフティ + クエリバリアント / 三大垂直エンジン / 日韓ドメインルーティング補完；v2.6.1 のルーティング修正を含む。詳細は [リリースノート](docs/RELEASE_NOTES_v2.6.2.md) |
| **v2.6.1** | v2.6.0 修正版：ルーティングの巻き込み修正（`capital of` が fact_check を奪わない）；バージョン同期。詳細は [リリースノート](docs/RELEASE_NOTES_v2.6.1.md) |
| **v2.6.0** | **多言語検索**（検出 / エンジンパラメータ / 言語横断フォールバック）；映像・スポーツ・地理・組織・メディア垂直；recovery 汚染防止；能力族と行列回帰；約 120+ 源。[リリースノート](docs/RELEASE_NOTES_v2.6.0.md) |
| **v2.5.1** | 金融/マクロ/化学の答え源を厚く；エンジン階層 + combo 予算；[v2.5.1](docs/RELEASE_NOTES_v2.5.1.md) |
| **v2.5.0** | インストールスクリプト + npx；書き換えとルーティング分離；ホットパスキャッシュ；MCP コンパクト |
| **v2.4.0** | 低分ルートのフォールバックと SNS 誤吸フィルタ；キャッシュ depth / ソフトヒット；ブレーカと負キャッシュ；`engine_outcomes` |
| **v2.2–v2.3** | 証拠二段階、中国語ソース表、content_signals、fetch スタック、エンジン拡充 |
| **v2.1** | SNS エンジン層（多プラットフォーム UGC） |
| **v1.x** | 名称を Argo に統一、多エンジンルーティングと二層キャッシュ |

---

## 貢献

Issue と Pull Request を歓迎します。ルーティングや証拠ロジックを変えるときはテストを足してください：

```bash
python3 -m pytest tests/test_unit.py tests/test_multilingual.py -q
python3 scripts/regression_p0p1.py --offline
python3 scripts/matrix_search_eval.py --offline
python3 scripts/ab_eval_p0p1.py   # 任意、オンライン含む
```

コミット前：本物の API Key、本機絶対パス、cookie などを含めないこと。本機 Skill パスは `installs.local.yaml`（gitignore 済み）。

## License

Apache License 2.0 © 2026 [taxueseek](https://github.com/taxueseek)

<p align="center">
  <a href="https://github.com/oil-oil/beautify-github-readme"><img src="assets/readme/made-with-beautify.svg" width="300" alt="README made with beautify-github-readme"></a>
</p>

---

> 良い検索は、もっと多く見せることではない。自信を持って結論できること——そしてまだ結論してはいけないときを知ることだ。
