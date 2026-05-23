# Style Fit Profiler Spec

## 規格狀態

- 目標版本：`v0.1.0`
- 版本名稱：Optional reference-image bootstrap + interactive style exploration MVP
- 規格狀態：Draft
- 最後更新：2026-05-22

本文件是 `style-fit-profiler` 的實作與驗證契約。README 負責說明概念、
用途與 roadmap；本 spec 負責定義目前版本目標中哪些行為必須被實作、測試
與保留。

## 脈絡

Style Fit Profiler 的目標，是讓使用者透過一輪又一輪的候選圖選擇，逐步找出
自己偏好的 AI 圖像風格。使用者不需要一開始就能說出完整畫風名稱或美術術語；
系統應該從使用者的偏好選擇中，記錄並演化 prompt genes、seed genes 與其他
風格條件。

若使用者已經有一批喜歡的既有圖片，`v0.1.0` 可選擇先執行 Phase 0，從這些
圖片抽取候選風格基因。Phase 0 的輸出不是最終風格定義，而是 Phase 1 初始
gene pool 的 bootstrap 來源。

長期版本會包含資料集整理、LoRA 匯出、LoRA 訓練與驗證。`v0.1.0` 只定義最小
可用的互動式探索流程，重點是收集偏好、保留可追蹤紀錄，並把入選圖片整理成
早期 LoRA dataset 需要的輸出格式。

## 目標

`v0.1.0` 必須提供一條可重現的風格探索流程：

```text
optionally extract candidate genes from reference images
  -> load config and gene pool
  -> generate candidate images
  -> record user selections
  -> evolve prompt and seed genes
  -> repeat until stopped or max generations reached
  -> export selected images and metadata
```

本版本的 correctness 問題是：

> 給定 config、gene pool 與使用者選擇，系統是否能記錄一場可追蹤的風格探索，
> 並在匯出入選圖片時保留每張圖背後的 prompt、seed、genes 與 selection history？

## 範圍

`v0.1.0` 包含：

- 載入並驗證 `style_profiler_config.json`。
- 載入並驗證 `style_gene_pool.json`。
- 可選擇從 reference images 抽取候選風格基因。
- 為每次探索建立唯一 run directory。
- 依設定產生每一代候選圖。
- 支援可測試的 mock 或 dry-run generation backend。
- 記錄 candidate metadata、generated image path 與 generation payload。
- 記錄每一代的 selected / rejected candidates。
- 根據 selected candidates 進行 crossover / mutation，產生下一代條件。
- 匯出 selected images、captions 與 metadata 到類 LoRA dataset 資料夾。

## 非目標

`v0.1.0` 不需要：

- 實際訓練 LoRA。
- 比較多個 LoRA checkpoint。
- 整合 BLIP、WD14 或其他自動 tagger。
- 提供完整 GUI。
- 提供自動美學評分。
- 從既有圖片精準判斷藝術家、流派或版權狀態。
- 保證真實 Stable Diffusion backend 在不同機器產生 pixel-identical 圖片。
- 自動判斷最終風格是否已經收斂。
- 支援多人或 hosted collaboration。

## 輸入

### `style_profiler_config.json`

必要欄位：

```json
{
  "version": "0.1.0",
  "run_name": "default",
  "generation_backend": {
    "type": "mock"
  },
  "image_size": {
    "width": 768,
    "height": 768
  },
  "candidates_per_generation": 8,
  "max_generations": 10,
  "random_seed": 12345,
  "reference_image_analysis_policy": {
    "enabled": false,
    "input_dir": "reference_images",
    "output_file": "style_gene_candidates.json",
    "aspects": [
      "rendering",
      "color_light",
      "texture_artifacts"
    ]
  },
  "selection_policy": {
    "min_selected": 1,
    "max_selected": 4
  },
  "evolution_policy": {
    "elite_count": 2,
    "mutation_rate": 0.2
  },
  "export_policy": {
    "include_rejected": false,
    "trigger_word": "pstyle",
    "caption_source": "prompt_genes"
  }
}
```

驗證規則：

