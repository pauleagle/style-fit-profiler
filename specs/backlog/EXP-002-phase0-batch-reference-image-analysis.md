# EXP-002: Phase 0 Batch Reference Image Analysis

狀態：Post-P0 Experimental Spec，experimental batch analyzer helpers 已完成；仍為 opt-in，尚未取代 baseline default。
前置條件：Phase 0 baseline 已完成並驗證；至少一個單張 reference image analysis flow 已跑通。

Intent：

- 在既有 Phase 0 reference image analysis 之上，提供 batch-oriented 的分析 wrapper，讓多張 reference images 可以依固定批次處理。
- 將每一批 reference images 以一次 batch request 處理，但每張 image 的分析結果必須先分開保存；跨圖整合留到後續 phase 或人工審查。
- 保留 deterministic mock baseline，避免 batch orchestration 影響單張分析可測性。

背景：

- 單張 reference image analysis 適合早期驗證，但實務上常會遇到較大量圖片、需要分批送入模型或分段處理的情境。
- Batch wrapper 的目標不是改變 Phase 0 的輸出契約，而是把 reference images 的輸入流程、分批策略、錯誤隔離與結果彙總流程標準化。
- 這個 experimental spec 應支援未來不同 provider 的 batch flow，但不綁定特定 vision backend。

Scope：

- 新增 batch planner，將 reference image manifest records 分組成可處理的 batch。
- 新增 batch runner，逐批執行 analysis，並保留 batch index、batch size、batch input paths 與 batch-level status。
- 新增 batch result aggregator，將各批結果正規化成三個 aspects：
  - `rendering`
  - `color_light`
  - `texture_artifacts`
- 新增 per-image analysis artifact，讓每張 reference image 的 traits、notes、batch index 與 status 可獨立追蹤。
- 新增 batch failure isolation，避免單一 batch 失敗破壞其他 batch 的可用輸出。
- 新增 batch-level traceability，讓每個 candidate gene 都能 trace back 到至少一個 batch 與一張 source image。
- 支援 deterministic mock batch analysis，供 tests 與 early CLI 使用。

Non-goals：

- 不取代單張 Phase 0 analysis contract。
- 不在 unit tests 中依賴真實 image analysis API。
- 不直接覆蓋 `style_gene_pool.json`。
- 不處理 human approval UI。
- 不承諾 batch size 會自動最佳化或自動避開 provider quota。
- 不在此階段定義多 provider routing policy。

Input contract：

- Input 仍來自 reference image manifest records。
- Batch planner 必須以相對路徑或 manifest record reference 作為輸入，不可自行重新掃描原始目錄。
- Batch size 與 batch ordering 必須可配置或可重現，避免同一組輸入在 mock mode 下產生不穩定結果。
- 若某張 image 超出單批處理限制，wrapper 必須將其拆到後續 batch 或回報 spec-defined error。

Output contract：

- 每個 batch 必須產生 batch record，至少包含：
  - batch index
  - input reference image paths
  - batch status
  - batch-level error（若失敗）
  - batch output paths
- Manual Gemini batch flow 必須輸出 `phase0/reference_image_analysis.json`，其中每張 image 各自保留：
  - reference image path
  - batch index
  - analysis status
  - model
  - per-aspect traits
  - notes 或 error
- Aggregated output 必須維持 Phase 0 candidate schema：
  - `version`
  - `source`
  - `aspects`
- 在 Gemini batch flow 中，`style_gene_candidates.json` 只是 Phase 0 candidate schema 的相容投影，不代表已完成跨圖整合。
- `source` 應能辨識為 batch analysis flow，而不是單張 probe flow。
- 每個 candidate gene 的 `source_images` 必須保留原始 reference image relative path。
- 若同一 trait 由多個 batch 提出，aggregator 必須能保留去重或合併後的穩定 ID 規則。

Validation requirements：

- Parser / aggregator tests 使用 fixture batch outputs，不打真 API。
- Batch planner tests 必須覆蓋：
  - 空 input
  - 單批處理
  - 多批處理
  - 不同 batch size
  - 非法 batch size
- Batch runner tests 必須覆蓋：
  - 某一 batch 失敗時其他 batch 仍可完成
  - batch status 正確寫入
  - deterministic ordering
- Aggregator tests 必須覆蓋：
  - aspect 分流正確
  - duplicate candidate 處理
  - missing aspect / invalid schema 的失敗路徑
  - traceability 保留 source image relative paths

Candidate experimental atomic items：

- `EXP-002A`: Batch planner
  - 狀態：已完成。
  - 完成依據：baseline tests 通過；planner tests 覆蓋 empty input、single batch、multiple batches、不同 batch size、invalid batch size 與 deterministic ordering rule。
  - 將 manifest records 分組成 deterministic batches。
  - 支援可配置 batch size 與 ordering rule。
- `EXP-002B`: Batch runner
  - 狀態：已完成。
  - 完成依據：baseline tests 通過；runner tests 覆蓋 completed / failed batch status、batch-level error、failure 後續批次仍執行與 planner deterministic ordering。
  - 執行每一批 analysis，並記錄 batch-level status 與 error。
  - 支援 fake client 與 mock backend。
- `EXP-002C`: Batch result aggregator
  - 狀態：已完成。
  - 完成依據：baseline tests 通過；aggregator tests 覆蓋 aspect merge、batch-specific source、duplicate candidate source_images merge、missing aspect 與 invalid schema failure paths。
  - 將多批結果合併成單一 Phase 0 candidate output。
  - 維持三面向 aspect contract。
- `EXP-002D`: Batch failure isolation
  - 狀態：已完成。
  - 完成依據：baseline tests 通過；failure isolation tests 覆蓋 partial-success candidate output、failed batch status report、retryable batch indexes 與 failed batch retry selection。
  - 確保單批失敗不會覆蓋其他 batch 的成功輸出。
  - 失敗 batch 必須能被追蹤與重試。
- `EXP-002E`: Batch integration test coverage
  - 狀態：已完成。
  - 完成依據：baseline tests 通過；integration fixture 覆蓋 planner → runner → aggregator → report 的多批流程、失敗隔離、retry batch selection 與 deterministic output。
  - 用 fixture 驗證多批流程、失敗隔離與 deterministic output。

Open questions：

- Batch planner 應先以固定張數切批，還是以檔案大小 / provider limit 切批？
- Aggregated output 應直接覆蓋單一 `style_gene_candidates.json`，還是先保留 batch fragments 再由獨立 merge step 收斂？
- Batch 失敗時應採部分成功輸出，還是預設 fail-fast？
- 是否需要把 batch metadata 納入 run manifest，作為後續重試與 audit 的一部分？
