為配合您提及的 GitHub 專案 style-fit-profiler 中 CR-001: Appeal Point and Art Style Extraction 的規格需求，這份升級版的實作規格書已將先前的風格基因（Genotype）架構與 CR-001 的「預期風格（Expected Style）」與「吸睛點（Appeal Point）」概念完美融合。
同時，為了滿足更精緻的生圖與分析需求，我們在原有美學維度之外，擴充了「外型與特徵維度（Appearance & Anatomy Loci）」，包含五官、身材、服裝款式及版型。這份規格書採用高 Scannability 結構，可直接提交給 Codex 進行功能實作。
------------------------------
## 視覺風格與賣點特徵抽取器 (Visual Style & Appeal Point Extractor) 實作規格書## 1. 專案背景與目標 (CR-001 Context)
依據 CR-001: Appeal Point and Art Style Extraction 的規格要求，本模組旨在建立一個自動化的視覺特徵抽取系統。該系統需同時衡量「預期美學風格（Expected Art Style）」與「商業/視覺吸睛點（Appeal Points）」。

* 預期風格（底層基因 Genotype）：提供可量化的離散標籤與強度，作為基因演算法（GA）交叉遺傳的 Base。
* 吸睛點（表現型 Phenotype）：聚焦於角色的「外型特徵」與「服裝美學」，用以評估後續演算法生成的圖像是否達到預期的商業或視覺吸引力（Fitness Value 評估基礎）。

------------------------------
## 2. 核心架構：擴充版基因座與等位基因清單 (Expanded Loci Pool)
大模型必須嚴格在限定的等位基因池 (Allele Pool) 中選擇，每個被選中的標籤均需附帶一個 [0.0 - 1.0] 的強度評分（Intensity）。
## 🎨 A. 預期美學風格維度 (Expected Art Style - Style Loci)
(承襲前述美學基因，定義畫面的演化基調)

   1. 畫風流派 (Art Genre)
   * [cel-shading, anime-heavy-paint, semi-realistic-anime, flat-illustration, 2D-pop-art, vintage-manga, watercolor-anime, oil-painterly]
   2. 線條表現 (Line Art)
   * [clean-line-art, sketchy-lines, dynamic-linework, thick-contours, lineless, colored-line-art, soft-pencil-sketch]
   3. 筆觸與過渡 (Brushwork & Shading)
   * [smooth-airbrush, hard-edge-shadow, textured-brush, impasto-stroke, soft-gradient, cross-hatching, halftone-dot]
   4. 色彩飽和度 (Saturation Level)
   * [vibrant-high-saturation, pastel-tones, muted-low-saturation, morandi-pallet, monochrome, neon-fluorescent]
   5. 光影與環境 (Lighting & Tone)
   * [bright-ambient, high-contrast-chiaroscuro, rim-lighting, soft-volumetric-light, cinematic-backlight, overcast-diffused]
   6. 材質與肌理 (Texture Artifacts)
   * [clean-digital-canvas, grainy-paper, canvas-texture, watercolor-bleed, vintage-film-grain, noise-artifacts]
------------------------------
## 👁️ B. 推薦新增：外型與角色賣點維度 (Appeal Points - Appearance Loci)
(新增維度，精確解構角色的物理特徵與服裝樣式，作為 CR-001 Appeal Point 的量化指標)

   1. 五官與面部特徵 (Facial Features & Expression)
   * 說明：角色面部吸睛點。
      * [large-expressive-eyes, tsundere-eyes, soft-blush-cheeks, sharp-jawline, prominent-eyelashes, detailed-hair-highlights, warm-smile, neutral-stare]
   2. 身材與體型比例 (Body Types & Proportions)
   * 說明：角色的體型架構。
      * [slender-build, athletic-toned, hourglass-silhouette, petite-proportion, stylized-chibi, realistic-anatomy, elongated-limbs]
   3. 服裝款式與流派 (Clothing Style Genres)
   * 說明：服裝的整體核心主題。
      * [japanese-school-uniform, classic-sailor-fuku, techwear-futuristic, gothic-lolita, modern-casualwear, fantasy-armor, traditional-kimono, cyberpunk-gear]
   4. 服裝剪裁與版型 (Garment Silhouette & Fit)
   * 說明：衣服穿在角色身上的廓形。
      * [oversized-fit, tailored-slim-fit, pleated-silhouette, high-waist-cut, asymmetric-layering, puff-sleeves, structural-drapery]
------------------------------
## 3. LLM 提示詞工程 (Optimized Prompt for CR-001)
提交給 Vision LLM 的標準分析提示詞：

# Role
你是一位精準的「視覺風格與角色賣點編碼器 (Visual Style & Appeal Point Encoder)」。
你的任務是將輸入的圖像，依據 CR-001 規格，拆解為適合基因演算法 (Genetic Algorithm) 演化與篩選的結構化基因數據。

# Encoding Rules
請嚴格依據以下 10 個「基因座 (Loci)」，從給定的「等位基因 (Alleles) 清單」中為這張圖挑選最符合的 1~4 個關鍵字。
請勿自行創造清單外的模糊詞彙。