- `version` 必須是支援中的 spec version。
- `generation_backend.type` 必須是 `mock`、`webui`、`comfyui` 或 `diffusers`。
- `image_size.width` 與 `image_size.height` 必須是正整數。
- `candidates_per_generation` 必須大於 `0`。
- `max_generations` 必須大於 `0`。
- `reference_image_analysis_policy.enabled` 為 `false` 時，不需要 reference images。
- `reference_image_analysis_policy` 不可包含未知欄位；支援欄位只有 `enabled`、`input_dir`、`output_file`、`aspects`。
- `reference_image_analysis_policy.aspects` 若存在，必須至少包含一個 aspect，且只能包含 `rendering`、`color_light`、`texture_artifacts`。
- `selection_policy.min_selected` 必須至少為 `1`。
- `selection_policy.max_selected` 不可大於 `candidates_per_generation`。
- `evolution_policy.mutation_rate` 必須介於 `0` 到 `1`。
- `export_policy.trigger_word` 不可為空，且應避免使用常見自然語言單字。

### `style_gene_pool.json`

必要結構：

```json
{
  "version": "0.1.0",
  "genes": {
    "rendering": [
      {
        "id": "rendering_watercolor_edges",
        "prompt": "watercolor illustration with soft edges",
        "weight": 1.0
      }
    ],
    "color_light": [
      {
        "id": "color_light_muted_cyan_rose",
        "prompt": "muted cyan and rose palette with gentle rim light",
        "weight": 1.0
      }
    ],
    "texture_artifacts": [
      {
        "id": "texture_artifacts_subtle_paper_grain",
        "prompt": "subtle paper grain texture",
        "weight": 1.0
      }
    ]
  }
}
```

驗證規則：

- 每個 gene category 至少要有一個 gene。
- Gene ID 在整個 pool 中必須唯一。
- Gene ID 是穩定識別碼，不可在不同 run 之間任意重新產生。
- `prompt` 不可為空。
- `weight` 必須是正數。

### Phase 0 reference images（optional）

當 `reference_image_analysis_policy.enabled` 為 `true` 時，系統會從
`reference_image_analysis_policy.input_dir` 讀取既有圖片，抽取候選風格基因。

Phase 0 必須把候選基因分成三個面向：

1. 渲染與技法（Rendering）
   - 例如媒材感、筆觸、線條品質、描邊方式、上色方式、陰影處理、邊緣處理。
2. 色彩與光效（Color & Light）
   - 例如色盤、飽和度、明暗對比、曝光傾向、光源方向、glow、rim light、色溫。
3. 材質與雜訊（Texture & Artifacts）
   - 例如紙張顆粒、膠片顆粒、halftone、壓縮痕跡、掃描感、筆刷紋理、數位雜訊。

Phase 0 應產生 `style_gene_candidates.json`，但不應直接覆蓋
`style_gene_pool.json`。使用者或後續流程必須能先檢查、刪改或合併候選 genes。

候選基因輸出格式：

```json
{
  "version": "0.1.0",
  "source": "phase0_reference_image_analysis",
  "aspects": {
    "rendering": [
      {
        "id": "rendering_soft_airbrush_edges",
        "prompt": "soft airbrushed edges",
        "confidence": 0.72,
        "source_images": [
          "reference_images/ref-001.png"
        ],
        "notes": ""
      }
    ],
    "color_light": [
      {
        "id": "color_light_muted_cyan_rose",
        "prompt": "muted cyan and rose palette",
        "confidence": 0.68,
        "source_images": [
          "reference_images/ref-001.png"
        ],
        "notes": ""
      }
    ],
    "texture_artifacts": [
      {
        "id": "texture_artifacts_paper_grain",
        "prompt": "subtle paper grain texture",
        "confidence": 0.61,
        "source_images": [
          "reference_images/ref-002.png"
        ],
        "notes": ""
      }
    ]
  }
}
```

驗證規則：

- `aspects` 必須包含 `rendering`、`color_light`、`texture_artifacts` 三個 keys。
- 每個候選 gene 的 `id` 在檔案內必須唯一。
- 每個候選 gene 的 `prompt` 不可為空。
- `confidence` 必須介於 `0` 到 `1`。
- `source_images` 至少要包含一個 reference image path。
- `source_images` 應使用相對路徑。

### 使用者選擇

每一個完成的 generation 都必須接收 selected candidate IDs。Rejected candidates
預設為同一代中未被 selected 的 candidates；若未來介面支援 explicit rejected IDs，
則 explicit rejected IDs 必須與 selected IDs 分開驗證。

## 輸出

每次 run 會寫入新的 run directory：

