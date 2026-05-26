# CR-001: Appeal Point and Art Style Extraction

狀態：CR-001 v1 native baseline accepted / frozen；`CR-001-08` optional projection
deferred pending projection-policy decision。

來源摘要：

- `backlog/CR-001-01-gemini-update.md`：定義 Visual Style & Appeal Point Extractor、
  10 個核心 loci、restricted allele pool、LLM JSON output、schema guardrail，
  以及後續 GA / crossover 對接方向。
- `backlog/CR-XXX-chatgpt-replenish.md`：補充 composition、mood、color harmony、
  hair、eye、visual density、world setting 與 appeal archetype 等 Visual Genome
  延伸 loci，並提出 style crossover、mutation、fitness scoring 與 latent
  compression 的長期方向。
- `backlog/CR-001-FU-01-deprecate-legacy-phase0-default-paths.md`：follow-up for
  CR-001 replacement semantics；將 legacy Phase 0 default paths 降級為 explicit
  deprecated compatibility behavior，並要求 default manual Gemini paths 使用
  CR-001 native artifact。
- `backlog/CR-001-02-loci-expansion-table.md`：整理核心 canonical loci 與 candidate
  extended loci 的雙語 token table；本 spec 以精簡 token registry 形式彙總，不保留
  完整表格版面。
- `backlog/CR-001-03-impression-colors.md`：在 `color_harmony` 後補入結構化
  `impression_colors`，用 `main`、`secondary`、`accent` 三個 hex color fields 表達
  參考圖的印象色。

Intent：

- 擴充 reference image analysis，從既有圖片抽取 expected art style、appeal points、
  visual charm factors、character appearance traits、impression colors 與 reusable
  visual genes。
- 將 Phase 0 從單純候選風格基因抽取，延伸成可支援 mutation、recombination、
  matrix evolution、recommendation、clustering 與 style-fit profiling 的 Visual
  Genome / Visual DNA seed generator。
- 同時保留兩層語意：
  - Expected style genotype：可量化的底層美學風格基因，適合 crossover / mutation。
  - Appeal phenotype：角色外型、服裝、情緒印象與商業吸睛點，適合後續 fitness
    scoring 或 human review。

Do not include in current P0：

- 本 CR 不得修改目前 P0 atomic tasks。
- 本 CR 不得改變 deterministic mock Phase 0 default。
- 本 CR 不得讓 LLM / Gemini API 成為預設 unittest 或 baseline run dependency。
- 本 CR 不得直接覆蓋 `style_gene_pool.json`。
- 必須等 P0 baseline 完成、驗證通過後，才可拆分新的 implementation steps、
  schema 變更、acceptance criteria 或 migration path。

Core output concept：

- Vision LLM 應扮演 Visual Style & Appeal Point Encoder。
- LLM 只能從規格允許的 allele registry 中選詞；不得自行創造 synonyms 或自由標籤。
- 每個 locus 應選出 1 到 4 個 alleles，並為每個 allele 輸出 `0.0` 到 `1.0`
  的 intensity。
- CR-001 v1 schema 啟用順序：
  - Base required：`expected_style_genes` 6 個 canonical style loci、
    `character_appeal_genes` 4 個 canonical appeal loci，以及 top-level
    `cr001_summary`。
  - Base optional：`impression_colors`；它是 palette auxiliary output，不是 allele
    locus，缺席時不得卡死 v1 baseline，但若存在就必須通過 palette schema 驗證。
  - `CR-001A+` deferred：`composition`、`mood_atmosphere`、`color_harmony`、
    `hair_style`、`eye_rendering`、`visual_density`、`world_setting`、
    `appeal_archetype` 等 extended loci，暫不納入 v1 required schema。
- `cr001_summary` 應為短摘要，用於 review UI 或人工審查，不可取代 structured genes。
- 每份 output 必須能 trace back 到 source reference image。

Expected JSON shape（with optional `impression_colors` example）：

```json
{
  "appeal_point_and_art_style": {
    "expected_style_genes": {
      "genre": { "selected": ["cel-shading"], "intensity": [0.9] },
      "line_art": { "selected": ["clean-line-art"], "intensity": [0.8] },
      "brush_shading": { "selected": ["smooth-airbrush"], "intensity": [0.8] },
      "saturation": { "selected": ["vibrant-high-saturation"], "intensity": [0.7] },
      "lighting": { "selected": ["bright-ambient"], "intensity": [0.8] },
      "texture": { "selected": ["clean-digital-canvas"], "intensity": [0.9] }
    },
    "character_appeal_genes": {
      "facial_features": { "selected": ["large-expressive-eyes"], "intensity": [0.9] },
      "body_type": { "selected": ["slender-build"], "intensity": [0.8] },
      "clothing_genre": { "selected": ["japanese-school-uniform"], "intensity": [0.9] },
      "clothing_fit": { "selected": ["pleated-silhouette"], "intensity": [0.8] }
    },
    "impression_colors": {
      "main": "#88C8FF",
      "secondary": "#F8B0D0",
      "accent": "#FFF2A8"
    }
  },
  "cr001_summary": "short combined style and appeal summary"
}
```

