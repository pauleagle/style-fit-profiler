# Style Fit Profiler

Style Fit Profiler 是一個用來探索、收斂並固定個人 AI 視覺風格的實驗型工具。它的目標不是一開始就要求使用者描述清楚「想要什麼畫風」，而是透過互動式偏好選擇，逐步找出使用者直覺喜歡的視覺特徵，最後整理成可用於 Stable Diffusion / LoRA 微調的訓練資料。

這個 module 預計結合互動式基因演算法、Stable Diffusion 圖像生成、資料集整理與 LoRA 訓練流程，作為建立個人畫風模型的前置 profiler。

## 正式規格

目前 README 作為概念入口與 roadmap。可實作、可測試的 `v0.1.0` 規格放在 [SPEC.md](./SPEC.md)，包含 scope、non-goals、input/output contract、business rules、error conditions、acceptance criteria 與 testing implications。

## 核心概念

```text
Phase 0（optional）：從既有圖片抽取候選風格基因
  ↓
Phase 1：互動式風格探索
  ↓
Phase 2：候選風格收斂與資料集整理
  ↓
Phase 3：LoRA 訓練資料輸出
  ↓
Phase 4：個人風格 LoRA 微調與驗證
```

在這個專案中，`style_profile` 不是單一 prompt 或單張參考圖，而是以下資料的組合：

```text
style_profile = reference images + extracted candidate genes + prompt genes + seed genes + visual preferences + selected images + rejected images + tagging policy + LoRA training config
```

使用者不需要先定義美術理論或風格關鍵字，只需要在每一輪從多張候選圖中選出喜歡的結果。系統會把這些偏好轉換成下一輪生成條件，讓風格逐步往使用者的潛在審美收斂。

## 預期專案結構

```text
style-fit-profiler/
├─ phase0-style-gene-extractor.py    # Phase 0：從既有圖片抽取候選風格基因（optional）
├─ phase1-style-evolution.py         # Phase 1：互動式候選圖生成與偏好選擇
├─ phase2-dataset-curator.py         # Phase 2：整理入選圖片、去重、品質篩選
├─ phase3-lora-exporter.py           # Phase 3：輸出 LoRA 訓練資料與 caption
├─ phase4-style-validator.py         # Phase 4：用驗證 prompt 測試 LoRA 穩定性
├─ reference_images/                 # Phase 0 optional input：使用者已喜歡的既有圖片
├─ style_gene_candidates.json        # Phase 0 optional output：待審查 / 合併的候選風格基因
├─ style_profiler_config.json        # 主設定：模型、prompt genes、selection policy、export policy
├─ style_gene_pool.json              # 可演化的風格基因：媒材、線條、色彩、構圖等
├─ style_validation_prompts.json     # LoRA 完成後的驗證題組
├─ requirements.txt
├─ SPEC.md
└─ README.md
```

目前此 module 仍在設計階段，檔案結構會隨實作逐步補齊。

## 預期流程

### Phase 0（optional）：從既有圖片抽取候選風格基因

如果使用者已經有一批喜歡的既有圖片，Phase 0 可以先從這些圖片抽取候選風格基因，作為 Phase 1 的初始 gene pool 來源。

Phase 0 預期分成三個面向：

1. 渲染與技法（Rendering）
2. 色彩與光效（Color & Light）
3. 材質與雜訊（Texture & Artifacts）

預期功能：

- 掃描 `reference_images/` 中的既有圖片
- 建立 reference image manifest
- 從圖片中抽取候選 prompt genes
- 依 Rendering、Color & Light、Texture & Artifacts 三面向分類
- 輸出 `style_gene_candidates.json`
- 讓使用者審查、刪改或合併候選 genes 到 `style_gene_pool.json`

#### Manual Gemini Image Probe

EXP-001 保留一個手動 Gemini 圖片分析入口，供本機確認單張 reference image 是否能回傳 Phase 0 三面向 traits。此入口不是預設 Phase 0 backend，也不納入 CI；正式 Phase 0 baseline 仍使用 deterministic mock extractor，Gemini extractor 必須明確 opt in。

PowerShell 範例：

```powershell
$env:PYTHONPATH = "src"
$env:GEMINI_API_KEY = "<your key>"
python -m style_fit_profiler.gemini_image_probe reference_images/ref-001.png
```

可選參數：

```powershell
python -m style_fit_profiler.gemini_image_probe reference_images/ref-001.png --model gemini-2.5-flash
python -m style_fit_profiler.gemini_image_probe reference_images/ref-001.png --raw
python -m style_fit_profiler.gemini_image_probe reference_images/ref-001.png --prompt-file prompts/phase0-gemini.txt
```

#### Manual Gemini Batch Probe

EXP-001 / EXP-002 也提供一個手動批次 Gemini 入口，供本機將 `reference_images/`
中的多張圖片依固定 batch size 送入 Gemini extractor，並輸出 Phase 0 artifacts。
此入口仍是 opt-in manual probe，不是預設 backend，也不納入 CI。

PowerShell 範例：

```powershell
$env:PYTHONPATH = "src"
$env:GEMINI_API_KEY = "<your key>"
python -m style_fit_profiler.gemini_batch_probe --input-dir reference_images --batch-size 2
```

可選參數：

```powershell
python -m style_fit_profiler.gemini_batch_probe --run-dir runs/manual-gemini-batch
python -m style_fit_profiler.gemini_batch_probe --model gemini-2.5-flash
python -m style_fit_profiler.gemini_batch_probe --prompt-file prompts/phase0-gemini.txt
python -m style_fit_profiler.gemini_batch_probe --timeout-seconds 90
```

輸出位置：

