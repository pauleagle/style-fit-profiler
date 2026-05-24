# EXP-001: Gemini Image Analysis Extractor

狀態：Post-P0 Experimental Spec，experimental extractor 已完成；仍為 opt-in，尚未取代 baseline default。
前置條件：Phase 0 baseline 已完成並驗證；manual Gemini image probe 已跑通。

Intent：

- 將已驗證可用的 `gemini_image_probe.py` 拆成正式、opt-in 的 Phase 0 experimental extractor。
- 使用 Google Gemini multimodal API 分析本機 reference images，輸出可轉換成 `StyleGeneCandidate` 的三面向候選 genes。
- 保留 deterministic mock extractor 作為 baseline default；Gemini extractor 僅在明確設定或手動命令下啟用。

背景：

- 手動 probe 已能讀取本機圖片、使用 `GEMINI_API_KEY` 呼叫 Gemini REST `generateContent`，並取得符合 Phase 0 三面向的 JSON。
- Probe 實測回傳包含 `rendering`、`color_light`、`texture_artifacts` 與 `notes`。
- 目前 probe 是人工工具，尚未納入 `run_phase0` production path，也尚未把 Gemini JSON 轉成正式 `StyleGeneCandidate` records。

Scope：

- 新增 Gemini response parser，將模型回傳 JSON 正規化成：
  - `rendering`
  - `color_light`
  - `texture_artifacts`
  - `notes`
- 新增 Gemini-to-candidate mapper，把每個 trait 轉成 `StyleGeneCandidate`。
- 新增 opt-in Gemini extractor，符合既有 `Phase0Extractor` interface。
- Gemini extractor input 必須仍是 reference image manifest records。
- Gemini extractor output 必須通過 P0-06 candidate schema validator 與 P0-09 aspect classification validator。
- Gemini extractor 不得直接寫入 `style_gene_pool.json`。

Non-goals：

- 不取代 deterministic mock extractor 作為預設 baseline。
- 不在 unit tests 中呼叫真實 Gemini API。
- 不加入 human approval UI。
- 不處理 candidate genes 合併到 `style_gene_pool.json`。
- 不處理 Gemini API billing / quota 管理 UI。
- 不承諾模型回傳的 artist、character、copyright 或 private identity 判定可信。

Input contract：

- `GEMINI_API_KEY` 必須由環境變數提供，不得寫入 repo、config、README 或 SPEC 範例 key。
- Reference image path 來自 manifest record 的 `path` 欄位。
- 圖片可先使用 inline image data；若圖片或 request 超過 Gemini inline limit，後續再拆 File API flow。
- 每次 extractor call 必須保留 source image relative path，供 candidate traceability 使用。

Output contract：

- 每個 Gemini trait 轉成一個 `StyleGeneCandidate`。
- Candidate ID 必須穩定、可重現，並符合 aspect prefix，例如：
  - `rendering_anime_art_style_<digest>`
  - `color_light_vibrant_colors_<digest>`
  - `texture_artifacts_smooth_textures_<digest>`
- `prompt` 使用 Gemini trait 的清理後文字，不應包含空字串。
- `confidence` 初版可使用固定 experimental default，例如 `0.5`，直到後續 spec 定義信心分數來源。
- `source_images` 必須包含原始 reference image relative path。
- `notes` 可記錄 `gemini experimental extractor` 與模型名稱，避免和 deterministic mock output 混淆。

Validation requirements：

- Parser tests 使用 fixture Gemini response，不打真 API。
- Mapper tests 覆蓋：
  - 三個合法 aspects。
  - 空 trait list。
  - trait slug / candidate ID 穩定性。
  - duplicate trait 或 duplicate ID 處理。
  - invalid / missing aspect response。
- Extractor tests 使用 fake Gemini client，確認：
  - input 來自 manifest records。
  - output 可通過 P0-06 / P0-09 validators。
  - API failure 會回報清楚 error，且不改動 `style_gene_pool.json`。
- Manual integration probe 可保留為非 CI 驗證，不納入預設 unittest。

Candidate experimental atomic items：

- `EXP-001A`: Gemini response parser
  - 狀態：已完成。
  - 完成依據：baseline tests 通過；fixture tests 覆蓋 valid JSON、invalid JSON、missing aspect、unknown key、非 list traits、空白 / 非字串 trait 與 invalid notes。
  - 將 Gemini JSON text parse 成三面向 traits。
  - 拒絕 invalid JSON、missing aspect、unknown aspect 或非 list traits。
- `EXP-001B`: Gemini trait-to-candidate mapper
  - 狀態：已完成。
  - 完成依據：baseline tests 通過；mapper tests 覆蓋 schema-valid candidate output、stable candidate ID、source image traceability、duplicate trait handling 與 missing / unknown aspect failure paths。
  - 將 traits 轉成 stable `StyleGeneCandidate` records。
  - 保留 source image relative path。
- `EXP-001C`: Gemini API client wrapper
  - 狀態：已完成。
  - 完成依據：baseline tests 通過；client wrapper tests 覆蓋 injected payload builder、injected transport、response text extraction 與 transport error propagation，unit tests 不呼叫真實 Gemini API。
  - 抽出目前 probe 的 REST call 與 image inline payload builder。
  - 支援 dependency injection，讓 tests 不打真 API。
- `EXP-001D`: Opt-in Gemini Phase 0 extractor
  - 狀態：已完成。
  - 完成依據：baseline tests 通過；extractor tests 覆蓋 manifest-record input、fake Gemini client、P0-06 / P0-09 compatible output、explicit run_phase0 opt-in、API failure source traceability 與 no gene pool overwrite。
  - 實作符合 `Phase0Extractor` 的 extractor。
  - 明確 opt-in，不改 deterministic mock default。
- `EXP-001E`: Manual integration command
  - 狀態：已完成。
  - 完成依據：baseline tests 通過；manual command tests 覆蓋 CLI options、missing `GEMINI_API_KEY` guard 與 fake-client raw output path；README 已文件化 PowerShell 指令、環境變數與安全注意事項。
  - 保留或整理 `gemini_image_probe.py` 作為手動驗證入口。
  - 文件化本機圖片測試指令、環境變數與安全注意事項。
- `EXP-001F`: Manual Gemini batch command
  - 狀態：已完成。
  - 完成依據：baseline tests 通過；batch command tests 覆蓋 CLI options、missing `GEMINI_API_KEY` guard、multi-image batch request、per-image analysis output path、partial failure report 與 non-zero exit code；README 已文件化 PowerShell 指令、輸出位置與安全注意事項。
  - 新增 `gemini_batch_probe.py` 作為手動批次驗證入口。
  - 每個 batch 以一次 multi-image Gemini request 送出多張 reference images，但回傳後必須逐圖記錄 analysis result，避免 Phase 0 提前整合跨圖 traits。
  - 輸出 `reference_image_manifest.json`、逐圖 `reference_image_analysis.json`、相容投影 `style_gene_candidates.json` 與 `batch_run_report.json`。

Open questions：

- Gemini extractor 應透過 config 啟用，還是先只提供 CLI/manual command？
- 初版 `confidence` 應固定為 experimental default，還是從模型 response 中要求自評分數？
- Gemini 回傳的 broad traits 是否需要 human review 後才可合併到 candidate output？
- 大圖是否立即支援 File API，或先限制 inline request size？