Canonical CR-001 loci registry：

- `genre`：`cel-shading`、`anime-heavy-paint`、`semi-realistic-anime`、
  `flat-illustration`、`2D-pop-art`、`vintage-manga`、`watercolor-anime`、
  `oil-painterly`。
- `line_art`：`clean-line-art`、`sketchy-lines`、`dynamic-linework`、
  `thick-contours`、`lineless`、`colored-line-art`、`soft-pencil-sketch`。
- `brush_shading`：`smooth-airbrush`、`hard-edge-shadow`、`textured-brush`、
  `impasto-stroke`、`soft-gradient`、`cross-hatching`、`halftone-dot`。
- `saturation`：`vibrant-high-saturation`、`pastel-tones`、`muted-low-saturation`、
  `morandi-palette`、`monochrome`、`neon-fluorescent`。
- `lighting`：`bright-ambient`、`high-contrast-chiaroscuro`、`rim-lighting`、
  `soft-volumetric-light`、`cinematic-backlight`、`overcast-diffused`。
- `texture`：`clean-digital-canvas`、`grainy-paper`、`canvas-texture`、
  `watercolor-bleed`、`vintage-film-grain`、`noise-artifacts`。
- `facial_features`：`large-expressive-eyes`、`tsundere-eyes`、`soft-blush-cheeks`、
  `sharp-jawline`、`prominent-eyelashes`、`detailed-hair-highlights`、`warm-smile`、
  `neutral-stare`。
- `body_type`：`slender-build`、`athletic-toned`、`hourglass-silhouette`、
  `petite-proportion`、`stylized-chibi`、`realistic-anatomy`、`elongated-limbs`。
- `clothing_genre`：`japanese-school-uniform`、`classic-sailor-fuku`、
  `techwear-futuristic`、`gothic-lolita`、`modern-casualwear`、`fantasy-armor`、
  `traditional-kimono`、`cyberpunk-gear`。
- `clothing_fit`：`oversized-fit`、`tailored-slim-fit`、`pleated-silhouette`、
  `high-waist-cut`、`asymmetric-layering`、`puff-sleeves`、`structural-drapery`。

Canonical grouping：

- Expected Art Style loci：`genre`、`line_art`、`brush_shading`、`saturation`、
  `lighting`、`texture`。
- Character Appeal loci：`facial_features`、`body_type`、`clothing_genre`、
  `clothing_fit`。

Candidate extended loci（`CR-001A+` deferred by default）：

- `composition`：`center-focused`、`rule-of-thirds`、`symmetrical-layout`、
  `dynamic-diagonal`、`close-up-portrait`、`full-body-showcase`、
  `cinematic-wide-shot`、`fisheye-perspective`、`low-angle-heroic`、
  `top-down-view`、`crowded-detail-rich`、`minimal-negative-space`。
- `mood_atmosphere`：`warm-cozy`、`melancholic`、`lonely-silent`、`dreamlike`、
  `energetic-chaotic`、`romantic-soft`、`mysterious`、`nostalgic`、
  `hopeful-bright`、`cold-detached`、`epic-grandiose`、`healing-gentle`。
- `color_harmony`：`analogous-colors`、`complementary-contrast`、`triadic-palette`、
  `split-complementary`、`warm-dominant`、`cool-dominant`、`high-value-contrast`、
  `low-contrast-foggy`、`dual-tone`、`rainbow-spectrum`。
- `impression_colors`：結構化印象色 palette，包含 `main`、`secondary`、`accent`
  三個 hex color strings，canonical output 格式為 uppercase `#RRGGBB`；此欄位描述
  整體主色、輔色與點綴色，不使用 `selected` / `intensity` allele 形式。
- `hair_style`：`long-flowing`、`short-bob`、`twin-tail`、`ponytail`、
  `messy-hair`、`ahoge`、`braided`、`curly-hair`、`straight-hair`、`wolf-cut`、
  `hime-cut`。
- `hair_rendering`：`sharp-anime-highlight`、`soft-gradient-hair`、
  `chunky-hair-strands`、`individual-strand-detail`、`glossy-hair`、`matte-hair`。
