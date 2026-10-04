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
- 取代法律、資安或專業領域審查。

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

repository 裡有 49 個簡短的測試案例，內容是開源專案常見的文字：README 段落、PR
說明、review 回覆、commit message、程式碼註解、錯誤訊息。每個案例記錄原文與預期
結果；有些原文本來就沒問題，應該原樣交回，其餘的需要修改。

我們把每段文字交給三個模型修改，比較五種條件：

- **沒有 skill**：只有修改指示。
- **一句話**：指示前加上「If the text is already clear and fits its surface,
  returning it unchanged is a valid answer.」
- **三句話**：指示前加上下面[不安裝 skill 的做法](#不安裝-skill-的做法)那段英文。
- **v0.1.0**、**v0.2.0**：載入該版本的 skill。

Claude Opus 5.5 在 Claude Code 上每種條件跑兩輪；GPT-6.1 Sol 與 GPT-6 Astra 在
Codex 上每種條件跑一輪。同一個模型在每種條件收到的指示都相同，但不同模型之間的指示
措辭略有差異，所以請橫向比較同一列，不要比較不同模型。

以下是 28 個 `zh-Hant-TW` 案例的結果。一格有兩個數字時，代表兩輪的結果。

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

這代表：

- 沒有任何提醒時，每個模型都幾乎把每段本來就沒問題的文字改掉。
- 加一句或三句提醒就能少掉大部分不必要的修改，三句比一句有效。如果你只需要模型
  別亂改，下面那段提醒可能就夠了。
- 中文題目上，三句提醒對需要修改的文字影響不大；但在英文題目上，它讓每個模型都
  漏改了不少該改的地方（見英文 README）。
- v0.2.0 讓清楚的文字原樣交回，同時仍然改掉該改的地方。skill 多出來的，是告訴模型
  哪些問題值得改。台灣用詞方面，模型自己就會選對。

這不代表：

- 案例和預期結果都是我們自己寫的，評分只檢查特定字詞有沒有出現，不是判斷文字好壞。
- 開發 v0.2.0 時，我們修正了幾個「需要修改」案例的預期結果，也看過這些案例的失敗
  後才補上規則，所以 v0.2.0 在第二張表上有主場優勢。「應該原樣交回」的預期結果沒有
  改過。
- 每個模型只跑一到兩輪，兩段提醒也都是英文。

所以這些數字只能當回歸檢查，不是 benchmark。

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