```text
runs/manual-gemini-batch/
└─ phase0/
   ├─ reference_image_manifest.json
   ├─ style_gene_candidates.json
   └─ batch_run_report.json
```

若部分 batch 失敗，CLI 仍會寫出可用的 partial `style_gene_candidates.json` 與
`batch_run_report.json`，並以非零 exit code 結束，方便人工檢查與重試。

安全注意事項：

- `GEMINI_API_KEY` 只放在環境變數，不寫入 repo、README、SPEC、config 或 commit。
- Gemini probe / batch probe 會把圖片內容送到 Gemini API；不要用未準備送出本機的私人或敏感圖片。
- Prompt 明確要求不要產生 artist names、copyrighted character names 或 private identity claims；輸出仍需人工審查。
- 若圖片超過 inline request size，先停止並改走後續 File API flow；不要在此手動 probe 中硬塞大檔。

### Phase 1：互動式風格探索

Phase 1 會建立第一代候選圖，讓使用者用直覺選擇喜歡的圖片。

```text
initial gene pool
  ↓
generate image candidates
  ↓
user selects preferred images
  ↓
crossover + mutation
  ↓
next generation
```

預期功能：

- 隨機產生第一代候選圖
- 每輪顯示多張風格不同的候選圖
- 記錄使用者選擇與淘汰結果
- 根據入選圖進行 crossover / mutation
- 持續產生下一代候選圖，直到風格收斂

### Phase 2：候選風格收斂與資料集整理

Phase 2 會把演化後期的高分圖片整理成 LoRA 訓練集。

預期功能：

- 收集演化後期入選圖片
- 排除重複、低品質、構圖不穩定的樣本
- 保留使用者明確喜歡的視覺特徵
- 建立正樣本資料夾
- 可選擇保留 rejected samples，供未來偏好模型或反向分析使用

### Phase 3：LoRA 訓練資料輸出

Phase 3 會將整理後的圖片轉成 LoRA 訓練可用的資料格式。

預期功能：

- 統一圖片解析度，例如 512x512 或 768x768
- 產生 caption / tag 檔案
- 支援 BLIP 或 WD14 tagging 流程
- 設定個人風格 trigger word
- 輸出 Kohya_ss 或其他 LoRA trainer 可讀取的資料夾格式

### Phase 4：個人風格 LoRA 驗證

Phase 4 會使用固定驗證 prompt 檢查 LoRA 是否真的學到穩定風格。

預期功能：

- 使用同一組 validation prompts 測試多個 LoRA checkpoint
- 比較 trigger word 有無啟用時的差異
- 檢查人物、場景、構圖變化下的風格穩定性
- 記錄推薦 checkpoint 與建議權重

## 設定檔方向

### `style_profiler_config.json`

主設定檔，預期包含：

- `generation_model`
- `image_size`
- `reference_image_analysis_policy`
- `candidates_per_generation`
- `max_generations`
- `mutation_rate`
- `selection_policy`
- `caption_policy`
- `lora_export_policy`
- `validation_policy`

### `style_gene_pool.json`

放可被演化流程抽樣與重組的風格基因，例如：

- rendering
- color_light
- texture_artifacts
- medium
- color palette
- line quality
- lighting
- composition
- character rendering
- background density
- texture

### `style_validation_prompts.json`

放 LoRA 訓練完成後用來驗證風格穩定性的 prompt 題組。適合包含人物、場景、動作、距離與光線變化，避免模型只記住單一構圖。

## 環境需求

預期需求：

- Python 3.10+
- Stable Diffusion WebUI、ComfyUI 或 Diffusers
- 可執行圖像生成的 GPU 環境
- LoRA trainer，例如 Kohya_ss
- BLIP 或 WD14 tagger

Colab 版本可作為早期實驗環境；本地版本會優先考慮可重現、可記錄、可版本化的 pipeline。

## v0.1.0 預期用途

第一版目標是建立一條最小可用流程：

```text
optional reference image analysis
  → extract candidate style genes
  → review / merge gene candidates
  → generate candidates
  → user selection
  → evolve prompt / seed genes
  → export selected images
  → prepare LoRA dataset
```

這個版本適合用來回答：

- 我其實喜歡什麼樣的 AI 視覺風格？
- 哪些 prompt / seed / 色彩 / 線條特徵會反覆被我選中？
- 能不能把這些偏好整理成一組 LoRA 訓練資料？
- 訓練後的 LoRA 是否能在不同 prompt 下穩定重現風格？

## 注意事項

- 互動式選擇結果會受到當天心情、候選圖品質與模型隨機性的影響。
- 少量圖片訓練出的 LoRA 可能會過度記住特定角色或構圖。
- 如果資料集太一致，模型可能缺乏泛化能力；如果資料集太發散，風格可能不穩定。
- trigger word 應避免使用常見單字，以降低和既有概念衝突的機率。
- LoRA 訓練參數需要依 base model、圖片數量與風格複雜度調整。

## Roadmap

Possible next steps:

- 建立 optional Phase 0 既有圖片風格基因抽取流程
- 建立互動式候選圖選擇介面
- 設計第一版 `style_gene_pool.json`
- 記錄每一代圖片、基因與使用者選擇
- 加入簡單 crossover / mutation policy
- 匯出 LoRA 訓練資料夾
- 整合 caption / tag 產生流程
- 建立 validation prompt set
- 產生 style profile report
- 支援不同 base model 的風格比較
- 支援多個 style profile 的版本管理

## Version Direction

```text
v0.1.0  Optional reference-image bootstrap and interactive style exploration MVP
v0.2.0  Dataset curation and LoRA export
v0.3.0  LoRA validation and style profile report
v0.4.0  Multi-profile comparison and versioning
```