- `eye_rendering`：`sparkling-eyes`、`multi-layered-iris`、`flat-anime-eyes`、
  `glassy-reflection`、`star-shaped-highlights`、`gradient-iris`、
  `sharp-cat-eyes`、`droopy-eyes`、`heterochromia`。
- `visual_density`：`minimal-clean`、`balanced-detail`、`hyper-detailed`、
  `ornament-heavy`、`background-simplified`、`foreground-focused`、`texture-dense`。
- `world_setting`：`post-apocalyptic`、`fantasy-medieval`、`urban-modern`、
  `sci-fi-futuristic`、`idol-stage`、`military-tactical`、`magical-girl`、
  `school-life`、`steampunk`、`traditional-eastern`。
- `appeal_archetype`：`moe-cute`、`cool-beauty`、`mysterious`、`boyish-charm`、
  `elegant-refined`、`pure-innocent`、`energetic-genki`、`tsundere`、`kuudere`、
  `oneesan`、`villainous-allure`。

Extended loci policy：

- Canonical CR-001 初版應先支援 10 個核心 loci。
- Candidate extended loci 可拆成後續 `CR-001A+` 或 experimental items；未正式納入前，
  不得要求 baseline output 一定包含這些 keys。
- 若某個 extended locus 被啟用，必須走與 canonical loci 相同的 registry validation、
  intensity validation、traceability 與 no-custom-allele rules。
- 所有 CR-001 loci 使用 `selected` / `intensity` allele schema；唯一例外是
  `impression_colors`，它是 palette auxiliary output，而非 allele locus。
- `impression_colors` 不得放入 `CR001_ALLELE_REGISTRY`；若啟用，必須驗證三個
  channel 皆存在且可正規化為 canonical uppercase hex color string。

Schema / validation expectations：

- 除 `impression_colors` 外，每個 CR-001 locus 都必須使用 `selected` / `intensity`
  形式表示。
- `selected` 必須是 list，且每個 value 必須存在於該 locus 的 allele registry。
- `intensity` 必須是 list，長度必須等於 `selected`，每個值必須介於 `0.0` 到 `1.0`。
- 每個 canonical locus 初版應選 1 到 4 個 alleles；若未來要允許空值，需先定義
  explicit unknown / not-applicable policy。
- `impression_colors` 若出現，必須只包含 `main`、`secondary`、`accent`，每個值必須是
  可正規化為 uppercase `#RRGGBB` 的 hex color string；若 LLM raw response 回傳
  lowercase hex，parser / validator 必須自動轉成 uppercase canonical output，不得使用
  自由文字 color names 取代。
- Output 不可包含未知 top-level key、未知 locus key 或 registry 外的 allele。
- Summary 不得取代 structured fields；structured fields 才是後續 recombination、
  mutation、fitness scoring 與 audit 的來源。
- Parser / mapper 必須能使用 fixture LLM response 測試，不呼叫真實 Gemini API。
- API client / extractor 必須支援 dependency injection 與 fake transport。
- API failure 必須回報清楚 error，且不得修改 `style_gene_pool.json`。

Integration direction：

- Multi-objective fitness：分開衡量 expected style consistency、appeal strength、
  style uniqueness、genre purity 或其他後續定義的 fitness signals。
- Decoupled crossover：允許風格 loci 與角色賣點 loci 分別 recombine，例如保留一組
  watercolor style，同時交換另一組 clothing / silhouette genes。
- Mutation engine：允許 saturation、line art、composition、mood 或其他 loci 依
  mutation rate 漂移，但 mutation 只能引入 registry 中已知 alleles。
- Style matrix evolution：支援把 A 的風格、B 的角色設計、C 的情緒或世界觀組合成
  新 candidate seed。
- Latent compression：長期可把 style vector、appeal vector、mood vector 與 palette
  vector 壓縮成可 retrieval、clustering、interpolation 與 recommendation 的 profile seed。

Validation requirements：

- Registry tests 覆蓋 canonical 10 loci 與所有合法 alleles。
- Parser tests 覆蓋 valid JSON、invalid JSON、missing required loci、unknown loci、
  unknown allele、non-list `selected`、non-list `intensity`、長度不一致、非數字 intensity
  與 out-of-range intensity。
- Parser tests 覆蓋 `impression_colors` 的 missing channel、unknown channel、
  lowercase-to-uppercase normalization、invalid hex string 與 non-string value。
- Mapper tests 覆蓋 source image traceability、stable normalized gene IDs、duplicate
  allele handling、summary preservation 與 no gene pool overwrite。
- Extractor tests 使用 fake Gemini / fake vision client，確認 input 來自 reference
  image manifest records，output 可通過 schema validation，API failure 不破壞既有檔案。