```text
runs/
└─ <run_id>/
   ├─ run_manifest.json
   ├─ phase0/                         # only when Phase 0 enabled
   │  ├─ reference_image_manifest.json
   │  └─ style_gene_candidates.json
   ├─ generations.jsonl
   ├─ selections.jsonl
   ├─ candidates/
   │  └─ generation-000/
   │     ├─ candidate-000.png
   │     └─ candidate-000.json
   └─ export/
      └─ lora_dataset/
         ├─ images/
         │  ├─ candidate-000.png
         │  └─ candidate-000.txt
         └─ dataset_manifest.json
```

輸出契約：

- `run_manifest.json` 記錄 config hash、gene pool hash、run ID、run start time、backend type 與 spec version。
- 若啟用 Phase 0，`phase0/reference_image_manifest.json` 記錄 reference image path、file hash、image size 與分析狀態。
- 若啟用 Phase 0，`phase0/style_gene_candidates.json` 記錄從 reference images 抽取出的候選風格基因。
- `generations.jsonl` 以 append-only 方式記錄每個完成的 generation event。
- `selections.jsonl` 以 append-only 方式記錄每一代的 selected 與 rejected candidate IDs。
- 每個 candidate metadata file 記錄 candidate ID、generation index、prompt text、gene IDs、seed、backend payload、image path 與 status。
- `dataset_manifest.json` 記錄每張 exported image、source candidate ID、caption path、gene IDs、source generation 與 trigger word。
- Metadata 中儲存的路徑應以 run directory 為基準使用 relative path。

## 業務規則

1. 如果 config 或 gene pool 無效，run 必須在 generation 前失敗。
2. 一個完成的 generation 必須剛好包含 `candidates_per_generation` 個 candidates。
3. Candidate IDs 在同一個 run 內必須唯一。
4. Candidate 一旦被標記為 complete，其 metadata 不可被修改。
5. Selection event 只能引用同一個 completed generation 裡的 candidates。
6. 同一個 candidate 不可在同一個 selection event 中同時被 selected 與 rejected。
7. Selected candidate 數量必須符合 `selection_policy.min_selected` 與 `selection_policy.max_selected`。
8. 下一代必須由 selected candidates 的 gene IDs，加上 gene pool mutation 產生。
9. Mutation 只能引入 `style_gene_pool.json` 中已知的 gene IDs。
10. Export 預設只包含 selected candidates，除非 `export_policy.include_rejected` 為 `true`。
11. Caption 必須包含 configured trigger word 與該 selected candidate 的 prompt gene text。
12. 使用相同 config、gene pool、random seed、selection history 與 mock backend 時，必須產生等價 metadata。
13. Phase 0 為 optional；未啟用時，run 不得要求 reference images。
14. Phase 0 產生的是候選風格基因，不得未經合併流程直接覆蓋 `style_gene_pool.json`。
15. Phase 0 candidate merge 只能使用 `rendering`、`color_light`、`texture_artifacts` 三個面向中的候選 genes。

## 不變條件

- 每張 generated image 必須有對應 candidate metadata file。
- 每張 exported selected image 必須能 trace back 到一個 candidate ID。
- 每個 exported caption 必須能 trace back 到一個 candidate ID。
- 每個 candidate 必須能 trace back 到產生它的 gene IDs。
- Selection history 必須是 append-only。
- Export 不可覆蓋既有 dataset directory，除非 overwrite 被明確啟用。
- Failed 或 incomplete candidates 不可被匯出為 positive training samples。
- Phase 0 的每個候選 gene 必須能 trace back 到至少一張 reference image。
- Phase 0 失敗不可破壞既有 `style_gene_pool.json`。

## 錯誤條件

系統必須對以下情境回報清楚錯誤：

- 缺少 config file。
- Config schema 無效或 config version 不支援。
- 缺少 gene pool file。
- Gene pool schema 無效。
- Gene ID 重複。
- Gene category 為空。
- Phase 0 enabled 但 reference image directory 不存在。
- Phase 0 enabled 但 reference image directory 中沒有支援的圖片格式。
- Phase 0 candidate gene schema 無效。
- Generation backend 不支援。
- Generation backend failure。
- Generation response 成功但 candidate image 不存在。
- 使用者選擇了無效 candidate ID。
- Selected candidate 數量過少或過多。
- 尚未有任何 selected candidates 就要求 export。
- Export directory 已存在，但 overwrite 未啟用。