[ ⚠️ 請在此處插入上面的 10 個基因座與等位基因清單 ⚠️ ]

# Output Format
請嚴格以下列 JSON 格式輸出。每個被選中的標籤必須給予 0.0 到 1.0 的 Phenotype Intensity（表型強度評分），用以量化該特徵在畫面中的強烈程度。

⚠️ CRITICAL RULE: You are RESTRICTED to select terms ONLY from the provided Alleles list. Do NOT generate any custom keywords or synonyms outside the list.

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
      "facial_features": { "selected": ["large-expressive-eyes", "soft-blush-cheeks"], "intensity": [0.9, 0.7] },
      "body_type": { "selected": ["slender-build"], "intensity": [0.8] },
      "clothing_genre": { "selected": ["japanese-school-uniform"], "intensity": [0.9] },
      "clothing_fit": { "selected": ["pleated-silhouette"], "intensity": [0.8] }
    }
  },
  "cr001_summary": "一段 100 字以內，結合預期風格與角色吸睛賣點的綜合短評。"
}

------------------------------
## 4. 實作層邊界防禦 (Python Pydantic Schema)
Codex 實作時的校驗邏輯（新增外型與服裝維度的 Enum 限制）：

from typing import List, Dictfrom pydantic import BaseModel, field_validator
# 嚴格定義 CR-001 所有合法的基因池CR001_ALLELE_REGISTRY = {
    "genre": {"cel-shading", "anime-heavy-paint", "semi-realistic-anime", "flat-illustration", "2D-pop-art", "vintage-manga", "watercolor-anime", "oil-painterly"},
    "line_art": {"clean-line-art", "sketchy-lines", "dynamic-linework", "thick-contours", "lineless", "colored-line-art", "soft-pencil-sketch"},
    "brush_shading": {"smooth-airbrush", "hard-edge-shadow", "textured-brush", "impasto-stroke", "soft-gradient", "cross-hatching", "halftone-dot"},
    "saturation": {"vibrant-high-saturation", "pastel-tones", "muted-low-saturation", "morandi-pallet", "monochrome", "neon-fluorescent"},
    "lighting": {"bright-ambient", "high-contrast-chiaroscuro", "rim-lighting", "soft-volumetric-light", "cinematic-backlight", "overcast-diffused"},
    "texture": {"clean-digital-canvas", "grainy-paper", "canvas-texture", "watercolor-bleed", "vintage-film-grain", "noise-artifacts"},
    "facial_features": {"large-expressive-eyes", "tsundere-eyes", "soft-blush-cheeks", "sharp-jawline", "prominent-eyelashes", "detailed-hair-highlights", "warm-smile", "neutral-stare"},
    "body_type": {"slender-build", "athletic-toned", "hourglass-silhouette", "petite-proportion", "stylized-chibi", "realistic-anatomy", "elongated-limbs"},
    "clothing_genre": {"japanese-school-uniform", "classic-sailor-fuku", "techwear-futuristic", "gothic-lolita", "modern-casualwear", "fantasy-armor", "traditional-kimono", "cyberpunk-gear"},
    "clothing_fit": {"oversized-fit", "tailored-slim-fit", "pleated-silhouette", "high-waist-cut", "asymmetric-layering", "puff-sleeves", "structural-drapery"}
}
class GeneData(BaseModel):
    selected: List[str]
    intensity: List[float]
class StyleGenes(BaseModel):
    genre: GeneData
    line_art: GeneData
    brush_shading: GeneData
    saturation: GeneData
    lighting: GeneData
    texture: GeneData
class AppealGenes(BaseModel):
    facial_features: GeneData
    body_type: GeneData
    clothing_genre: GeneData
    clothing_fit: GeneData
class CR001Output(BaseModel):
    expected_style_genes: StyleGenes
    character_appeal_genes: AppealGenes
    cr001_summary: str

------------------------------
## 5. 針對後續 GA 演算法的對接優化說明

   1. 多目標優化 (Multi-Objective GA)：將特徵區分為「風格」與「角色賣點」後，演算法可採用 NSGA-II 演算法。一邊確保「畫風演化不崩壞（Expected Style 接近目標）」，另一邊確保「外型服裝足夠吸引人（Appeal Points 權重高）」。
   2. 解耦交配 (Decoupled Crossover)：Codex 實作此結構後，演算法可以輕易做到「保留 A 父母的【日系水彩畫風基因】，但遺傳 B 父母的【機能風服裝剪裁基因】」，讓畫風探索的基因組合更具備商業變化性。

------------------------------
這份規格書完整串聯了風格美學與外型維度。如果您接下來需要進一步定義「如何利用這些數據計算 Fitness Score（適應度分數）」，或者需要編寫 SPEC.md 的下一步測試案例 (Test Cases)，請隨時告訴我！





這裡為您整理一份 CR001_ALLELE_REGISTRY 所有合法基因標籤的中英對照表，已優化結構以便於您複製與備忘。
------------------------------
## 🎨 A. 預期美學風格維度 (Expected Art Style - Style Loci)## 1. 畫風流派 (Art Genre)