- Manual integration probe 可作為非 CI 驗證；預設 unittest 不依賴 API key、network、
  Gemini quota 或真實 image analysis backend。

Devil's Advocate drill-down register：

目前 gate status：`ready-for-atomic-decomposition`。所有 blocking DA 項目已完成
decision / implementation verification，可進入 CR-001 atomic item decomposition。

目前 gate 判讀：

| ID | Current status | Blocks CR-001 atomic decomposition | Blocks existing Phase 0 / EXP |
|---|---|---|---|
| `DA-CR-001-003` | `resolved-by-spec-decision` | No | No |
| `DA-CR-001-004` | `resolved-by-playbook-change` | No | No |
| `DA-CR-001-005` | `resolved-by-spec-decision` | No | No |
| `DA-CR-001-006` | `verified-by-implementation-and-focused-mutation` | No | No |

## DA-CR-001-001: Morandi palette token typo

- Severity：Low。
- Issue：`saturation` allele 曾使用 `morandi-pallet`，容易把 typo 固化成 canonical ID。
- Suggestion：將 canonical token 修正為 `morandi-palette`，並同步所有 CR-001 來源文件。
- Decision：接受修正；`SPEC.md`、`backlog/CR-001-01-gemini-update.md` 與
  `backlog/CR-001-02-loci-expansion-table.md` 已同步使用 `morandi-palette`。
- Status：`resolved-by-spec-change`。

## DA-CR-001-002: `impression_colors` is not an allele locus

- Severity：Medium。
- Issue：`impression_colors` 不適合使用 `selected` / `intensity` allele schema；
  若混入 locus registry，parser、mapper、registry tests 與 mutation/crossover
  semantics 會被兩種資料規則拉扯。
- Suggestion：將 `impression_colors` 定義為 palette auxiliary output，使用獨立
  palette schema 驗證，不放入 `CR001_ALLELE_REGISTRY`。
- Decision：已確認。所有 CR-001 loci 使用 `selected` / `intensity` allele schema；
  唯一例外是 `impression_colors`，其 schema 為 `main`、`secondary`、`accent`
  三個 uppercase `#RRGGBB` hex color strings；若 LLM raw response 回傳 lowercase
  hex，必須正規化為 uppercase canonical output。
- Status：`resolved-by-spec-change`。

## DA-CR-001-003: Canonical, extended, and palette enablement order is unclear

- Severity：Medium。
- Issue：Canonical 10 loci、candidate extended loci 與 `impression_colors` 的初版啟用
  順序尚未完全定義；若直接實作，可能混淆 base schema、experimental loci 與 optional
  output。
- Suggestion：在拆 atomic item 前明確定義哪些欄位屬於 CR-001 base schema，哪些保留為
  `CR-001A+` 或 experimental items，以及 `impression_colors` 在初版中是 required
  或 optional。
- Decision：已定案 CR-001 v1 schema 啟用順序。Base required 為
  `expected_style_genes` 6 個 canonical style loci、`character_appeal_genes`
  4 個 canonical appeal loci，以及 top-level `cr001_summary`。Base optional 為
  `impression_colors`，採 optional but validated when present；缺席時不得卡死
  baseline，存在時必須通過 palette auxiliary schema。`composition`、
  `mood_atmosphere`、`color_harmony`、`hair_style`、`eye_rendering`、
  `visual_density`、`world_setting`、`appeal_archetype` 等 extended loci 暫不進
  v1 required schema，保留到 `CR-001A+` 或 experimental items。
- Rationale：CR-001 目前已明確說 canonical 初版先支援 10 個核心 loci，
  extended loci 拆到 `CR-001A+`，且 `impression_colors` 是 palette auxiliary
  output，不是 allele locus。
- Status：`resolved-by-spec-decision`。

## DA-CR-001-004: CR-001 currently has no accepted atomic decomposition

- Severity：High。
- Issue：CR-001 目前仍是 backlog / post-P0 change request，尚未有正式 accepted atomic
  item list；若直接進實作，第一刀可能錯切成 parser、Gemini prompt、artifact writer 或
  projection mapper。
- Suggestion：先完成 Devil's Advocate numbered drill-down gate，再進入 workflow /
  atomic decomposition。
- Decision：已確認目前工作流位置是 `spec -> Devil's Advocate Review -> numbered
  drill-down gate`；所有 blocking objections 完成 resolution 前，不得進入 CR-001
  atomic item decomposition。Playbook 已補入此 gate。
- Status：`resolved-by-playbook-change`。

## DA-CR-001-005: CR-001 artifact boundary is unclear