## Acceptance Criteria

### AC-01: Config and gene pool validation

給定有效 config 與 gene pool，profiler 接受它們並建立 run manifest。給定無效
檔案時，profiler 必須在 generation 前失敗，並指出無效欄位。

### AC-01A: Optional Phase 0 reference image analysis

給定 `reference_image_analysis_policy.enabled = true` 與有效 reference images，
profiler 必須產生 `phase0/reference_image_manifest.json` 與
`phase0/style_gene_candidates.json`。候選 genes 必須被分入 `rendering`、
`color_light`、`texture_artifacts` 三個面向，且每個候選 gene 都能追溯到至少
一張 reference image。

### AC-02: Candidate generation

給定 `candidates_per_generation = N`，一個 completed generation 必須建立剛好
`N` 筆 candidate metadata 與 `N` 個 image artifacts；若 generation 失敗，不可
把該 generation 視為 complete。

### AC-03: Selection recording

給定 completed generation 與有效 selected candidate IDs，profiler 必須記錄一筆
selection event，包含 selected 與 rejected candidate IDs。無效 IDs 或不合法的
selection count 必須被拒絕。

### AC-04: Evolution

給定至少一個 selected candidate，下一代必須從 selected candidates 的 gene IDs
衍生。當 mutation 啟用且 gene pool 有可用替代 gene 時，下一代中至少一個
candidate 應該包含相對於 parent lineage 的 changed gene。

### AC-05: Traceability

對任何 exported image，驗證者必須能從 exported file 追溯到 candidate metadata、
generation event、selection event、prompt text、seed 與 gene IDs。

### AC-06: LoRA dataset export

給定 selected candidates，export 必須建立 `export/lora_dataset` folder，內含 copied
images、對應 `.txt` captions 與 `dataset_manifest.json`。

### AC-07: Mock backend reproducibility

給定相同 config、gene pool、random seed 與 selection history，mock backend 必須
產生等價 candidate metadata 與 export manifests。

### AC-08: Safe overwrite behavior

給定已存在的 export directory 且 overwrite disabled，export 必須以清楚錯誤失敗，
並保持既有 export 內容不變。

## Phase 0 Atomic Implementation Steps

Phase 0 的第一版實作目標是先完成 deterministic / mock-friendly 的資料流，不先鎖定
真實 image analysis backend。以下步驟應能逐步實作、逐步測試，並 trace back 到
`AC-01A`、Phase 0 output contract、business rules 與 error conditions。

### P0-00: Python project scaffold

狀態：已完成。

- 建立最小 Python project metadata，例如 `pyproject.toml`。
- 建立 `src/style_fit_profiler/` package layout。
- 建立 `tests/` 測試目錄與可執行的 stdlib `unittest` discovery。
- 建立 `.gitignore`，排除 `__pycache__/`、`.venv/` 與常見 Python test / lint cache。
- 不引入 Phase 0 domain behavior。
- 不預先綁定 heavy image generation 或 image analysis dependencies。
- Validation / test hook: `python -m unittest discover -s tests` 可成功執行。
- Spec reference: Phase 0 Atomic Implementation prerequisite。

### P0-01: Config model

狀態：已完成。

- 定義 `reference_image_analysis_policy` config model。
- 支援 `enabled`、`input_dir`、`output_file`、`aspects`。
- 拒絕 unknown policy fields，避免 config typo 被 silent ignore。
- 驗證 `aspects` 至少包含一個 aspect，且只能包含 `rendering`、`color_light`、`texture_artifacts`。
- Spec reference: `reference_image_analysis_policy` validation, `AC-01A`。

### P0-02: Disabled path

狀態：已完成。

- 當 `reference_image_analysis_policy.enabled = false` 時，不讀取 reference images。
- 不要求 `reference_images/` 存在。
- 不產生 `phase0/` output。
- Spec reference: Business Rule 13。

### P0-03: Reference image discovery

狀態：已完成。
完成依據：baseline tests 通過；focused mutation review 已殺掉 P0-03 關鍵變異。

- 當 Phase 0 enabled 時，掃描 `reference_image_analysis_policy.input_dir`。
- 只接受支援的 image file extensions。
- 若目錄不存在或沒有支援圖片，回報 spec-defined error。
- Spec reference: Phase 0 error conditions。

