# EXP-003: Colab Notebook Wrapper for Phase 0

狀態：Post-P0 Experimental Spec，experimental notebook wrapper helpers 已完成；仍為 opt-in，尚未成為正式 production entrypoint。
前置條件：Phase 0 baseline 已完成並驗證；至少一個可重現的本機 Phase 0 flow 已跑通。

CR-001-FU-01 status note：

- 本 spec 的 notebook wrapper 目前包裝 deterministic / legacy Phase 0 candidate
  schema flow，主要用於 preview、export、demo 與 review。
- Notebook 產出的 `style_gene_candidates.json` 不是 CR-001 primary artifact；CR-001
  manual Gemini default 的 primary artifact 是
  `phase0/cr001_reference_image_analysis.json`。
- 若 notebook 未來要支援 CR-001 native artifacts 或 CR-001-to-legacy projection，
  必須另走 accepted spec，不可由本 EXP-003 wording 隱含承諾。

Intent：

- 提供一個 Colab-friendly 的 wrapper，讓使用者可在 notebook 介面中執行 Phase 0 reference image analysis。
- 讓 upload, analysis, preview, export 與 download 這些步驟對非 CLI 使用者更容易操作。
- 保留核心 Phase 0 邏輯在本地或可重用的 library code 中，避免 notebook 成為唯一執行路徑。

背景：

- Phase 0 早期驗證常需要快速展示 reference image analysis、候選 genes 與輸出檔案。
- Notebook wrapper 的價值在於把 existing flow 包裝成可逐 cell 操作的教學 / demo / review 介面，而不是新增另一套 business logic。
- Colab 環境對檔案系統、環境變數與長時間運算都有額外限制，因此 wrapper 應優先考慮最小依賴與可中斷性。

Scope：

- 新增 notebook wrapper cells，涵蓋：
  - runtime setup
  - reference image upload
  - Phase 0 config loading
  - batch 或單張 analysis trigger
  - candidate preview
  - output download
- 新增 notebook-friendly helper functions，讓核心 Phase 0 流程可被 notebook 重用。
- 新增暫存資料夾與輸出下載流程，確保 notebook 執行結果可導出到本機。
- 新增可選的 notebook status display，方便查看每個 reference image 與 batch 的處理狀態。

Non-goals：

- 不把 notebook wrapper 當作正式 production entrypoint。
- 不在 notebook 中硬編碼任何 API key。
- 不讓 notebook 取代 CLI、自動化測試或 library API。
- 不在 notebook 中加入 human approval workflow。
- 不在 notebook 中直接修改 `style_gene_pool.json`。
- 不保證 Colab runtime 與本機 runtime 的完全一致性。

Input contract：

- Notebook 必須明確區分 uploaded files、local cached files 與 analysis outputs。
- API key 或其他敏感資訊只能透過 notebook runtime secrets 或環境變數注入。
- Notebook wrapper 必須可以接受既有 `style_profiler_config.json` 或其等價輸入。
- 若 notebook 需要 reference images，應支援單張上傳與多張上傳兩種情境。

Output contract：

- Notebook 應產生與 deterministic / legacy Phase 0 flow 相同語意的輸出：
  - `reference_image_manifest.json`
  - `style_gene_candidates.json`（deterministic / legacy Phase 0 candidate schema）
  - batch / run metadata
- Notebook wrapper 應保留輸出下載入口，讓使用者能將 analysis artifacts 匯出到本機。
- Notebook 中的 preview 不得改變正式輸出內容。
- 所有 notebook 產出的 candidate genes 仍必須通過既有 schema validator。

Validation requirements：

- Notebook cell tests 或 smoke checks 必須覆蓋：
  - config loading
  - image upload handling
  - analysis trigger
  - output generation
  - download/export path
- Notebook wrapper tests 必須使用 fake backend 或 mock analysis，不依賴真實 Colab runtime。
- Notebook wrapper 不得破壞 deterministic mock baseline。

Candidate experimental atomic items：

- `EXP-003A`: Notebook runtime bootstrap
  - 狀態：已完成。
  - 完成依據：baseline tests 通過；notebook bootstrap tests 覆蓋 Colab runtime setup cell、dependency check cell、ipynb-serializable bootstrap document 與 no hardcoded secret values。
  - 建立 Colab runtime setup 與依賴初始化 cell。
- `EXP-003B`: Upload and staging helper
  - 狀態：已完成。
  - 完成依據：baseline tests 通過；upload/staging tests 覆蓋 Colab upload bytes staging、manifest generation、unsupported upload rejection、duplicate staged name rejection 與 no hardcoded secret values。
  - 處理 reference image upload、暫存與 manifest generation。
- `EXP-003C`: Notebook analysis runner
  - 狀態：已完成。
  - 完成依據：baseline tests 通過；analysis runner tests 覆蓋 config loading、single Phase 0 flow、batch wrapper flow、mock analyzer output 與 notebook analysis cell generation。
  - 在 notebook 中呼叫 Phase 0 analysis flow，支援 mock backend 與 batch wrapper。
- `EXP-003D`: Preview and export cells
  - 狀態：已完成。
  - 完成依據：baseline tests 通過；preview/export tests 覆蓋 candidate preview rows、invalid candidate schema rejection、preview 不修改正式輸出、export manifest、download zip 與 Colab preview/export cells。
  - 顯示候選 genes、輸出 manifest，並提供下載路徑。
- `EXP-003E`: Notebook smoke tests
  - 狀態：已完成。
  - 完成依據：baseline tests 通過；smoke tests 覆蓋 package-level notebook helper exports、完整 Colab notebook document serialization，以及 upload → batch analysis → preview → export 的 deterministic mock flow。
  - 驗證 wrapper 不破壞核心 Phase 0 contract。

Open questions：

- Notebook wrapper 應只面向 Colab，還是也要兼容本機 Jupyter？
- Upload 後的 staging file 命名應以原檔名為主，還是以穩定 digest 為主？
- Notebook 是否需要一鍵產生可下載 zip，包含 manifests 與 analysis artifacts？
- Wrapper 應直接呼叫現有 CLI/library，還是先定義更薄的 notebook-specific adapter？