- Severity：High。
- Issue：CR-001 expected JSON 是 `appeal_point_and_art_style` + `cr001_summary`，但現有
  Phase 0 / batch flow 主要輸出 `style_gene_candidates.json`、
  `reference_image_analysis.json` 與 `batch_run_report.json`。現有 validator 也仍偏向
  三面向 Phase 0 candidate schema。
- Suggestion：第一個 CR-001 atomic item 前，先決定 CR-001 是否為獨立 primary artifact，
  或只是投影到 `style_gene_candidates.json`；若兩者都需要，應先保留 CR-001 原生
  artifact，再另拆 optional projection。
- Decision：CR-001 應先保留多面向 raw / native artifact，而不是直接壓平成
  `style_gene_candidates.json`。Expected style、character appearance、appeal traits、
  impression colors 與 summary 都是後續演算法可讀的原始觀測面向；後續 GA / search
  layer 可以固定幾個外型面向來收斂畫風，也可以固定畫風面向來探索角色變體。
- Status：`resolved-by-spec-decision`。

## DA-CR-001-006: Phase 0 / EXP Gemini batch evidence does not prove CR-001 schema readiness

- Severity：High。
- Issue：Human 測試中 batch Gemini 順利成功且沒有 timeout，屬於 Phase 0 / 相關 EXP
  允許產出的 integration evidence，可降低 transport / timeout 風險；但它不能證明
  CR-001 的 constrained allele output、registry validation、palette schema、
  summary preservation 或 source-image traceability 已可用。
- Suggestion：在進入 CR-001 前，先把這項歸入 Phase 0 / 相關 EXP 的 error-handling
  hardening：使用 fixture 或 fake vision client 補足 Gemini batch / manual probe 在
  CR-incompatible output、schema mismatch、partial failure 與 source traceability
  斷裂時的錯誤回報；真 API manual probe 只作為非 CI 驗證。
- Decision：已確認 human batch 成功是有價值的 Phase 0 / EXP integration evidence，
  不回溯阻擋 Phase 0 / 相關 EXP；但進入 CR-001 atomic decomposition 前，仍必須先
  補完 Phase 0 / EXP 端面向 CR-001 的 error handling 與 fixture-based validation。
  對應流程採 `raw -> valid raw -> downstream` gate：Gemini batch 或 single-image
  raw response 必須先保留為 raw evidence；只有通過 deterministic parser、schema
  validation、source-image traceability 與 optional palette validation 的 valid raw，
  才能進入 mapper、Phase 0 projection 或 CR-001 native artifact。Partial failure
  不得阻塞已 valid 的 raw，但必須在 report 中標示 failed scope、retryability、
  attempt count、remaining attempts 與後續 retry target。
- Code review note：retry 限次必須抽到 config / CLI policy 層，不得寫死在
  parser、batch runner、Gemini client 或 mapper 中。其他會影響執行成本、可靠性或
  provider 限制的 magic numbers（例如 batch size、timeout seconds、inline image
  byte limit、backoff interval、attempt budget）也應由具名 config / policy owner
  管理；若必須保留為常數，需有明確名稱、註解理由與測試覆蓋。
- Implementation evidence：`7972bf2` 已加入 Phase 0 / Gemini raw validation gate；
  `bae6f50` 已補 focused mutation coverage。驗證包含 full unittest、
  diff hygiene，以及 two scoped manual mutants：remaining retry budget 與 final
  invalid raw non-retryable status。
- Status：`verified-by-implementation-and-focused-mutation`（pre-CR Phase 0 / EXP
  error-handling prerequisite 已滿足；不阻擋既有 Phase 0 / EXP）。

## Atomic decomposition preparation draft

Status：`baseline-frozen`；CR-001 v1 native artifact baseline is accepted.
workflow_step：`Step 14 - Decision Proposal` completed；`CR-001-08` optional
projection remains deferred / non-primary and MUST NOT start until projection
policy is explicitly decided.

Current DA conclusion：

- 不應直接照現有 `CR-001-00` 到 `CR-001-08` 開始實作；目前清單方向正確，
  但部分 item 邊界會讓 validator、parser、prompt、adapter、artifact writer 與 batch
  integration 混入同一個 diff。
- `CR-001-02` 與 `CR-001-04` 有責任重疊。Gene payload validator 應只驗
  in-memory CR-001 record；raw response parser 應只處理 raw JSON parse、呼叫
  validator、產生 valid / invalid result。
- `CR-001-06` 太大。Gemini prompt contract 與 fake-client adapter / extractor
  應拆開，避免 prompt 測試、runtime transport seam 與 API dependency 混在一起。
- 缺少 single-image CR-001 extraction pipeline。應先有單張 reference image 的
  `raw -> valid raw -> native record` orchestration，再做 batch integration。