### P0-04: Reference image manifest

狀態：已完成。
完成依據：baseline tests 通過；focused mutation review 已殺掉 P0-04 關鍵變異。

- 為每張 reference image 建立 manifest record。
- 每筆 record 至少包含 relative path、file hash、image size、analysis status。
- Manifest 輸出到 `phase0/reference_image_manifest.json`。
- Spec reference: Phase 0 output contract。

### P0-05: Candidate gene schema

狀態：已完成。
完成依據：baseline tests 通過；focused mutation review 已殺掉 P0-05 schema key / field 變異。

- 定義 `style_gene_candidates.json` schema。
- `aspects` 必須包含 `rendering`、`color_light`、`texture_artifacts`。
- 每個 candidate gene 必須包含 `id`、`prompt`、`confidence`、`source_images`、`notes`。
- Spec reference: Phase 0 candidate gene validation rules。

### P0-06: Candidate gene validator

狀態：已完成。
完成依據：baseline tests 通過；focused mutation review 已殺掉 duplicate ID、blank prompt、confidence range 與 source_images relative path 變異。

- 驗證 candidate gene IDs 在檔案內唯一。
- 驗證 `prompt` 不為空。
- 驗證 `confidence` 介於 `0` 到 `1`。
- 驗證 `source_images` 至少有一個 relative path。
- Spec reference: Phase 0 candidate gene validation rules, invariants。

### P0-07: Extractor interface

狀態：已完成。
完成依據：baseline tests 通過；focused mutation review 已殺掉 extractor input / output contract 變異。

- 定義 Phase 0 extractor interface。
- Interface input 為 reference image manifest records。
- Interface output 為三面向 candidate gene collections。
- Interface 不應直接寫入 `style_gene_pool.json`。
- Spec reference: Business Rule 14。

### P0-08: Deterministic mock extractor

狀態：已完成。
完成依據：baseline tests 通過；focused mutation review 已殺掉 deterministic ordering / schema-valid output 變異。

- 實作 deterministic mock extractor，供測試與早期 CLI 使用。
- Mock extractor 可根據檔名、固定 fixture metadata 或測試輸入產生候選 genes。
- 相同輸入必須產生等價 `style_gene_candidates.json`。
- Spec reference: `AC-01A` and reproducible MVP behavior。

### P0-09: Aspect classification

狀態：已完成。
完成依據：baseline tests 通過；focused mutation review 已殺掉 missing/unknown aspect 與 ID prefix mismatch 變異。

- 確保 extractor output 被分類到三個固定 aspects。
- 不允許輸出未知 aspect key。
- 每個輸出 candidate gene 的 ID prefix 應對應 aspect，例如 `rendering_`、`color_light_`、`texture_artifacts_`。
- Spec reference: `AC-01A`, Business Rule 15。

### P0-10: Phase 0 output writer

狀態：已完成。
完成依據：baseline tests 通過；focused mutation review 已殺掉 manifest/candidate output path 與 extractor wiring 變異。

- 建立 `phase0/` output directory。
- 寫出 `reference_image_manifest.json`。
- 寫出 `style_gene_candidates.json`。
- Metadata 中的路徑應相對於 run directory 或 project-defined input root。
- Spec reference: Phase 0 output contract。

### P0-11: No implicit gene pool overwrite

狀態：已完成。
完成依據：baseline tests 通過；focused mutation review 已殺掉 success/failure path 覆蓋 `style_gene_pool.json` 變異。

- Phase 0 不得直接覆蓋 `style_gene_pool.json`。
- 若未來加入 merge command，merge 必須是獨立步驟，且輸入為已驗證的 candidate genes。
- Spec reference: Business Rule 14, invariant "Phase 0 失敗不可破壞既有 `style_gene_pool.json`"。

### P0-12: AC-01A test coverage

狀態：已完成。
完成依據：baseline tests 通過；`T-AC01A-phase0-reference-analysis` 覆蓋 enabled output、disabled skip、invalid reference input 與 invalid candidate schema。

- 補上 `T-AC01A-phase0-reference-analysis`。
- 測試 enabled path 會產生 manifest 與 candidate genes。
- 測試 disabled path 不要求 reference images。
- 測試 invalid directory、empty directory、invalid candidate schema 會回報清楚錯誤。
- Spec reference: `AC-01A`, Phase 0 error conditions。

### Deferred from Phase 0 MVP