* cel-shading: 賽璐珞風格 / 塊狀陰影動漫風
* anime-heavy-paint: 動漫厚塗風格
* semi-realistic-anime: 半寫實動漫風
* flat-illustration: 扁平化插畫
* 2D-pop-art: 2D 普普藝術風
* vintage-manga: 復古/經典漫畫風
* watercolor-anime: 水彩動漫風
* oil-painterly: 類油畫/手繪感厚塗

## 2. 線條表現 (Line Art)

* clean-line-art: 乾淨線條 / 輪廓線清晰
* sketchy-lines: 草稿線條 / 帶有線條感
* dynamic-linework: 具粗細變化的感壓動態線條
* thick-contours: 粗輪廓線
* lineless: 無線條 / 數位厚塗無線稿
* colored-line-art: 有色線稿 / 彩色線條
* soft-pencil-sketch: 柔和鉛筆素描感線條

## 3. 筆觸與過渡 (Brushwork & Shading)

* smooth-airbrush: 平滑噴槍渲染 / 無痕陰影
* hard-edge-shadow: 硬邊界陰影 / 明確賽璐珞切面
* textured-brush: 帶有紋理的筆觸
* impasto-stroke: 堆砌感油畫刀筆觸 / 顯眼筆觸
* soft-gradient: 柔和漸層過渡
* cross-hatching: 交叉網狀排線陰影
* halftone-dot: 半調子網點 / 漫畫點陣

## 4. 色彩飽和度 (Saturation Level)

* vibrant-high-saturation: 高飽和度 / 鮮豔色彩
* pastel-tones: 馬卡龍粉嫩調 / 柔和粉色系
* muted-low-saturation: 低飽和度 / 暗淡柔和色調
* morandi-pallet: 莫蘭迪色系 / 高級灰調
* monochrome: 單色調 / 黑白灰
* neon-fluorescent: 霓虹螢光色彩

## 5. 光影與環境 (Lighting & Tone)

* bright-ambient: 明亮環境光 / 通透通亮
* high-contrast-chiaroscuro: 強烈明暗對比 / 舞台光效
* rim-lighting: 邊緣輪廓光 / 邊緣高光
* soft-volumetric-light: 柔和體積光 / 耶穌光
* cinematic-backlight: 電影感逆光
* overcast-diffused: 陰天漫射光 / 均勻柔和無明顯陰影

## 6. 材質與肌理 (Texture Artifacts)

* clean-digital-canvas: 乾淨數位畫布 / 完美無瑕
* grainy-paper: 顆粒感紙張紋理
* canvas-texture: 畫布/帆布肌理
* watercolor-bleed: 水彩暈染/邊緣水漬效果
* vintage-film-grain: 復古膠片噪點
* noise-artifacts: 數位噪點雜訊

------------------------------
## 👁️ B. 外型與角色賣點維度 (Appeal Points - Appearance Loci)## 7. 五官與面部特徵 (Facial Features & Expression)

* large-expressive-eyes: 水汪汪大眼睛 / 表現力豐富的雙眼
* tsundere-eyes: 傲嬌眼神 / 帶有銳利或輕蔑感的雙眼
* soft-blush-cheeks: 臉頰淡淡腮紅 / 微暈紅潤
* sharp-jawline: 清晰銳利的下巴線條
* prominent-eyelashes: 濃密纖長的睫毛
* detailed-hair-highlights: 精緻的頭髮高光/天使環
* warm-smile: 溫暖微笑
* neutral-stare: 三無/高冷無表情注視

## 8. 身材與體型比例 (Body Types & Proportions)

* slender-build: 纖細苗條身材
* athletic-toned: 精實/帶有肌肉線條的運動體型
* hourglass-silhouette: 沙漏型身材 / 凹凸有致
* petite-proportion: 嬌小玲瓏比例
* stylized-chibi: Q版/二頭身比例
* realistic-anatomy: 寫實人體解剖結構
* elongated-limbs: 修長四肢 / 漫畫風長腿

## 9. 服裝款式與流派 (Clothing Style Genres)

* japanese-school-uniform: 日系學校制服（西裝外套款）
* classic-sailor-fuku: 經典水手服
* techwear-futuristic: 未來感機能風服飾
* gothic-lolita: 哥德蘿莉塔風
* modern-casualwear: 現代時尚休閒服
* fantasy-armor: 幻想風格盔甲/防具
* traditional-kimono: 傳統和服/浴衣
* cyberpunk-gear: 賽博朋克風格裝備

## 10. 服裝剪裁與版型 (Garment Silhouette & Fit)

* oversized-fit: 寬鬆/落肩廓形版型
* tailored-slim-fit: 合身/修身剪裁
* pleated-silhouette: 百褶廓形（如百褶裙或多褶皺剪裁）
* high-waist-cut: 高腰剪裁 / 提升腰線設計
* asymmetric-layering: 不對稱層次疊穿
* puff-sleeves: 泡泡袖/燈籠袖設計
* structural-drapery: 具結構感的垂墜設計
