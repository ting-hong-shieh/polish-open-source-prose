<p align="center">
  <img src="docs/assets/readme-banner.svg" alt="Polish Open-Source Prose 字標——保留事實與作者聲音的開源專案文字編輯 skill" width="100%">
</p>

<p align="center">
  <a href="README.md">English</a>
  ·
  <a href="#快速開始">快速開始</a>
  ·
  <a href="#我們怎麼測試">我們怎麼測試</a>
  ·
  <a href="CONTRIBUTING.md">參與貢獻</a>
</p>

<p align="center">
  <a href="https://github.com/ting-hong-shieh/polish-open-source-prose/actions/workflows/validate.yml"><img src="https://github.com/ting-hong-shieh/polish-open-source-prose/actions/workflows/validate.yml/badge.svg?branch=main" alt="驗證狀態"></a>
  <img src="docs/assets/logo-badge.svg" alt="Polish Open-Source Prose">
  <img src="https://img.shields.io/badge/locale-zh--Hant--TW-4338ca?style=flat-square" alt="zh-Hant-TW locale pack">
  <img src="https://img.shields.io/badge/forward_cases-49-0f766e?style=flat-square" alt="49 個前向案例">
  <img src="https://img.shields.io/badge/license-Apache--2.0-2563eb?style=flat-square" alt="Apache-2.0 授權">
</p>

請模型「潤飾」一段文字，它幾乎一定會改點什麼，即使原文沒有問題。我們測試時，
現在的模型自己就會刪宣傳語、選對台灣用詞，但也會把英文授權條款翻成中文、在資安
政策裡加上原文沒有的規定，或把已經清楚的句子換個說法。

這個 skill 就是用來踩煞車的：清楚的文字原樣交回，必須精確的內容不動，缺的事實
向作者提問而不是自己編。它不負責讓文字更像人寫的，那件事現在的模型自己就做得到。