- 真實 CLIP / captioner / vision model backend。
- confidence 的模型化計算方式。
- human approval UI。
- candidate genes 合併到 `style_gene_pool.json` 的互動流程。
- reference image 的版權、作者、流派或資料來源判定。

## Backlog

### EXP-001: Gemini Image Analysis Extractor

狀態：Post-P0 Experimental Spec，尚未實作為正式 extractor。
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
  - 實作符合 `Phase0Extractor` 的 extractor。
  - 明確 opt-in，不改 deterministic mock default。
- `EXP-001E`: Manual integration command
  - 保留或整理 `gemini_image_probe.py` 作為手動驗證入口。
  - 文件化本機圖片測試指令、環境變數與安全注意事項。

Open questions：

- Gemini extractor 應透過 config 啟用，還是先只提供 CLI/manual command？
- 初版 `confidence` 應固定為 experimental default，還是從模型 response 中要求自評分數？
- Gemini 回傳的 broad traits 是否需要 human review 後才可合併到 candidate output？
- 大圖是否立即支援 File API，或先限制 inline request size？

### EXP-002: Phase 0 Batch Reference Image Analysis

狀態：Post-P0 Experimental Spec，尚未實作為正式 batch analyzer。
前置條件：Phase 0 baseline 已完成並驗證；至少一個單張 reference image analysis flow 已跑通。

Intent：

- 在既有 Phase 0 reference image analysis 之上，提供 batch-oriented 的分析 wrapper，讓多張 reference images 可以依固定批次處理。
- 將每一批 reference images 的分析結果彙整成同一份 `style_gene_candidates.json` 或同一組可合併的 batch fragments。
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
- Aggregated output 必須維持 Phase 0 candidate schema：
  - `version`
  - `source`
  - `aspects`
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
  - 狀態：planned。
  - 將 manifest records 分組成 deterministic batches。
  - 支援可配置 batch size 與 ordering rule。
- `EXP-002B`: Batch runner
  - 狀態：planned。
  - 執行每一批 analysis，並記錄 batch-level status 與 error。
  - 支援 fake client 與 mock backend。
- `EXP-002C`: Batch result aggregator
  - 狀態：planned。
  - 將多批結果合併成單一 Phase 0 candidate output。
  - 維持三面向 aspect contract。
- `EXP-002D`: Batch failure isolation
  - 狀態：planned。
  - 確保單批失敗不會覆蓋其他 batch 的成功輸出。
  - 失敗 batch 必須能被追蹤與重試。
- `EXP-002E`: Batch integration test coverage
  - 狀態：planned。
  - 用 fixture 驗證多批流程、失敗隔離與 deterministic output。

Open questions：

- Batch planner 應先以固定張數切批，還是以檔案大小 / provider limit 切批？
- Aggregated output 應直接覆蓋單一 `style_gene_candidates.json`，還是先保留 batch fragments 再由獨立 merge step 收斂？
- Batch 失敗時應採部分成功輸出，還是預設 fail-fast？
- 是否需要把 batch metadata 納入 run manifest，作為後續重試與 audit 的一部分？

### EXP-003: Colab Notebook Wrapper for Phase 0

狀態：Post-P0 Experimental Spec，尚未實作為正式 notebook wrapper。
前置條件：Phase 0 baseline 已完成並驗證；至少一個可重現的本機 Phase 0 flow 已跑通。

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

- Notebook 應產生與核心 Phase 0 flow 相同語意的輸出：
  - `reference_image_manifest.json`
  - `style_gene_candidates.json`
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
  - 狀態：planned。
  - 建立 Colab runtime setup 與依賴初始化 cell。
- `EXP-003B`: Upload and staging helper
  - 狀態：planned。
  - 處理 reference image upload、暫存與 manifest generation。
- `EXP-003C`: Notebook analysis runner
  - 狀態：planned。
  - 在 notebook 中呼叫 Phase 0 analysis flow，支援 mock backend 與 batch wrapper。
- `EXP-003D`: Preview and export cells
  - 狀態：planned。
  - 顯示候選 genes、輸出 manifest，並提供下載路徑。
- `EXP-003E`: Notebook smoke tests
  - 狀態：planned。
  - 驗證 wrapper 不破壞核心 Phase 0 contract。

Open questions：

