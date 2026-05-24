# CR-001: Appeal Point and Art Style Extraction

狀態：Backlog / Post-P0 Change Request，限 Phase 0 baseline 完成並驗證後再拆分實作。

來源摘要：

- `backlog/CR-001-01-gemini-update.md`：定義 Visual Style & Appeal Point Extractor、
  10 個核心 loci、restricted allele pool、LLM JSON output、schema guardrail，
  以及後續 GA / crossover 對接方向。
- `backlog/CR-XXX-chatgpt-replenish.md`：補充 composition、mood、color harmony、
  hair、eye、visual density、world setting 與 appeal archetype 等 Visual Genome
  延伸 loci，並提出 style crossover、mutation、fitness scoring 與 latent
  compression 的長期方向。
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
      "main": "#88c8ff",
      "secondary": "#f8b0d0",
      "accent": "#fff2a8"
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
  三個 hex color strings，格式為 `#RRGGBB`；此欄位描述整體主色、輔色與點綴色，
  不使用 `selected` / `intensity` allele 形式。
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
  channel 皆存在且為 canonical hex color string。

Schema / validation expectations：

- 除 `impression_colors` 外，每個 CR-001 locus 都必須使用 `selected` / `intensity`
  形式表示。
- `selected` 必須是 list，且每個 value 必須存在於該 locus 的 allele registry。
- `intensity` 必須是 list，長度必須等於 `selected`，每個值必須介於 `0.0` 到 `1.0`。
- 每個 canonical locus 初版應選 1 到 4 個 alleles；若未來要允許空值，需先定義
  explicit unknown / not-applicable policy。
- `impression_colors` 若出現，必須只包含 `main`、`secondary`、`accent`，每個值必須是
  `#RRGGBB` hex color string；不得使用自由文字 color names 取代。
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
  invalid hex string 與 non-string value。
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
  三個 `#RRGGBB` hex color strings。
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

Open questions：

- Allele registry 應硬編碼在 Python module、放在 JSON config，還是提供可版本化的
  registry file？
- `confidence`、`intensity` 與後續 `fitness_score` 的關係應如何定義？
- CR-001 raw artifact 的檔名、版本欄位、schema migration 與 optional Phase 0
  projection path 應如何命名？
- `impression_colors` 應由 LLM 判定、影像 palette extraction，還是兩者交叉驗證產生？
- Gemini broad traits 是否必須先經 human review，才可合併到 active gene pool？