- `CR-001-05` 在開始前必須收斂 artifact path、schema version 與 source linkage
  欄位；若決策面過多，builder 與 writer 應再拆。
- `CR-001-08` 應維持 deferred / non-primary；optional projection 不屬於 v1
  baseline completion，不得和 native artifact 混成同一個 item。

Decomposition constraints：

- v1 required scope 只包含 10 個 canonical loci 與 `cr001_summary`。
- `impression_colors` 是 optional palette auxiliary output，present 時驗證，
  不放入 allele registry。
- `CR-001A+` extended loci 不進 v1 baseline required schema。
- CR-001 native artifact 先於 optional projection；不得直接壓平成
  `style_gene_candidates.json`。
- Parser / mapper 必須以 fixture 或 fake client 測試；baseline unittest 不呼叫
  真 Gemini API。
- 所有 downstream 行為必須遵守 `raw -> valid raw -> downstream` gate。

Recommended revised atomic items：

| ID | Recommended slice | Main output | Validation focus |
|---|---|---|---|
| `CR-001-00` | Acceptance scaffold | CR-001 v1 fixture set and test namespace | SDD/TDD anchor, no implementation behavior yet |
| `CR-001-01` | Canonical allele registry | `CR001_ALLELE_REGISTRY` for 10 loci | no unknown locus, no custom allele, `impression_colors` excluded |
| `CR-001-02` | In-memory CR-001 schema validator | validator for required record shape and `selected` / `intensity` loci | required loci, 1-4 selected alleles, matched intensity length, intensity range, summary presence |
| `CR-001-03` | Palette auxiliary validator | optional `impression_colors` validator | exact `main` / `secondary` / `accent`, uppercase `#RRGGBB`, lowercase raw normalized, optional but validated |
| `CR-001-04` | Raw response parser / valid-raw gate | raw JSON -> validation result and valid CR-001 record | malformed JSON, unknown key, schema mismatch, source traceability; no file write |
| `CR-001-05A` | Native artifact document builder | CR-001 native artifact document shape | schema version, source image linkage, summary preservation, no Phase 0 projection |
| `CR-001-05B` | Native artifact writer | write CR-001 native artifact under `phase0/` | stable output path, deterministic JSON, no overwrite of `style_gene_pool.json` |
| `CR-001-06A` | Gemini prompt contract | CR-001 restricted-allele prompt and fixture response | prompt references canonical registry and rejects free-form allele drift |
| `CR-001-06B` | Opt-in fake-client adapter / extractor | injectable CR-001 vision client seam | fake transport in tests, no API dependency in baseline unittest |
| `CR-001-07A` | Single-image CR-001 extraction orchestration | manifest record -> raw -> valid raw -> native record | valid raw isolation, source traceability, no batch complexity |
| `CR-001-07B` | Batch integration | partial success/failure CR-001 batch report | failed scope, retry metadata, configured attempt budget, output paths |
| `CR-001-08` | Optional projection | projection from CR-001 native artifact to Phase 0 candidates | deferred / non-primary, no gene pool overwrite |

Implementation progress:

- `CR-001-00` through `CR-001-05B` completed in prior commits.
- `CR-001-06A` completed: Gemini prompt contract is generated from the canonical
  registry, forbids free-form allele drift / extra raw keys, keeps
  `impression_colors` as optional palette auxiliary output, and remains fixture /
  unittest-only with no API dependency.
- `CR-001-06B` completed: CR-001 has an opt-in Gemini payload/client/raw
  extractor seam with injected fake transport in baseline tests. This slice
  returns raw response text only and does not parse, validate, write native
  artifacts, or call the real Gemini API in unittest.
- `CR-001-07A` completed: single-image orchestration now runs one manifest
  record through raw extraction and the valid-raw parser, preserves raw response
  text, enforces source-image traceability, and keeps invalid raw isolated from
  native records without file writes or batch behavior.
- `CR-001-07B` completed: batch integration writes
  `phase0/cr001_reference_image_analysis.json` and
  `phase0/cr001_batch_run_report.json`, preserves partial valid records when
  some images fail, retries failed image scope up to the configured attempt
  budget, records retry metadata / output paths, and does not write
  `style_gene_pool.json`.
- Manual CR-001 probe entrypoints completed: opt-in real Gemini manual test
  paths now exist for single-image and batch native artifact generation:

  ```text
  python -m style_fit_profiler.cr001_gemini_probe single <image>
  python -m style_fit_profiler.cr001_gemini_probe batch --input-dir reference_images
  ```

  These entrypoints write CR-001 native outputs only; they do not produce
  `style_gene_candidates.json` compatibility projection outputs.