它是一個 [Agent Skill](https://agentskills.io)，適用於 README、文件、release note、
changelog、PR、issue、程式碼註解、UI 文案與錯誤訊息，可在 Claude Code 與 Codex 上
執行。

## 它防止什麼

以下每個例子都列出原文、Claude Opus 5.5 在沒有 skill 時的輸出，以及加上 skill 後的
輸出。例子都來自[測試案例](skills/polish-open-source-prose/tests/forward_cases.json)，
測試方式見[我們怎麼測試](#我們怎麼測試)。

### 授權條款不翻譯

> THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND.

| 沒有 skill | 有 skill |
| --- | --- |
| 本軟體係依「現狀」提供，不附帶任何形式之擔保。 | 原文不變，並說明這是授權條款，翻譯可能改變法律效力。 |

指定目標語系是 `zh-Hant-TW`，不代表法律文字要跟著翻。兩輪沒有 skill 的測試都翻成了
中文。

### 資安政策不加料

> 請勿公開 issue；請寄信到 `security@example.com`，並至少等待 90 天。

| 沒有 skill | 有 skill |
| --- | --- |
| 若發現安全性漏洞，請勿建立公開的 issue，請寄信至 `security@example.com` 回報。自回報日起至少 90 天內，請勿公開揭露相關細節。 | 原文不變。 |

原文只說「至少等待 90 天」，沒有說從哪天起算，也沒有說等待的是「公開揭露」。沒有
skill 的版本讀起來比較完整，卻替專案定了一條原文沒有的規定。

### 清楚的句子不換說法

> API 僅在權杖過期時回傳 `401`；權限不足則回傳 `403`。

| 沒有 skill | 有 skill |
| --- | --- |
| API 只有在權杖過期時才會回傳 `401`；若權限不足，則回傳 `403`。 | 原文不變。 |

這是其中一輪的結果。意思沒變，但每次「潤稿」都換一次說法，reviewer 就得重新確認
一次條件有沒有被改掉。

### 作者的口語保留

> 這個 bug 不太正常，只有禮拜一、locale 是 `zh-Hant-TW` 的時候才會出現。
> 我先補做 regression test。

「不太正常」「禮拜一」「補做」是作者自己的說法，條件和下一步也都清楚，所以預期
結果是原文不變，也不把 regression test 翻成中文。這句是 v0.2.0 才換上的測試案例，
還沒有跑過下面的模型測試。

## 會做與不會做的事

這個 skill 會：

- 文字已經清楚、符合場景時，原樣交回；
- 保留數字、版本、條件、否定、範圍、命令、連結、識別碼、引文、授權與政策文字、
  Markdown 結構，以及作者刻意的語氣；
- 不補原文沒有的數據、測試結果、commit 或產品行為，缺的資訊在修改後列成問題；
- 沒有命令、commit 與範圍支撐時，不讓「全部測試通過」「完全修好」這類說法留著；
  對「更穩定」「效能更好」這類沒有證據的評價，刪掉或請作者補證據。

不會：

- 讓文字更像人寫的，這件事現在的模型不靠 skill 也做得到；
- 判斷一段文字是人或模型寫的，或幫文字規避 AI 偵測；
- 移除統計浮水印，或把浮水印當成身分證明；需要證明作者時，建議簽署 commit 或檔案；
- 取代法律、資安或專業領域審查；
- 解決真實 PR 裡大部分被 reviewer 批評的問題，那些問題通常需要只有作者知道的事實
  （見[我們怎麼測試](#我們怎麼測試)）。

## 台灣繁體中文

指定 `zh-Hant-TW`，或文字的讀者在台灣時，skill 會另外讀
[台灣繁體中文編輯層](skills/polish-open-source-prose/references/locales/zh-Hant-TW.md)：

- **依語境選詞：** 只列容易選錯的詞，例如 `information` 與 `message` 都可能來自
  「信息」，前者是「資訊」、後者是「訊息」。一般軟體詞彙模型自己就會選對，不列表。
- **標點：** 一般敘述用全形標點，程式碼、命令、路徑與版本號維持半形。
- **法律、資安與引文：** 逐字保留，目標語系是 `zh-Hant-TW` 也不翻譯。
- **誤判防護：** 為了可搜尋性重複的 API 名稱、平行的操作步驟、作者的口語與中英夾用，
  都不算問題。

只有「文字是繁體」並不足以推定目標是台灣。香港、澳門等其他繁體中文語系需要各自的
locale pack；新增語系的規格見 [locale pack contract](docs/locale-pack-contract.md)。

## 快速開始

### 使用 Claude Code 安裝

將這個 repository 加為 plugin marketplace，然後安裝 plugin：

```text
/plugin marketplace add ting-hong-shieh/polish-open-source-prose
/plugin install polish-open-source-prose
```

若不使用 plugin 系統，也可以直接複製 skill 目錄：

```bash
git clone https://github.com/ting-hong-shieh/polish-open-source-prose.git
cp -r polish-open-source-prose/skills/polish-open-source-prose ~/.claude/skills/
```

要讓 skill 只在單一專案生效，請改放到該專案的 `.claude/skills/`。

### 使用 Codex 安裝

呼叫 `$skill-installer`，並提出以下要求：

> 從這個 repository 的 `skills/polish-open-source-prose` 目錄安裝
> `polish-open-source-prose` skill：
> `https://github.com/ting-hong-shieh/polish-open-source-prose/tree/main/skills/polish-open-source-prose`

在本機開發期間，也可以直接使用 skill 目錄：

```text
skills/polish-open-source-prose
```

### 使用

當要求符合 skill 的 description 時，Claude Code 會自動載入。也可以直接呼叫：Claude
Code 用 `/polish-open-source-prose`，Codex 用 `$polish-open-source-prose`。例如：

```text
幫我潤這份 PR 說明，已經清楚的地方不要動。

把這份 release note 在地化成 zh-Hant-TW，不要改變產品行為。

檢查這段 README，只列出能解決具體問題的修改。
```

## 我們怎麼測試

我們把簡短的文字交給七種模型設定修改：Claude Code 上的 Claude Opus 5.5、Opus 4.6、
Sonnet 5.5，以及 Codex 上的 GPT-6.1 Sol、GPT-6 Astra（high 與 low）、GPT-6 Luna。每段
文字都在五種條件下執行：

- **沒有 skill**：只有修改指示。
- **一句話**：指示前加上「If the text is already clear and fits its surface,
  returning it unchanged is a valid answer.」
- **三句話**：指示前加上下面[不安裝 skill 的做法](#不安裝-skill-的做法)那段英文。
- **v0.1.0**、**v0.2.0**：載入該版本的 skill。

測試文字分成三組：

- **開發集**：開發 skill 時用的 49 個[測試案例](skills/polish-open-source-prose/tests/forward_cases.json)。
- **A1**：v0.2.0 發布後才寫的 24 個新案例，其中 8 個是 `zh-Hant-TW`，在任何模型執行
  前就凍結。有些原文本來就沒問題，應該原樣交回，其餘的有問題要修。
- **A2**：Apache Airflow、Arrow、DataFusion 與 CPython 的 21 篇真實 PR 標題與說明，
  取的是被 reviewer 批評之前的版本，全部是英文。原文不公開，網址與雜湊值記錄在
  [`evals/heldout/a2_manifest.json`](evals/heldout/a2_manifest.json)。

每份輸出都用字串比對檢查；A1 與 A2 的輸出另外由 Claude Opus 5.5 與 GPT-6.1 Sol 在不
知道模型與條件的情況下評分。「乾淨修正」是指修好問題、而且沒有加入原文沒有的事實、
也沒有改壞必要內容的程度。完整的方法與結果在[報告](docs/report/report.pdf)裡（英文）。

以下是七種設定的平均；有範圍時代表兩位評審的結果：

| | 沒有 skill | 一句話 | 三句話 | v0.1.0 | v0.2.0 |
| --- | --- | --- | --- | --- | --- |
| A1 中文：清楚的文字原樣交回 | 0% | 34% | 61% | 18% | 70% |
| A1 中文：乾淨修正（0 到 1） | 0.52–0.62 | 0.54–0.61 | 0.46–0.49 | 0.74–0.85 | 0.79–0.88 |
| A2：乾淨修正（0 到 1） | 0.12–0.15 | 0.15–0.18 | 0.07–0.10 | 0.22–0.25 | 0.18–0.19 |
| A2：改寫時加入事實的比例 | 21–38% | 9–22% | 0–5% | 8–18% | 0–1% |

A1 的中文案例只有 4 題原樣交回、4 題需要修改，數字只能參考。

這代表：

- 沒有任何提醒時，每個模型都幾乎把每段本來就沒問題的文字改掉。
- 加一句或三句提醒就能少掉大部分不必要的修改，三句比一句有效。如果你只需要模型別
  亂改，下面那段提醒可能就夠了。
- 三句提醒也會讓模型留下沒有根據的說法，例如只在 macOS 上跑過 `make test`，卻寫成
  「所有平台都沒有問題」；v0.2.0 修掉這類問題的次數多得多。skill 多出來的，是告訴模型哪些問題值得改。台灣用詞方面，
  模型自己就會選對。
- 真實 PR 上，沒有任何條件能乾淨修好超過約四分之一的問題，因為多數批評需要只有作者
  知道的事實。v0.2.0 主要的作用是不把事情弄得更糟：沒有提醒時，改寫常加入原文沒有
  的事實，70 份輸出中有 10 份改動或刪掉了作者的 `Generated-by:` AI 揭露行；用
  v0.2.0 時一份都沒有。
- v0.1.0 在真實 PR 上修好的問題比 v0.2.0 多一些，主要是說明不清楚和標題誤導；21 題
  的差異不顯著。
- 在 Claude Code 上，用 v0.2.0 每次執行的成本是不用 skill 的 2.5 到 3.3 倍。GPT-6
  Luna（max）約有一半的清楚文字還是被改掉。

這不代表：

- 開發集與 A1 是我們自己寫的。A1 由 Claude Opus 5.5 起草，而它同時是受測模型與評審
  之一。
- A2 只有四個專案的 21 篇英文 PR。
- 字串比對會漏掉措辭不同的好修改，評審也是模型。
- Claude 的設定各跑兩輪、Codex 的設定各跑一輪，兩段提醒也只用英文寫過一次。

<details>
<summary>開發集結果（28 個中文案例、三個模型）</summary>

這些是在保留測試之前跑的，只用了三個模型：Claude Opus 5.5 在 Claude Code 上每種條件
跑兩輪，GPT-6.1 Sol 與 GPT-6 Astra 在 Codex 上各跑一輪。一格有兩個數字時，代表兩輪
的結果。開發 v0.2.0 時，我們修正了幾個「需要修改」案例的預期結果，所以 v0.2.0 在第二
張表上有主場優勢；這些數字只能當回歸檢查。

**應該原樣交回的文字（11）**

| 模型 | 沒有 skill | 一句話 | 三句話 | v0.1.0 | v0.2.0 |
| --- | --- | --- | --- | --- | --- |
| Claude Opus 5.5 | 0、1 | 8、7 | 9、8 | 8、8 | 11、11 |
| GPT-6.1 Sol | 0 | 5 | 8 | 5 | 10 |
| GPT-6 Astra | 0 | 4 | 8 | 4 | 10 |

**需要修改的文字（15）**

| 模型 | 沒有 skill | 一句話 | 三句話 | v0.1.0 | v0.2.0 |
| --- | --- | --- | --- | --- | --- |
| Claude Opus 5.5 | 12、10 | 13、12 | 11、11 | 13、12 | 13、13 |
| GPT-6.1 Sol | 8 | 8 | 8 | 13 | 12 |
| GPT-6 Astra | 8 | 8 | 11 | 10 | 11 |

另外 2 個案例是來源證明問題，不列在表中。跑測試時，「作者的口語」那題用的還是舊
句子。

</details>

### 不安裝 skill 的做法

如果你只想讓模型別再改動本來就沒問題的文字，可以在要求前加上這段：

```text
Polish this text only where there is a concrete problem. Leave already-clear text
unchanged. Preserve facts, scope, conditions, negation, commands, links, quotations,
and author voice. Do not invent missing facts.
```

代價是它可能會漏改一些該改的地方。

## 開發

執行完整 repository 驗證：

```bash
python3 scripts/validate_repo.py
```

直接執行 skill 驗證：

```bash
python3 skills/polish-open-source-prose/scripts/validate_skill.py
```

這些是結構檢查：確認每個測試案例格式正確、受保護的字串同時出現在原文與預期結果、
連結都能開。它們不會呼叫模型。

<details>
<summary><strong>Repository 目錄</strong></summary>

```text
.
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── .codex-plugin/plugin.json
├── docs/
│   ├── assets/
│   └── locale-pack-contract.md
├── scripts/validate_repo.py
└── skills/
    └── polish-open-source-prose/
        ├── SKILL.md
        ├── agents/openai.yaml
        ├── references/
        ├── scripts/
        └── tests/
```

每個平台各自讀取自己的 manifest 目錄與共用的 `skills/`，因此新增平台不會讓編輯
內容產生分支。給使用者看的 repository 文件放在 skill 目錄外，避免被當成 agent 指令
載入。

</details>

## 參與貢獻

提出新規則或新語系前，請先讀 [CONTRIBUTING.md](CONTRIBUTING.md)。最有幫助的貢獻是：

- skill 改了不該改的文字；
- skill 留下沒有根據的說法，或補了原文沒有的事實；
- 可以公開散布的真實專案文字，做成測試案例；
- 母語使用者審查語系編輯層。

## 緣起

這個專案最早是從 [stop-slop](https://github.com/hardikpandya/stop-slop) 與幾個台灣的
「去 AI 味」專案出發：[speak-human-tw](https://github.com/Raymondhou0917/speak-human-tw)、
[Humanizer-zh-TW](https://github.com/kevintsai1202/Humanizer-zh-TW)、
[humanizer-zh-tw](https://github.com/nagameTW/humanizer-zh-tw) 與
[Humanizer-zh-TW-Pro](https://github.com/slivenred/humanizer-zh-TW-Pro)。測試後發現，
現在的模型自己就能做到其中大部分，所以 v0.2.0 拿掉了詞表，只留下防止模型改過頭的
規則。早期版本包含哪些第三方內容，見 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 授權

Apache-2.0，詳見 [LICENSE](LICENSE)。
