# Style Fit Profiler Spec

## 規格狀態

- 目標版本：`v0.1.0`
- 版本名稱：Interactive style exploration MVP
- 規格狀態：Draft
- 最後更新：2026-05-21

本文件是 `style-fit-profiler` 的實作與驗證契約。README 負責說明概念、
用途與 roadmap；本 spec 負責定義目前版本目標中哪些行為必須被實作、測試
與保留。

## 脈絡

Style Fit Profiler 的目標，是讓使用者透過一輪又一輪的候選圖選擇，逐步找出
自己偏好的 AI 圖像風格。使用者不需要一開始就能說出完整畫風名稱或美術術語；
系統應該從使用者的偏好選擇中，記錄並演化 prompt genes、seed genes 與其他
風格條件。

長期版本會包含資料集整理、LoRA 匯出、LoRA 訓練與驗證。`v0.1.0` 只定義最小
可用的互動式探索流程，重點是收集偏好、保留可追蹤紀錄，並把入選圖片整理成
早期 LoRA dataset 需要的輸出格式。

## 目標

`v0.1.0` 必須提供一條可重現的風格探索流程：

```text
load config and gene pool
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
    "medium": [
      {
        "id": "medium_watercolor",
        "prompt": "watercolor illustration",
        "weight": 1.0
      }
    ],
    "color_palette": [
      {
        "id": "palette_muted_cyan_rose",
        "prompt": "muted cyan and rose palette",
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

## 不變條件

- 每張 generated image 必須有對應 candidate metadata file。
- 每張 exported selected image 必須能 trace back 到一個 candidate ID。
- 每個 exported caption 必須能 trace back 到一個 candidate ID。
- 每個 candidate 必須能 trace back 到產生它的 gene IDs。
- Selection history 必須是 append-only。
- Export 不可覆蓋既有 dataset directory，除非 overwrite 被明確啟用。
- Failed 或 incomplete candidates 不可被匯出為 positive training samples。

## 錯誤條件

系統必須對以下情境回報清楚錯誤：

- 缺少 config file。
- Config schema 無效或 config version 不支援。
- 缺少 gene pool file。
- Gene pool schema 無效。
- Gene ID 重複。
- Gene category 為空。
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

## Testing Implications

測試案例必須能 trace back 到 acceptance criteria：

```text
Test ID: T-AC01-valid-config
Spec Reference: AC-01
Purpose: 接受有效 config 與 gene pool。

Test ID: T-AC01-invalid-config
Spec Reference: AC-01
Purpose: 在 generation 前拒絕無效 config。

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

- Config validation unit tests。
- Gene pool validation unit tests。
- Selection validation unit tests。
- Crossover / mutation unit tests。
- Caption composition unit tests。
- Mock backend full-flow integration test。
- Dataset export integration test。

## Open Questions

- 第一個 real generation backend 應優先實作 Stable Diffusion WebUI、ComfyUI 還是 Diffusers？
- 第一版使用者介面應該是 CLI、local web UI、notebook，還是 file-based review？
- LoRA training 有意義前，最少需要多少 selected images？
- `v0.1.0` 是否只支援 manual convergence，或要暴露早期 convergence signal？
- Rejected samples 是否要預設保留，供未來 preference modeling 使用？
- `style_validation_prompts.json` 應納入 `v0.1.0`，還是延到 `v0.3.0`？