- Legacy manual batch entrypoint aligned: the existing command now defaults to
  the CR-001 native backend:

  ```text
  python -m style_fit_profiler.gemini_batch_probe
  ```

  This lets the existing Phase 0 manual batch command act as the new CR-001
  Phase 0 path. The prior EXP / legacy three-aspect output remains available
  only through `--backend legacy`.
- Legacy manual single-image entrypoint aligned: the existing command now also
  defaults to the CR-001 native backend:

  ```text
  python -m style_fit_profiler.gemini_image_probe reference_images/ref-001.png
  ```

  The prior EXP / legacy three-aspect single-image output remains available
  only through `--backend legacy`.

## Follow-ups

| ID | Status | Spec | Source | Reason | Blocks frozen CR-001 v1 native baseline |
|---|---|---|---|---|---|
| `CR-001-FU-01` | DA reviewed；ready for atomic decomposition；next `CR-001-FU-01B` | [`CR-001-FU-01-deprecate-legacy-phase0-default-paths.md`](CR-001-FU-01-deprecate-legacy-phase0-default-paths.md) | [`../../backlog/CR-001-FU-01-deprecate-legacy-phase0-default-paths.md`](../../backlog/CR-001-FU-01-deprecate-legacy-phase0-default-paths.md) | Deprecate legacy Phase 0 default paths and make CR-001 native artifact the default manual Gemini Phase 0 baseline. | No. It is required before docs and entrypoint defaults can be called migration-clean. |

## Decision: CR-001 v1 native baseline freeze

Decision：Accepted.

CR-001 v1 is accepted as a native baseline. The primary output of CR-001 is:

```text
phase0/cr001_reference_image_analysis.json
```

This artifact preserves the richer CR-001-native structure, including expected
style genes, character appeal genes, optional impression colors, summaries, and
source traceability.

`CR-001-08` is deferred.

Reason：`CR-001-08` would introduce a lossy compatibility projection from
CR-001 native records into the legacy Phase 0 candidate gene format. This
projection requires an explicit policy for mapping CR-001 loci into the legacy
Phase 0 aspects:

- `rendering`
- `color_light`
- `texture_artifacts`

Until that policy is decided, CR-001 native artifacts must not be projected into
`style_gene_candidates.json`-like outputs, and must not be merged into
`style_gene_pool.json`.

### Deferred question before CR-001-08

Before starting `CR-001-08`, decide which CR-001 loci are eligible for
projection.

Likely safe:

- `genre` -> `rendering`
- `line_art` -> `rendering`
- `brush_shading` -> `rendering`
- `saturation` -> `color_light`
- `lighting` -> `color_light`
- `impression_colors` -> `color_light`
- `texture` -> `texture_artifacts`

Needs caution:

- `facial_features`
- `body_type`
- `clothing_genre`
- `clothing_fit`
- `character_appeal_genes`

These may represent character appeal / phenotype rather than legacy Phase 0
style genes.

Decision candidates already suitable for the revised table：

- Registry owner：start with a Python module constant for v1; defer external JSON registry
  until schema migration/versioning is needed.
- `confidence` / `intensity` / `fitness_score`：v1 owns `intensity` only；`confidence`
  belongs to extraction reliability if introduced later，`fitness_score` stays outside
  CR-001 parsing.
- Native artifact candidate path：`phase0/cr001_reference_image_analysis.json`。
- `impression_colors` producer：use hybrid validation. LLM semantic judgment is
  the primary source for perceived / narrative / emotional color impressions,
  while image palette extraction provides objective visual evidence and
  validation.
- `impression_colors` hex normalization：canonical artifact 固定輸出 uppercase
  `#RRGGBB`；LLM raw response 若回傳 lowercase hex，parser / validator 自動正規化
  為 uppercase。
  Rationale（ChatGPT 補充）：
  - 視覺辨識較清楚：uppercase `#A0B4FF` 比 lowercase `#a0b4ff` 更容易快速辨識為色碼。
  - 常見於設計規格與色票文件：design token、style guide、Adobe / Figma 匯出文件常偏向
    uppercase hex。
  - 避免混用造成 diff 雜訊：固定格式讓 Git diff、JSON 比對與 schema validation 更乾淨。
- Gene pool merge：human-reviewed merge required. CR-001 / Phase 0 outputs may
  inform review and proposed candidate genes, but merge to active
  `style_gene_pool.json` must remain a separate human-reviewed step before
  Phase 1 use.

### Native artifact schema version

Decision: Accepted.

CR-001 native artifact MUST include a top-level `schema_version` field. For
CR-001 v1, the value MUST be:

```json
"schema_version": "cr001.v1"
```

This field identifies the schema contract of the CR-001 native artifact
container. It describes the artifact container, not a single analysis result,
the allele registry, or any downstream projection.

Scope:

- Applies to `phase0/cr001_reference_image_analysis.json`.
- Produced by `CR-001-05A`.
- Written by `CR-001-05B`.

It MUST appear only at the top level of the CR-001 native artifact file. It MUST
NOT be placed inside:

- LLM raw response.
- `appeal_point_and_art_style`.
- `CR001_ALLELE_REGISTRY`.
- `style_gene_candidates.json` downstream projection.
- `style_gene_pool.json` finalized gene pool artifact.

Example:

```json
{
  "schema_version": "cr001.v1",
  "source": "cr001_reference_image_analysis",
  "records": [
    {
      "source_image": "reference_images/ref-001.png",
      "appeal_point_and_art_style": {},
      "cr001_summary": "..."
    }
  ]
}
```

### Native artifact builder / writer split

Decision: Accepted.

`CR-001-05A` and `CR-001-05B` are fixed as separate atomic items for CR-001 v1.
They MUST NOT be merged during v1 atomic decomposition.

`CR-001-05A` is the native artifact document builder. It owns the in-memory
CR-001 native artifact document shape, including top-level `schema_version`,
`source`, `records`, source image linkage, `appeal_point_and_art_style`, and
`cr001_summary`. It must not write files and must not produce Phase 0 projection
artifacts.

`CR-001-05B` is the native artifact writer. It owns filesystem output for the
already-built CR-001 native artifact, including `phase0/` directory creation,
the stable `phase0/cr001_reference_image_analysis.json` output path,
deterministic JSON formatting, and the no-overwrite rule for
`style_gene_pool.json`.

Rationale:

- Builder tests can validate document shape without filesystem side effects.
- Writer tests can focus on path, formatting, directory creation, and overwrite
  safety.
- Keeping data-contract errors separate from I/O errors reduces review and
  mutation-test ambiguity for the first CR-001 native artifact implementation.

### Impression colors producer policy

Decision: Hybrid validation.

`impression_colors` represents the perceived visual identity colors of the
reference image. It SHOULD be produced from LLM semantic judgment, with image
palette extraction used as evidence and validation.

LLM semantic judgment determines which colors are meaningful as character,
style, narrative, or emotional impressions. Image palette extraction provides
objective evidence for colors that are visually present in the source image.
The final `impression_colors` SHOULD prefer colors that are semantically
meaningful, visually supported, and useful for downstream style gene generation.

Palette extraction alone MUST NOT decide `impression_colors`, because dominant
image colors may come from background, lighting, shadows, or non-character
areas. In that case the result would be closer to `dominant_palette` or
`extracted_palette`, not impression colors.

LLM judgment alone SHOULD NOT be trusted without palette evidence, unless the
color is clearly tied to a visible semantic feature such as hair, eyes, outfit,
accessory, or atmosphere.

For CR-001 v1, this policy does not change the canonical `impression_colors`
output shape. The native artifact still stores the optional palette auxiliary
output as `main`, `secondary`, and `accent` uppercase hex strings. Richer
evidence metadata such as color name, role, source, or confidence may be added
later as validation evidence, `CR-001A+`, or EXP work, but is not required in
the v1 `impression_colors` object.

### Phase 1 active gene pool merge policy

Decision: Human-reviewed merge required.

CR-001 / Phase 0 outputs may produce native analysis artifacts and proposed
candidate genes, but Gemini broad traits MUST NOT be merged directly into the
active `style_gene_pool.json`.

The bridge from CR-001 / Phase 0 to Phase 1 is:

```text
reference images
  -> CR-001 / Phase 0 analysis
  -> phase0/cr001_reference_image_analysis.json
  -> optional projection / proposed candidate genes
  -> human review / edit / approve
  -> explicit merge into style_gene_pool.json
  -> Phase 1 uses active gene pool
```

Gemini broad traits may only enter the Phase 1 active gene pool after human
review, editing, deduplication, naming normalization, and explicit approval.
They are observations or candidate visual genes, not automatically accepted
active genes.

This policy preserves `style_gene_pool.json` as the active Phase 1 contract and
keeps CR-001 native artifact output separate from the governed merge step.

Non-scope:

- Automatic merge from CR-001 native artifact to `style_gene_pool.json`.
- Treating `phase0/cr001_reference_image_analysis.json` as the active gene pool.
- Overwriting `style_gene_pool.json` from Gemini / CR-001 extraction output.

Open questions before accepting revised atomic decomposition：

- None. All prior open questions have accepted decisions above.