- Notebook wrapper 應只面向 Colab，還是也要兼容本機 Jupyter？
- Upload 後的 staging file 命名應以原檔名為主，還是以穩定 digest 為主？
- Notebook 是否需要一鍵產生可下載 zip，包含 manifests 與 analysis artifacts？
- Wrapper 應直接呼叫現有 CLI/library，還是先定義更薄的 notebook-specific adapter？

### CR-001: Appeal Point and Art Style Extraction

狀態：Backlog，限 Phase 0 baseline 完成並驗證後再評估。

Intent：

- 擴充 reference image analysis，從既有圖片抽取 appeal points、visual charm factors、art style traits、impression colors 與 reusable visual genes。
- 將 Phase 0 從單純候選風格基因抽取，延伸成後續 mutation、recombination 與 style-fit profiling 可使用的 style / profile seed generator。

Do not include in current P0：

- 本 CR 不得修改目前 P0 atomic tasks。
- 必須等 P0 baseline 完成、驗證通過後，才可拆分新的 implementation steps、schema 變更或 acceptance criteria。

預期分析面向：

- Style / Technique：art style traits、brushwork、linework、shading、rendering density。
- Color / Mood：impression colors、palette、contrast、temperature、saturation。
- Appearance / Character Design：facial features、hairstyle、outfit motifs、silhouette、accessories。
- Appeal / Charm：appeal points、visual charm factors、emotional impression、memorability。
- Reusable Genes：normalized visual traits、recombinable design tokens、stable identity anchors。

## Testing Implications

測試案例必須能 trace back 到 acceptance criteria：

```text
Test ID: T-AC01-valid-config
Spec Reference: AC-01
Purpose: 接受有效 config 與 gene pool。

Test ID: T-AC01-invalid-config
Spec Reference: AC-01
Purpose: 在 generation 前拒絕無效 config。

Test ID: T-AC01A-phase0-reference-analysis
Spec Reference: AC-01A
Purpose: 驗證 Phase 0 會輸出三面向候選 genes，且每個 gene 可追溯 reference image。

Test ID: T-AC02-candidate-count
Spec Reference: AC-02
Purpose: 確認 generation 建立剛好等於設定值的 candidate count。

Test ID: T-AC03-selection-validation
Spec Reference: AC-03
Purpose: 拒絕無效 candidate IDs 與不合法 selection count。

Test ID: T-AC04-mutation
Spec Reference: AC-04
Purpose: 驗證 mutation 可以從 gene pool 引入已知 genes。

Test ID: T-AC05-traceability
Spec Reference: AC-05
Purpose: 從 exported image 追溯 candidate、generation、selection、seed 與 genes。

Test ID: T-AC06-export-format
Spec Reference: AC-06
Purpose: 驗證 dataset image、caption 與 manifest 輸出格式。

Test ID: T-AC07-mock-reproducibility
Spec Reference: AC-07
Purpose: 驗證 mock backend 在相同輸入下產生等價 metadata 與 manifests。

Test ID: T-AC08-safe-overwrite
Spec Reference: AC-08
Purpose: 確認 export 預設不覆蓋既有輸出。
```

建議第一層測試：

- P0-00 project scaffold smoke test：確認 package 可 import，且 `python -m unittest discover -s tests` 可執行。
- Config validation unit tests。
- Gene pool validation unit tests。
- Phase 0 candidate gene schema unit tests。
- Selection validation unit tests。
- Crossover / mutation unit tests。
- Caption composition unit tests。
- Mock Phase 0 reference-image analysis integration test。
- Mock backend full-flow integration test。
- Dataset export integration test。

## Open Questions

- 第一個 real generation backend 應優先實作 Stable Diffusion WebUI、ComfyUI 還是 Diffusers？
- Phase 0 第一版應使用哪種 image analysis 實作：CLIP embedding、captioner、vision model prompt、手動標註，還是混合流程？
- Phase 0 候選 genes 是否需要 human approval 後才可合併到 `style_gene_pool.json`？
- 第一版使用者介面應該是 CLI、local web UI、notebook，還是 file-based review？
- LoRA training 有意義前，最少需要多少 selected images？
- `v0.1.0` 是否只支援 manual convergence，或要暴露早期 convergence signal？
- Rejected samples 是否要預設保留，供未來 preference modeling 使用？
- `style_validation_prompts.json` 應納入 `v0.1.0`，還是延到 `v0.3.0`？
