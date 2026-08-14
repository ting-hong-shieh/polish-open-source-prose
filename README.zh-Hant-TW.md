<p align="center">
  <img src="docs/assets/readme-banner.svg" alt="Polish Open-Source Prose 字標——保留事實與作者聲音的開源專案文字編輯 skill" width="100%">
</p>

<p align="center">
  <a href="README.md">English</a>
  ·
  <a href="#快速開始">快速開始</a>
  ·
  <a href="#語系支援">語系支援</a>
  ·
  <a href="CONTRIBUTING.md">參與貢獻</a>
</p>

<p align="center">
  <a href="https://github.com/ting-hong-shieh/polish-open-source-prose/actions/workflows/validate.yml"><img src="https://github.com/ting-hong-shieh/polish-open-source-prose/actions/workflows/validate.yml/badge.svg?branch=main" alt="驗證狀態"></a>
  <img src="docs/assets/logo-badge.svg" alt="Polish Open-Source Prose">
  <img src="https://img.shields.io/badge/locale-zh--Hant--TW-4338ca?style=flat-square" alt="zh-Hant-TW locale pack">
  <img src="https://img.shields.io/badge/forward_cases-43-0f766e?style=flat-square" alt="43 個前向案例">
  <img src="https://img.shields.io/badge/license-Apache--2.0-2563eb?style=flat-square" alt="Apache-2.0 授權">
</p>

> 一套用來編輯 README、文件、release note、貢獻指南、PR、issue、UI 文案、
> 錯誤訊息與 prompt 的 agent skill；它不把禁詞表或偵測器分數當成文風準則。
> 可在 Claude Code 與 Codex 上執行。

<table>
  <tr>
    <td width="33%">
      <strong>保留原意</strong><br>
      保護事實、數字、版本、條件、否定、引用來源、因果、命令、連結、引文與
      Markdown 結構。
    </td>
    <td width="33%">
      <strong>符合文件場景</strong><br>
      README、教學、PR、release note、錯誤訊息與政策文件使用不同的編輯標準。
    </td>
    <td width="33%">
      <strong>尊重地區語系</strong><br>
      依語境處理地區詞彙與誤判，不用一份通用取代清單套用所有語言。
    </td>
  </tr>
</table>

## 快速開始

skill 目錄採用 [Agent Skills](https://agentskills.io) 格式，同一份檔案可以在
Claude Code 與 Codex 上使用。

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

### 呼叫 skill

當要求符合 skill 的 description 時，Claude Code 會自動載入。也可以直接呼叫：

```text
/polish-open-source-prose
```

在 Codex：

```text
$polish-open-source-prose
```

可以從以下要求開始：

```text
稽核這份 README，只提出有證據支持的修改。

將這份 release note 在地化為 zh-Hant-TW，不要改變產品行為。

檢查這份 PR 說明是否有無依據聲明或遺失限定條件。
```

## 運作方式

1. **確認事實來源。** 先檢查程式碼、測試、設定與專案詞彙，不直接相信宣傳文字。
2. **鎖定語意限制。** 保護事實、限定詞、識別碼、引文、法律文字、命令、連結與
   Markdown 結構。
3. **診斷具體問題。** 處理含糊、無依據聲明、主體不明、邏輯中斷、機械式重複，
   以及文件場景或地區語系不合。
4. **比對修改前後。** 交付前逐項比較主詞、數字、版本、條件、否定、引用來源、
   因果與操作順序。

如果文字已經清楚、具體，而且符合作者聲音，skill 會保留原文。被動句、排比、
片段、設問、破折號或工整句型本身都不是問題。

## 保護範圍

| 項目 | 範例 |
| --- | --- |
| 語意 | 主詞、範圍、比較、條件、例外、不確定性 |
| 證據 | 數字、日期、版本、引用來源、因果聲明 |
| 技術文字 | 命令、參數、API、識別碼、路徑、URL、錯誤字串 |
| 引文與規範 | 引文、引用、授權、政策、安全步驟 |
| 結構 | 標題、錨點、表格、清單、程式碼區塊、預留位置、frontmatter |
| 聲音 | 刻意的幽默、社群詞彙、語域與第一人稱立場 |

## 語系支援

| 語系 | 狀態 | 範圍 |
| --- | --- | --- |
| 英文 | 共通規則 | 開源文字編輯訊號與文件場景 |
| 中文 | 共通規則 | 中文編輯訊號與語意保真 |
| `zh-Hant-TW` | 專用 locale pack | 台灣詞彙、標點、語域與前向案例 |
| 其他語系 | 只有共通基礎 | 仍需母語 locale pack 與審查 |

[Locale pack contract](skills/polish-open-source-prose/references/locale-pack-contract.md)
規定新增語言與地區時需要的證據、詞彙、誤判防護、文件場景與測試。這份規格也
預留給未來的 PolyglotGuard 檢查器使用。

## 邊界

本專案不會：

- 判定一段文字是人或模型寫的；
- 為了規避 AI 偵測器而改寫文字；
- 承諾移除統計浮水印；
- 捏造數據、產品行為、使用者故事、作者立場或個人經驗；
- 宣稱支援尚未建立並審查的語系；
- 取代法律、安全或專業領域審查。

需要證明作者來源時，skill 會建議簽署 canonical artifact，不把文風或統計浮水印
當成身分證明。

## 驗證

執行完整 repository 驗證：

```bash
python3 scripts/validate_repo.py
```

直接執行 skill 驗證：

```bash
python3 skills/polish-open-source-prose/scripts/validate_skill.py
```

目前有 43 個前向規格：17 個案例應保持不變，26 個案例應修改或提供來源證明建議。
結構檢查可以找出受保護內容漂移與案例格式錯誤，但真實專案文字仍需母語使用者
審查。

<details>
<summary><strong>Repository 目錄</strong></summary>

```text
.
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── .codex-plugin/plugin.json
├── docs/assets/
├── scripts/validate_repo.py
└── skills/
    └── polish-open-source-prose/
        ├── SKILL.md
        ├── agents/openai.yaml
        ├── references/
        ├── scripts/
        └── tests/
```

每個平台各自讀取自己的 manifest 目錄與共用的 `skills/`，因此新增平台不會讓
編輯內容產生分支。

給使用者看的 repository 文件放在 skill 目錄外，避免它們被當成 agent 指令載入。

</details>

## 參與貢獻

提出廣泛編輯規則或新 locale 前，請先閱讀
[CONTRIBUTING.md](CONTRIBUTING.md)。特別有幫助的貢獻包括：

- 誤判案例；
- 缺少的語意保護；
- 依語境處理的地區詞彙；
- 可以重新散布的範例；
- 平衡的「應修改／不應修改」前向案例；
- locale pack 的母語審查。

## 授權與致謝

本 repository 的原創貢獻採 Apache-2.0。源自 `hardikpandya/stop-slop` 的內容
仍依 MIT 授權。詳情請見
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 與
[LICENSE.stop-slop](skills/polish-open-source-prose/LICENSE.stop-slop)。

設計過程參考了
[stop-slop](https://github.com/hardikpandya/stop-slop)、
[speak-human-tw](https://github.com/Raymondhou0917/speak-human-tw)、
[Humanizer-zh-TW](https://github.com/kevintsai1202/Humanizer-zh-TW)、
[humanizer-zh-tw](https://github.com/nagameTW/humanizer-zh-tw) 與
[Humanizer-zh-TW-Pro](https://github.com/slivenred/humanizer-zh-TW-Pro) 的公開成果。
