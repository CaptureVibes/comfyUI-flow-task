"""persona_tagging_service.py

TikTok 视频/博主人设打标核心逻辑。
移植自 persona-layer-tagging 项目，不依赖外部 HTTP 服务，直接调用本地 EvoLink API。

功能：
  - 5 阶段视频分析 Pipeline（描述单元 → 分类 → 风格向量 → 风格签名）
  - 博主级聚合（从多视频 description_unit 推断账号标签）
  - 32 维风格向量计算 / 8-facet 风格签名聚合
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.persona_tagging import BloggerTaggingResult, VideoTaggingResult
from app.models.video_source import VideoSource
from app.services.ai_api import call_gemini_api

logger = logging.getLogger("app.persona_tagging")

# ── 风格维度 ───────────────────────────────────────────────────────────────────

STYLE_NAMES = [
    "americana", "athleisure", "avant_garde", "bohemian", "casual", "classic",
    "clean", "coquette", "cottagecore", "cozy", "dark_academia", "edgy",
    "elegant", "gorpcore", "luxe", "minimal", "moto", "premium", "preppy",
    "quiet_luxury", "relaxed", "resort", "romantic", "sport", "streetwear",
    "sustainable", "tailored", "technical", "vintage", "western", "workwear", "y2k",
]

# ── Prompt 定义 ────────────────────────────────────────────────────────────────

PROMPT_1 = """你是一个 TikTok 单视频"账号级人设打标证据采集"模型。

我会提供一个 TikTok 视频，以及该视频对应的 caption 和 hashtags。

你的任务不是给单条视频打最终标签，而是为后续"账号级 Personal Tags 打标"收集高质量证据。
你需要重点描述那些会影响第二阶段判断的内容：基础人口视觉、身材/身体部位、消费层级线索、气质心理、社会身份、穿搭场景 Occasion、账号视觉记忆点。

你只能根据视频、视频内人物、画面、动作、场景、字幕、音频/说话内容，以及我提供的 caption 和 hashtags 判断。
不要使用外部信息。
允许基于视频内反复或明确出现的线索做"合理推测"，但必须写清楚推测依据。
不要猜测视频之外的人设、职业、收入、价格、身份或关系。
看不清、听不清、证据不足时写"无明确"。

# 重要：你需要做合理推测，而不是只描述直观现象

你不仅要记录"看到了什么"，还要记录"这些画面可能想营造什么账号信号"。
例如：
- 多次出现 gym、力量训练、运动套装、蛋白饮、健康餐、健身镜自拍，可以推测该视频在营造 Sport / Active、运动健康型、Muscular 或健身身材管理信号。
- 反复展示沙拉、低卡餐、meal prep、健康饮食、训练前后状态，可以推测该视频在强化健康自律、身材管理、运动健康型信号。
- 反复展示紧身裙、露肤、扭胯、镜前展示曲线，可以推测该视频在强化自信性感型、身体曲线展示、Party / Night-out 或 Date 场景信号。
- 反复展示通勤套装、办公室、电梯镜、电脑桌、会议感单品，可以推测 Work / Office、职场/专业型、精英利落型信号。
- 反复展示家居服、卧室、沙发、素颜、做饭、收纳，可以推测 At-home / Cozy、温柔亲和或安静内向信号。

推测必须满足：
1. 推测只能来自本视频中的画面、文字、语音、caption、hashtag。
2. 必须区分"直接证据"和"推测信号"。
3. 如果推测较弱，明确写"弱推测"。
4. 如果没有足够线索，写"无明确推测"。
5. 不要把单条视频推测直接当成账号最终结论。

# 一、重点观察方向

1. 主体人物
- 视频中有几个人
- 谁是主要展示对象
- 是否能明确判断为账号主体/博主本人
- 如果无法确认主体人物，写"无明确"

2. 基础人口视觉证据
- 性别/性向呈现：男、女、Gay、Les、Trans、无明显
- 年龄感：18-24、25-34、35-44、45+、无明显
- 族裔视觉：非裔、亚裔、拉美裔、白人、印度人、无明显
- 只能记录视觉呈现，不要推断真实身份

3. 身材与身体部位证据
- 身材视觉：Super Fat、Large、Plump、Normal、Skinny、Muscular、无明显
- 是否明显偏瘦、丰满、健身感、肌肉感、大码、中码、产后身材等
- 如果视频出现健康餐、健身房、训练动作、运动装备、蛋白饮、身体管理文案，即使肌肉不完全清晰，也要记录它可能在营造 Muscular / 运动健康 / 身材管理信号，并标注推测强度
- 是否反复或刻意展示某个部位：胸、手、脚、腿、屁股、头发、背
- 只记录这条视频中的证据，不要因为单条视频直接推断账号整体
- 如果只是普通入镜，不算"突出身体部位"

4. 穿搭与视觉形象
- 衣服类型：裙子、牛仔裤、运动套装、泳装、办公装、居家服、派对装等
- 版型：紧身、宽松、短款、露肤、修身、休闲、正式等
- 妆发、配饰、鞋包、颜色、整体精致度
- 是否存在稳定视觉记忆点，例如长发、健身身材、性感穿搭、通勤感、甜美感、冷感等

5. 消费层级线索
- 是否出现价格、品牌、商品链接、试穿、haul、购物推荐
- 商品看起来更偏高性价比、中端通勤、轻奢、奢侈品，还是无明确
- 只能基于视频中明确出现的信息、caption、hashtag 或可见品牌判断
- 不要凭主观感觉猜价格

6. 气质心理线索
- 人物表现更偏温柔亲和、自信性感、冷感高级、活力阳光、搞笑混乱、安静内向、精英利落、叛逆个性，还是无明显
- 根据表情、姿态、动作、镜头互动、说话方式、文案语气判断
- 也要根据视频想营造的生活方式推测气质，例如健身/健康餐可推测自律活力，通勤穿搭可推测精英利落，夜店/贴身穿搭可推测自信性感
- 只记录单视频证据，不要给账号下最终结论

7. 社会身份线索
- 是否有学生/校园、职场/专业、创作者/媒体、家庭/关系、运动/健康、艺术/文化、社交/派对等明确线索
- 如果只是穿搭展示，没有明确身份线索，写"无明确"

8. Occasion 场景线索
- 判断视频主要穿搭或内容场景：Work / Office、School / Campus、Everyday Casual、At-home / Cozy、Café / Brunch、Date、Party / Night-out、Travel / Transit、Vacation / Resort、Sport / Active、Special Occasion、无明显
- 如果多个场景都出现，说明主次

9. 说话 / 音频 / 屏幕文字
- 如果人物说话，尽量逐句记录
- 听不清时总结大意，并标注"听不清"
- 记录屏幕字幕、贴纸文字、价格、品牌、地点、尺码、商品卖点
- 不要把 caption 当成视频内说话内容

10. caption 和 hashtags
- 原样记录 caption
- 将 hashtags 拆成数组
- 说明它们对第二阶段判断有何帮助，例如 outfit、gym、midsize、workwear、vacation、party 等

# 二、输出要求

请只输出 JSON，不要输出解释性段落。

JSON 格式如下：

{
  "video_description_unit": {
    "video_index": 0,
    "video_url": "",
    "objective_video_summary": "",
    "main_subject": {
      "people_count": "",
      "main_person": "",
      "is_account_owner_clear": "",
      "uncertainty": ""
    },
    "account_tag_evidence": {
      "basic_demographics_evidence": {
        "gender_or_sexuality_presentation": "",
        "age_impression": "",
        "visual_ethnicity": "",
        "evidence": ""
      },
      "body_and_body_part_evidence": {
        "body_type_signal": "",
        "height_impression": "",
        "special_body_focus": [],
        "body_display_intensity": "",
        "inferred_body_or_fitness_signal": "",
        "inference_strength": "",
        "evidence": ""
      },
      "styling_and_visual_image_evidence": {
        "outfit_items": "",
        "fit_silhouette": "",
        "exposure_level": "",
        "hair_makeup_accessories": "",
        "visual_memory_points": ""
      },
      "consumption_tier_evidence": {
        "visible_brand_or_price": "",
        "product_type": "",
        "possible_consumption_signal": "",
        "evidence": ""
      },
      "temperament_psychology_evidence": {
        "visible_temperament_signal": "",
        "inferred_temperament_signal": "",
        "facial_expression_and_pose": "",
        "speech_or_caption_tone": "",
        "evidence": ""
      },
      "social_identity_evidence": {
        "visible_identity_signal": "",
        "evidence": ""
      },
      "occasion_evidence": {
        "primary_occasion_signal": "",
        "secondary_occasion_signal": "",
        "inferred_occasion_signal": "",
        "scene_environment": "",
        "evidence": ""
      }
    },
    "inferred_signals_from_video_clues": {
      "body_or_fitness_inference": "",
      "temperament_inference": "",
      "social_identity_inference": "",
      "occasion_inference": "",
      "inference_basis": "",
      "inference_strength": ""
    },
    "speech_and_audio": {
      "has_speech": "",
      "spoken_words_or_transcript": "",
      "speech_summary": "",
      "audio_context": ""
    },
    "on_screen_text": {
      "has_on_screen_text": "",
      "text_content": ""
    },
    "social_media_info": {
      "caption": "",
      "hashtags": [],
      "caption_hashtag_signal_for_account_analysis": ""
    },
    "single_video_signal_summary": {
      "strong_signals_for_account_level_analysis": "",
      "weak_or_one_off_signals": "",
      "uncertainties": ""
    }
  }
}"""

PROMPT_3 = """你是一个 TikTok 单视频 Personal Tags 分类模型。

我会提供一个 TikTok 视频的 metadata，以及第一阶段生成的 video_description_unit。

你的任务是：只针对这一条视频，对以下 10 个属性做单视频分类：
1. 性别 / 性向呈现
2. 年龄段
3. 族裔视觉
4. 身材类型
5. 身高感
6. 特殊极致 Body 部位
7. 阶层消费标签
8. 气质心理标签
9. 社会身份标签
10. Occasion 标签

不要判断审美风格。
不要使用外部信息。
只能根据视频描述、画面线索、人物、场景、动作、字幕、说话内容、caption 和 hashtags 判断。
允许基于视频内线索做合理推测，但 evidence 必须写清楚依据。
如果信息不足，必须选择对应的"无明显 / 无明确"类标签。
不要为了丰富结果而过度推断。

# 一、候选标签

## 1. 性别 / 性向呈现，6 选 1
- 男
- 女
- Gay
- Les
- Trans
- 无明显

只判断视频中的视觉/表达呈现，不判断真实身份。

## 2. 年龄段，5 选 1
- 18-24
- 25-34
- 35-44
- 45+
- 无明显

## 3. 族裔视觉，6 选 1
- 非裔
- 亚裔
- 拉美裔
- 白人
- 印度人
- 无明显

只判断视觉呈现，不判断真实族裔。

## 4. 身材类型，6 选 1
- Super Fat
- Large
- Normal
- Skinny
- Muscular
- 无明显

如果视频出现 gym、力量训练、健康餐、蛋白饮、运动套装、身材管理文案，即使肌肉视觉不完全清晰，也可以作为 Muscular / 运动健康 / 身材管理的辅助推测证据，但必须说明是推测。

## 5. 身高感，4 选 1
- Short
- Normal
- Tall
- 无明显

## 6. 特殊极致 Body 部位，可多选
- 胸
- 手
- 脚
- 腿
- 屁股
- 头发
- 背
- belly
- 无明显特殊 Body 部位

只有当这一条视频明显突出、强调、展示某个身体部位，并且它是该视频的视觉重点时，才选择该部位。
如果只是普通入镜，选择「无明显特殊 Body 部位」。

## 7. 阶层消费标签，6 选 1
- 高性价比：$0 - $60
- 中端通勤：$60 - $180
- 轻奢：$180 - $500
- 奢侈品：$500+
- 无明显消费层级
- Remix 消费型

只能基于明确价格、品牌、商品类型、购物推荐、haul、try-on、caption/hashtags 判断。
没有明确价格或品牌层级时，不要凭感觉猜，选「无明显消费层级」。

## 8. 气质心理标签，10 选 1
- 温柔亲和型
- 自信性感型
- 冷感高级型
- 活力阳光型
- 搞笑混乱型
- 安静内向型
- 精英利落型
- 叛逆个性型
- 无明显气质类型
- Remix 气质型

根据表情、姿态、动作、镜头互动、说话方式、文案语气、视频想营造的生活方式判断。

## 9. 社会身份标签，9 选 1
- 学生/校园型
- 职场/专业型
- 创作者/媒体型
- 家庭/关系型
- 运动/健康型
- 艺术/文化型
- 社交/派对型
- 无明确社会身份型
- Remix 身份型

学生/校园型：学校、上课、宿舍、考试、校园社交等线索明确。
职场/专业型：办公室、通勤、职业身份、专业工作场景明确。
创作者/媒体型：内容生产、镜头、视觉、时尚媒体、造型行业身份明确。
家庭/关系型：妈妈、妻子、女友、朋友关系、亲密关系、备婚等关系身份明确。
运动/健康型：健身、训练、Pilates、跑步、健康餐、身体管理等强相关。
艺术/文化型：读书、电影、音乐、博物馆、艺术、游戏、二次元等文化兴趣明确。
社交/派对型：派对、夜生活、朋友局、club、festival、girls night 等明确。
无明确社会身份型：普通穿搭展示、自拍、对镜展示、商品展示，但没有明确身份线索。
Remix 身份型：只有当单条视频中两个或以上身份都非常明确，且无法判断主次时才选。

不要因为她是 TikTok 博主就默认选「创作者/媒体型」。

## 10. Occasion 标签，13 选 1
- Work / Office
- School / Campus
- Everyday Casual
- At-home / Cozy
- Café / Brunch
- Date
- Party / Night-out
- Travel / Transit
- Vacation / Resort
- Sport / Active
- Special Occasion
- 无明显Occasion
- Remix Occasion

# 二、判断原则

1. 优先看视频画面和人物行为。
2. 其次看屏幕文字、字幕、贴纸文字。
3. 再参考 caption 和 hashtags。
4. caption 和 hashtags 只能作为辅助证据，不能覆盖视频画面。
5. 每个字段都必须输出一个最终标签；特殊 Body 部位输出 labels 数组。
6. 如果线索不足，使用对应的无明显/无明确标签。

# 三、输出要求

请只输出 JSON，不要输出解释性段落。

JSON 格式如下：

{
  "video_url": "",
  "gender_or_sexuality_classification": {
    "label": "",
    "confidence": "",
    "evidence": "",
    "secondary_signals": []
  },
  "age_range_classification": {
    "label": "",
    "confidence": "",
    "evidence": "",
    "secondary_signals": []
  },
  "visual_ethnicity_classification": {
    "label": "",
    "confidence": "",
    "evidence": "",
    "secondary_signals": []
  },
  "body_type_classification": {
    "label": "",
    "confidence": "",
    "evidence": "",
    "secondary_signals": []
  },
  "height_impression_classification": {
    "label": "",
    "confidence": "",
    "evidence": "",
    "secondary_signals": []
  },
  "special_body_parts_classification": {
    "labels": [],
    "confidence": "",
    "evidence": "",
    "secondary_signals": []
  },
  "consumption_tier_classification": {
    "label": "",
    "confidence": "",
    "evidence": "",
    "secondary_signals": []
  },
  "temperament_psychology_classification": {
    "label": "",
    "confidence": "",
    "evidence": "",
    "secondary_signals": []
  },
  "social_identity_classification": {
    "label": "",
    "confidence": "",
    "evidence": "",
    "secondary_signals": []
  },
  "occasion_classification": {
    "label": "",
    "confidence": "",
    "evidence": "",
    "secondary_signals": []
  },
  "reasoning_summary": ""
}

# 四、字段规则

1. label 必须严格使用候选标签中的一个。
2. special_body_parts_classification.labels 必须是候选 Body 部位数组；如果没有，填 ["无明显特殊 Body 部位"]。
3. confidence 只能填 high、medium、low。
4. evidence 简短说明为什么选这个标签。
5. secondary_signals 记录次要线索；如果没有，填 []。
6. 不允许输出规则外标签。
7. 不允许输出多个最终 label。"""

PROMPT_4 = """你是一个严格的 Fashion Style Classification Scorer。你的任务是根据单条 TikTok 视频的视觉内容、caption、hashtags，以及已生成的 video_description_unit，输出 32 维风格向量。

你必须只输出 JSON，不要输出解释、Markdown、注释或多余文本。

评分规则：
1. 只根据可见证据、video_description_unit、caption、hashtags 打分，不要脑补。
2. 视觉证据优先级最高，caption 次之，hashtags 最低。
3. 每个分数必须是 0 到 1 之间的小数。
4. 轻微信号给 0.1-0.3；明确单个视觉信号给 0.3-0.5；整体明显符合给 0.6-0.8；核心主导风格给 0.8-1.0。
5. 没有证据的风格必须接近 0。
6. 不要因为"日常"默认 casual；不要因为黑色默认 edgy；不要因为宽松默认 streetwear；不要因为运动鞋默认 sport。
7. 多个风格可以同时高分，但必须都有证据。

STYLE_DIMENSIONS：
americana: U.S. heritage 工装牛仔，撞色丹宁、格纹法兰绒、工装靴、自染丹宁、皮带
athleisure: 运动休闲混搭，leggings、jogger、运动鞋、拉链外套
avant_garde: 实验性剪裁，解构、不对称、建筑感垂坠、毛边
bohemian: 自由波西米亚，混印花、流苏、刺绣、自然纤维、层叠
casual: 日常舒适，软面料、丹宁、运动鞋、T 恤、easy 层叠
classic: 永恒传统剪裁，结构肩、传承图案、中性、海军蓝、酒红
clean: 极简邻近，白衬衫、压熨布料、利落剪裁、tonal 配色
coquette: 蝴蝶结、珍珠、芭蕾女孩感，粉色、蕾丝边、平底鞋
cottagecore: 田园浪漫，prairie 裙、格子、灯笼袖、花卉、围裙
cozy: 温暖触感，chunky 针织、sherpa、抓绒、暖色
dark_academia: 老欧洲学府哥特学者，tweed blazer、毛料长裤、牛津衫、马甲、圆框眼镜
edgy: 反主流强硬黑暗，黑色、铆钉、拉链、不对称、皮革
elegant: 优雅场合感，流畅垂感、长裙摆、暗光泽、宝石色
gorpcore: 户外功能日常化，puffer 马甲、trail runner、抓绒、cargo 裤、登山扣
luxe: 高端投资级，含蓄炫富，高端面料、精工、隐性 logo
minimal: 极简留白，单色调色、净空线条、无装饰、哑光
moto: 机车风，皮夹克、斜拉链、金属件、紧身、靴子
premium: 大众与奢华的桥梁，高品质、精细缝合、扎实面料、精炼配件
preppy: 学院风，polo、绞花针织、卡其、boat shoes、格纹、pastel
quiet_luxury: 隐形财富，零 logo、灰阶中性、羊绒、定制长裤、乐福鞋
relaxed: 故意宽松不急，落肩、阔腿、软针织、亚麻、oversized
resort: 度假海岸，亚麻套装、热带印花、wrap dress、草编
romantic: 怀旧自然柔美，荷叶边、蕾丝、碎花、柔色、灯笼袖
sport: 性能运动，技术面料、网眼、反光、压缩 fit
streetwear: 都市 hip-hop/滑板/青年文化，印花 T、运动鞋、连帽、oversized、大 logo、cargo
sustainable: 环保伦理，天然染、有机质感、土色、极简、手工感
tailored: 精剪定制，blazer、长裤、结构肩、压熨褶
technical: 高科技功能，防水壳、密封缝、通风片、模块化、techwear
vintage: 复古旧时代，复古剪影、年代印花、做旧水洗、高腰
western: 牛仔边境，牛仔靴、流苏、绿松石、领结
workwear: 工业工装日常化，cargo 口袋、工具圈、重磅布、加固缝、chore coat
y2k: 2000 复兴，低腰牛仔、baby tee、丝绒套装、蝴蝶图案、彩钻

输出格式必须严格如下，key 不得增减：
{
  "americana": 0.0,
  "athleisure": 0.0,
  "avant_garde": 0.0,
  "bohemian": 0.0,
  "casual": 0.0,
  "classic": 0.0,
  "clean": 0.0,
  "coquette": 0.0,
  "cottagecore": 0.0,
  "cozy": 0.0,
  "dark_academia": 0.0,
  "edgy": 0.0,
  "elegant": 0.0,
  "gorpcore": 0.0,
  "luxe": 0.0,
  "minimal": 0.0,
  "moto": 0.0,
  "premium": 0.0,
  "preppy": 0.0,
  "quiet_luxury": 0.0,
  "relaxed": 0.0,
  "resort": 0.0,
  "romantic": 0.0,
  "sport": 0.0,
  "streetwear": 0.0,
  "sustainable": 0.0,
  "tailored": 0.0,
  "technical": 0.0,
  "vintage": 0.0,
  "western": 0.0,
  "workwear": 0.0,
  "y2k": 0.0
}"""

PROMPT_5 = """你是一个严格的 Fashion Style Signature Extractor。你的任务是根据单条 TikTok 视频的视觉内容、caption、hashtags、video_description_unit，以及可选 style_vector，输出结构化 StyleSignature JSON。

你必须只输出 JSON，不要输出解释、Markdown、注释或多余文本。

核心原则：
1. 只根据可见证据、video_description_unit、caption、hashtags 判断，不要脑补。
2. 视觉证据优先级最高，caption 次之，hashtags 最低。
3. Layer 2 不是重新输出 32 个风格分数，而是描述这个造型的细粒度视觉指纹。
4. 所有枚举字段必须严格使用给定取值。
5. 所有 0-1 数值必须是小数，范围必须在 0 到 1。
6. 不确定时选择更保守、更中性的值。
7. 如果某字段没有足够证据，使用空数组、null、0 或中性默认值。
8. occasion_vector 是多标签相关度，不要求总和等于 1。
9. 不得输出 schema 之外的字段。
10. 输出必须是合法 JSON。

字段标准：
color_palette: dominant_colors 最多 5 个英文小写主色；temperature=warm/cool/neutral；saturation=muted/medium/vivid；contrast=low/medium/high；signature_combos 为配色组合；monochromatic_tendency=0-1。
material_profile: primary_materials 最多 5 个；texture_preference=smooth/textured/mixed；weight_preference=light/medium/heavy；transparency_level=opaque/semi-sheer/sheer；hardware_affinity=0-1。
silhouette_profile: fit_preference=slim/regular/oversized/mixed；proportion_play=balanced/top-heavy/bottom-heavy/volume-contrast；structure_level=unstructured/semi-structured/structured；length_preference 为 object；layering_complexity=minimal/moderate/maximal。
pattern_profile: pattern_types 数组；pattern_scale=small/medium/large/mixed；pattern_frequency=0-1；logo_visibility=none/subtle/prominent；print_mixing=true/false。
aesthetic_mood: energy=serene/balanced/dynamic/intense；formality_range 为长度 2 的数组，只能从 casual/semi-formal/formal 选择；gender_expression=feminine/androgynous/masculine/fluid；cultural_references 数组；mood_keywords 3-5 个英文关键词。
occasion_vector: 必须包含 everyday, casual, work, date_night, evening_out, party, formal, brunch, vacation, festival, beach, active。
price_positioning: tier=budget/mid-range/premium/luxury/mixed；investment_vs_trend=0-1；brand_consciousness=0-1。
era_influence: primary_era=90s/70s/y2k/contemporary/null；era_authenticity=faithful/reinterpreted/subtle-nod/null；retro_futurism=0-1。

输出格式必须严格如下：
{
  "color_palette": {
    "dominant_colors": [],
    "temperature": "neutral",
    "saturation": "muted",
    "contrast": "medium",
    "signature_combos": [],
    "monochromatic_tendency": 0.0
  },
  "material_profile": {
    "primary_materials": [],
    "texture_preference": "mixed",
    "weight_preference": "medium",
    "transparency_level": "opaque",
    "hardware_affinity": 0.0
  },
  "silhouette_profile": {
    "fit_preference": "regular",
    "proportion_play": "balanced",
    "structure_level": "semi-structured",
    "length_preference": {},
    "layering_complexity": "minimal"
  },
  "pattern_profile": {
    "pattern_types": [],
    "pattern_scale": "medium",
    "pattern_frequency": 0.0,
    "logo_visibility": "none",
    "print_mixing": false
  },
  "aesthetic_mood": {
    "energy": "balanced",
    "formality_range": ["casual", "semi-formal"],
    "gender_expression": "fluid",
    "cultural_references": [],
    "mood_keywords": []
  },
  "occasion_vector": {
    "everyday": 0.0,
    "casual": 0.0,
    "work": 0.0,
    "date_night": 0.0,
    "evening_out": 0.0,
    "party": 0.0,
    "formal": 0.0,
    "brunch": 0.0,
    "vacation": 0.0,
    "festival": 0.0,
    "beach": 0.0,
    "active": 0.0
  },
  "price_positioning": {
    "tier": "mid-range",
    "investment_vs_trend": 0.0,
    "brand_consciousness": 0.0
  },
  "era_influence": {
    "primary_era": null,
    "era_authenticity": null,
    "retro_futurism": 0.0
  }
}"""

PROMPT_6 = """你是一个 TikTok 博主账号级一句话总结模型。

我会提供同一个博主的 TikTok 主页 profile/bio 文案，以及多个 video_description_unit。
请把 profile/bio 和所有 video_description_unit 当作同一个账号的整体信息来分析，不要逐条视频总结，不要输出统计过程。

你的任务是生成一个字段：account_one_sentence_summary。
它是一句话，用来快速说明这个博主是谁、在做什么、为什么有人看、适合怎么复刻成 AI 博主。

特别注意：
- profile/bio 是账号自我介绍，通常比单条视频更能说明地点、职业、身份、内容定位、联系方式或账号人设。
- 如果 profile/bio 里有重要信息，并且不与视频内容明显冲突，要优先用于判断"他是谁"和"账号主要定位"。
- 邮箱、合作方式等联系方式一般不要写进最终总结，除非它能证明职业/商业属性。
- 如果 profile/bio 很空、只有 emoji、只有联系方式，主要根据 video_description_unit 判断。

分析逻辑按这 4 步：

1. 他是谁？
判断这个人的基础身份和第一印象，包括：
年龄感、性别/性向呈现、族裔视觉、身材、社会身份、气质、审美。
重点回答：这个人看起来像什么样的人？

2. 他在做什么？
判断这个账号主要在做哪类内容。
重点回答：这个账号主要靠什么内容运转？

3. 为什么有人看他？
判断这个博主的核心吸引力，例如：
好看、会穿、生活有代入感、内容有用、能帮人买东西、有情绪价值、代表某类人群。
重点回答：观众为什么愿意停下来继续看？

4. 他能被怎么复刻？
判断这个博主对 AI 账号生产的价值，例如：
美美展示型 AI 博主、穿搭方法型 AI 博主、人设生活型 AI 博主、可拆素材但不适合整体复刻、不适合复刻。
重点回答：这个博主适合被复刻成什么方向的 AI 博主？

输出要求：
- 只输出 JSON。
- 只输出一个字段 account_one_sentence_summary。
- 不要输出分析过程。
- 不要输出 evidence。
- 不要输出多个版本。
- 不要编造 profile/bio 或 video_description_unit 里完全没有的强信息。
- 如果信息不明确，用"无明显""偏""可能"这类保守表达。
- 句子尽量自然、短、可直接给业务方看。

最终句式尽量遵循：

这是一个【什么样的人】，主要在做【什么类型的内容】，用户看TA是因为【核心吸引力】，适合被复刻成【什么方向的 AI 博主】。

输出 JSON 格式：

{
  "account_one_sentence_summary": ""
}"""


BLOGGER_ACCOUNT_PROMPT = """你是一个 TikTok 博主账号级 Personal Tags 打标模型。

我会提供同一个 TikTok 博主的多个 video_description_unit。
你只能根据这些单视频描述单元，判断这个账号稳定呈现的 3 类标签：
1. 基础人口
2. 消费层级
3. 气质心理

不要输出 social_identity。
不要输出 occasion。
不要输出 style。
不要输出账号定位总结。
不要输出证据摘要。
不要输出 schema 之外的字段。

如果信息不足，必须选择"无明显 / 无明确"类标签。
只有多条视频反复稳定出现的信号，才作为账号级最终标签。

基础人口标签：
性别 / 性向呈现：男 / 女 / Gay / Les / Trans / 无明显
年龄段：18-24 / 25-34 / 35-44 / 45+ / 无明显
族裔视觉：非裔 / 亚裔 / 拉美裔 / 白人 / 印度人 / 无明显
身材类型：Super Fat / Large / Plump / Normal / Skinny / Muscular / 无明显
身高感：Short / Normal / Tall / 无明显
特殊 Body 部位：胸 / 手 / 脚 / 腿 / 屁股 / 头发 / 背 / belly / 无明显特殊 Body 部位

消费层级：
高性价比：$0 - $60 / 中端通勤：$60 - $180 / 轻奢：$180 - $500 / 奢侈品：$500+ / 无明显消费层级 / Remix 消费型

气质心理：
温柔亲和型 / 自信性感型 / 冷感高级型 / 活力阳光型 / 搞笑混乱型 / 安静内向型 / 精英利落型 / 叛逆个性型 / 无明显气质类型 / Remix 气质型

请只输出 JSON：
{
  "basic_demographics": {
    "gender_or_sexuality_presentation": "",
    "age_range": "",
    "visual_ethnicity": "",
    "body_type": "",
    "height_impression": "",
    "special_body_parts": []
  },
  "consumption_tier": "",
  "temperament_psychology": "",
  "confidence": {
    "basic_demographics": "",
    "consumption_tier": "",
    "temperament_psychology": ""
  }
}"""


# ── JSON 解析工具 ───────────────────────────────────────────────────────────────

def parse_json_text(text: str) -> dict | None:
    if not text:
        return None
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.S)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(cleaned[start: end + 1])
        except Exception:
            return None
    return None


# ── Prompt 构建 ────────────────────────────────────────────────────────────────

def _build_video_prompt(base_prompt: str, video_url: str, caption: str, hashtag: str, video_index: int) -> str:
    return (
        f"{base_prompt}\n\n"
        f"本条视频 metadata：\n"
        f"- video_index: {video_index}\n"
        f"- video_url: {video_url}\n"
        f"- caption: {caption or '无'}\n"
        f"- hashtags: {hashtag or '无'}\n\n"
        f"请把以上 caption 和 hashtags 写入 social_media_info 字段。"
    )


def _build_classification_prompt(base_prompt: str, video_url: str, caption: str, hashtag: str, unit: dict) -> str:
    return (
        f"{base_prompt}\n\n"
        f"本条视频 metadata：\n"
        f"- video_url: {video_url}\n"
        f"- caption: {caption or '无'}\n"
        f"- hashtags: {hashtag or '无'}\n\n"
        f"第一阶段 video_description_unit：\n"
        f"{json.dumps(unit, ensure_ascii=False, indent=2)}"
    )


def _build_style_vector_prompt(base_prompt: str, video_url: str, caption: str, hashtag: str, unit: dict) -> str:
    return (
        f"{base_prompt}\n\n"
        f"本条视频 metadata：\n"
        f"- video_url: {video_url}\n"
        f"- caption: {caption or '无'}\n"
        f"- hashtags: {hashtag or '无'}\n\n"
        f"第一阶段 video_description_unit：\n"
        f"{json.dumps(unit, ensure_ascii=False, indent=2)}"
    )


def _build_style_signature_prompt(
    base_prompt: str, video_url: str, caption: str, hashtag: str,
    unit: dict, style_vector: dict | None = None,
) -> str:
    return (
        f"{base_prompt}\n\n"
        f"本条视频 metadata：\n"
        f"- video_url: {video_url}\n"
        f"- caption: {caption or '无'}\n"
        f"- hashtags: {hashtag or '无'}\n\n"
        f"第一阶段 video_description_unit：\n"
        f"{json.dumps(unit, ensure_ascii=False, indent=2)}\n\n"
        f"可选 style_vector：\n"
        f"{json.dumps(style_vector or {}, ensure_ascii=False, indent=2)}"
    )


def _build_blogger_account_prompt(units: list[dict]) -> str:
    return (
        f"{BLOGGER_ACCOUNT_PROMPT}\n\n"
        f"以下是该账号的 {len(units)} 个 video_description_unit：\n"
        f"{json.dumps(units, ensure_ascii=False, indent=2)}"
    )


# ── LLM 调用封装 ───────────────────────────────────────────────────────────────

_DEFAULT_MODEL = "gemini-3.1-pro-preview"


async def _call_text(prompt: str, model: str | None = None, temperature: float = 0.3) -> str:
    return await call_gemini_api(
        model_name=model or _DEFAULT_MODEL,
        prompt=prompt,
        temperature=temperature,
        timeout=180.0,
    )


# ── 单视频 4 阶段分析 ──────────────────────────────────────────────────────────

async def analyze_video_description_unit(
    video_url: str,
    gcs_url: str,
    caption: str,
    hashtag: str,
    video_index: int = 1,
    model: str | None = None,
) -> dict:
    """阶段1：生成单视频描述单元（通过视频 URL）。返回 {parsed, raw_text, error}。"""
    try:
        prompt = _build_video_prompt(PROMPT_1, video_url, caption, hashtag, video_index)
        text = await call_gemini_api(
            model_name=model or _DEFAULT_MODEL,
            prompt=prompt,
            video_url=gcs_url,
            temperature=0.3,
            timeout=180.0,
        )
        parsed = parse_json_text(text)
        if parsed and "video_description_unit" in parsed:
            parsed = parsed["video_description_unit"]
        return {"parsed": parsed, "raw_text": text, "error": ""}
    except Exception as exc:
        logger.warning("analyze_video_description_unit failed: %s", exc)
        return {"parsed": None, "raw_text": "", "error": str(exc)}


async def analyze_video_classification(
    video_url: str,
    caption: str,
    hashtag: str,
    unit: dict,
    model: str | None = None,
) -> dict:
    """阶段3：单视频 10 属性分类。"""
    try:
        prompt = _build_classification_prompt(PROMPT_3, video_url, caption, hashtag, unit)
        text = await _call_text(prompt, model=model)
        return {"parsed": parse_json_text(text), "raw_text": text, "error": ""}
    except Exception as exc:
        logger.warning("analyze_video_classification failed: %s", exc)
        return {"parsed": None, "raw_text": "", "error": str(exc)}


async def analyze_video_style_vector(
    video_url: str,
    caption: str,
    hashtag: str,
    unit: dict,
    model: str | None = None,
) -> dict:
    """阶段4：32 维风格向量。"""
    try:
        prompt = _build_style_vector_prompt(PROMPT_4, video_url, caption, hashtag, unit)
        text = await _call_text(prompt, model=model)
        return {"parsed": parse_json_text(text), "raw_text": text, "error": ""}
    except Exception as exc:
        logger.warning("analyze_video_style_vector failed: %s", exc)
        return {"parsed": None, "raw_text": "", "error": str(exc)}


async def analyze_video_style_signature(
    video_url: str,
    caption: str,
    hashtag: str,
    unit: dict,
    style_vector: dict | None = None,
    model: str | None = None,
) -> dict:
    """阶段5：8-facet 风格签名。"""
    try:
        prompt = _build_style_signature_prompt(PROMPT_5, video_url, caption, hashtag, unit, style_vector)
        text = await _call_text(prompt, model=model)
        return {"parsed": parse_json_text(text), "raw_text": text, "error": ""}
    except Exception as exc:
        logger.warning("analyze_video_style_signature failed: %s", exc)
        return {"parsed": None, "raw_text": "", "error": str(exc)}


async def analyze_blogger_account(units: list[dict], model: str | None = None) -> dict:
    """博主账号级标签（基础人口 + 消费层级 + 气质心理）。"""
    try:
        prompt = _build_blogger_account_prompt(units)
        text = await _call_text(prompt, model=model)
        return {"parsed": parse_json_text(text), "raw_text": text, "error": ""}
    except Exception as exc:
        logger.warning("analyze_blogger_account failed: %s", exc)
        return {"parsed": None, "raw_text": "", "error": str(exc)}


async def analyze_blogger_one_sentence_summary(
    units: list[dict],
    blogger_profile: str = "",
    model: str | None = None,
) -> dict:
    """生成博主一句话总结，结合 profile/bio 和 video_description_unit。"""
    try:
        profile = (blogger_profile or "").strip() or "无"
        prompt = (
            f"{PROMPT_6}\n\n"
            f"以下是该 TikTok 博主主页 profile/bio 文案。它可能包含地点、职业、身份、内容定位、联系方式或自我介绍；"
            f"如果它提供了重要且可信的信息，请优先用于判断这个人是谁和账号定位，但不要编造 profile 里没有的信息：\n"
            f"{profile}\n\n"
            f"以下是该账号的 {len(units)} 个 video_description_unit：\n"
            f"{json.dumps(units, ensure_ascii=False, indent=2)}"
        )
        text = await _call_text(prompt, model=model)
        parsed = parse_json_text(text)
        summary = ""
        if isinstance(parsed, dict):
            summary = (parsed.get("account_one_sentence_summary") or "").strip()
        return {"parsed": parsed, "raw_text": text, "summary": summary, "error": ""}
    except Exception as exc:
        logger.warning("analyze_blogger_one_sentence_summary failed: %s", exc)
        return {"parsed": None, "raw_text": "", "summary": "", "error": str(exc)}


# ── 聚合工具函数 ───────────────────────────────────────────────────────────────

def _top_counts(values: list, limit: int = 5) -> list:
    counts: dict = {}
    first_seen: dict = {}
    for v in values:
        if v in ("", None, "null"):
            continue
        if not isinstance(v, (str, int, float, bool)):
            v = json.dumps(v, ensure_ascii=False, sort_keys=True)
        if v not in first_seen:
            first_seen[v] = len(first_seen)
        counts[v] = counts.get(v, 0) + 1
    return [
        v for v, _ in sorted(counts.items(), key=lambda x: (-x[1], first_seen[x[0]]))[:limit]
    ]


def _mode_value(values: list, default: Any = "") -> Any:
    top = _top_counts(values, limit=1)
    return top[0] if top else default


def _numeric_mean(values: list, default: float = 0.0) -> float:
    nums = [float(v) for v in values if isinstance(v, (int, float))]
    if not nums:
        return default
    return round(sum(nums) / len(nums), 4)


def _frequent_values(values: list, total: int, limit: int = 5, min_count: int = 2, min_share: float = 0.3) -> list:
    counts: dict = {}
    first_seen: dict = {}
    for v in values:
        if v in ("", None, "null"):
            continue
        if not isinstance(v, (str, int, float, bool)):
            v = json.dumps(v, ensure_ascii=False, sort_keys=True)
        if v not in first_seen:
            first_seen[v] = len(first_seen)
        counts[v] = counts.get(v, 0) + 1
    threshold = 1 if total < 3 else max(min_count, int(total * min_share + 0.9999))
    rows = sorted(counts.items(), key=lambda x: (-x[1], first_seen[x[0]]))
    filtered = [v for v, c in rows if c >= threshold]
    if not filtered and rows:
        filtered = [rows[0][0]]
    return filtered[:limit]


def _majority_bool(values: list) -> bool:
    bools = [v for v in values if isinstance(v, bool)]
    if not bools:
        return False
    return sum(1 for v in bools if v) / len(bools) >= 0.5


def _mixed_or_mode(values: list, default: str = "mixed") -> str:
    filtered = [v for v in values if v not in ("", None, "null")]
    if not filtered:
        return default
    counts: dict = {}
    first_seen: dict = {}
    for v in filtered:
        if v not in first_seen:
            first_seen[v] = len(first_seen)
        counts[v] = counts.get(v, 0) + 1
    top_v, top_c = sorted(counts.items(), key=lambda x: (-x[1], first_seen[x[0]]))[0]
    return top_v if top_c / len(filtered) >= 0.5 else default


def _aggregate_length_preferences(values: list) -> dict:
    buckets: dict = {}
    for item in values:
        if not isinstance(item, dict):
            continue
        for k, v in item.items():
            if v in ("", None, "null"):
                continue
            buckets.setdefault(k, []).append(v)
    return {k: _mode_value(vs) for k, vs in buckets.items()}


def aggregate_account_style_signature(signatures: list[dict]) -> dict:
    total = len(signatures)
    color = [s.get("color_palette") or {} for s in signatures]
    material = [s.get("material_profile") or {} for s in signatures]
    silhouette = [s.get("silhouette_profile") or {} for s in signatures]
    pattern = [s.get("pattern_profile") or {} for s in signatures]
    mood = [s.get("aesthetic_mood") or {} for s in signatures]
    price = [s.get("price_positioning") or {} for s in signatures]
    era = [s.get("era_influence") or {} for s in signatures]

    occasion_totals: dict = {}
    occasion_count = 0
    for s in signatures:
        occ = s.get("occasion_vector") or {}
        if not isinstance(occ, dict):
            continue
        occasion_count += 1
        for k, v in occ.items():
            if isinstance(v, (int, float)):
                occasion_totals[k] = occasion_totals.get(k, 0.0) + float(v)
    occasion_vector = {
        k: round(v / occasion_count, 4)
        for k, v in sorted(occasion_totals.items())
    } if occasion_count else {}

    primary_era = _mode_value([i.get("primary_era") for i in era if i.get("primary_era") is not None], None)
    era_authenticity = _mode_value(
        [i.get("era_authenticity") for i in era if i.get("era_authenticity") is not None], None
    )

    return {
        "color_palette": {
            "dominant_colors": _frequent_values(
                [v for i in color for v in (i.get("dominant_colors") or [])], total,
            ),
            "temperature": _mode_value([i.get("temperature") for i in color], "neutral"),
            "saturation": _mode_value([i.get("saturation") for i in color], "muted"),
            "contrast": _mode_value([i.get("contrast") for i in color], "medium"),
            "signature_combos": _frequent_values(
                [v for i in color for v in (i.get("signature_combos") or [])], total, limit=3,
            ),
            "monochromatic_tendency": _numeric_mean([i.get("monochromatic_tendency") for i in color]),
        },
        "material_profile": {
            "primary_materials": _frequent_values(
                [v for i in material for v in (i.get("primary_materials") or [])], total,
            ),
            "texture_preference": _mode_value([i.get("texture_preference") for i in material], "mixed"),
            "weight_preference": _mode_value([i.get("weight_preference") for i in material], "medium"),
            "transparency_level": _mode_value([i.get("transparency_level") for i in material], "opaque"),
            "hardware_affinity": _numeric_mean([i.get("hardware_affinity") for i in material]),
        },
        "silhouette_profile": {
            "fit_preference": _mode_value([i.get("fit_preference") for i in silhouette], "regular"),
            "proportion_play": _mode_value([i.get("proportion_play") for i in silhouette], "balanced"),
            "structure_level": _mode_value([i.get("structure_level") for i in silhouette], "semi-structured"),
            "length_preference": _aggregate_length_preferences([i.get("length_preference") for i in silhouette]),
            "layering_complexity": _mode_value([i.get("layering_complexity") for i in silhouette], "minimal"),
        },
        "pattern_profile": {
            "pattern_types": _frequent_values(
                [v for i in pattern for v in (i.get("pattern_types") or [])], total,
            ),
            "pattern_scale": _mode_value([i.get("pattern_scale") for i in pattern], "medium"),
            "pattern_frequency": _numeric_mean([i.get("pattern_frequency") for i in pattern]),
            "logo_visibility": _mode_value([i.get("logo_visibility") for i in pattern], "none"),
            "print_mixing": _majority_bool([i.get("print_mixing") for i in pattern]),
        },
        "aesthetic_mood": {
            "energy": _mode_value([i.get("energy") for i in mood], "balanced"),
            "formality_range": [
                _mode_value(
                    [i.get("formality_range", [None, None])[0] for i in mood
                     if isinstance(i.get("formality_range"), list)],
                    "casual",
                ),
                _mode_value(
                    [i.get("formality_range", [None, None])[1] for i in mood
                     if isinstance(i.get("formality_range"), list) and len(i.get("formality_range")) > 1],
                    "semi-formal",
                ),
            ],
            "gender_expression": _mode_value([i.get("gender_expression") for i in mood], "fluid"),
            "cultural_references": _frequent_values(
                [v for i in mood for v in (i.get("cultural_references") or [])], total,
            ),
            "mood_keywords": _frequent_values(
                [v for i in mood for v in (i.get("mood_keywords") or [])], total,
            ),
        },
        "occasion_vector": occasion_vector,
        "price_positioning": {
            "tier": _mixed_or_mode([i.get("tier") for i in price], "mid-range"),
            "investment_vs_trend": _numeric_mean([i.get("investment_vs_trend") for i in price]),
            "brand_consciousness": _numeric_mean([i.get("brand_consciousness") for i in price]),
        },
        "era_influence": {
            "primary_era": primary_era,
            "era_authenticity": era_authenticity,
            "retro_futurism": _numeric_mean([i.get("retro_futurism") for i in era]),
        },
    }


def aggregate_style_results(
    style_vectors: list[dict],
    style_signatures: list[dict],
) -> dict:
    """聚合多视频的风格向量和签名，生成账号级风格摘要。"""
    vector_totals: dict = {}
    vector_count = 0
    for item in style_vectors:
        if not item or item.get("error"):
            continue
        vector = item.get("parsed") or {}
        if isinstance(item, dict) and "parsed" not in item:
            vector = item
        numeric = {
            k: float(v)
            for k, v in vector.items()
            if k in STYLE_NAMES and isinstance(v, (int, float))
        }
        if not numeric:
            continue
        vector_count += 1
        for style in STYLE_NAMES:
            vector_totals[style] = vector_totals.get(style, 0.0) + numeric.get(style, 0.0)

    average_vector = {
        style: round(vector_totals.get(style, 0.0) / vector_count, 4)
        for style in STYLE_NAMES
    } if vector_count else {}
    top_styles = [
        {"style": style, "score": score}
        for style, score in sorted(average_vector.items(), key=lambda x: x[1], reverse=True)[:5]
        if score > 0
    ]

    # 收集有效的风格签名
    signatures: list[dict] = []
    for item in style_signatures:
        if not item or item.get("error"):
            continue
        sig = item.get("parsed") or {}
        if isinstance(item, dict) and "parsed" not in item:
            sig = item
        if sig:
            signatures.append(sig)

    account_style_signature = aggregate_account_style_signature(signatures)

    colors: list = []
    materials: list = []
    moods: list = []
    fit_values: list = []
    price_tiers: list = []
    eras: list = []
    temperatures: list = []
    occasion_totals: dict = {}
    occasion_count = 0

    for sig in signatures:
        colors.extend(sig.get("color_palette", {}).get("dominant_colors") or [])
        temperatures.append(sig.get("color_palette", {}).get("temperature"))
        materials.extend(sig.get("material_profile", {}).get("primary_materials") or [])
        fit_values.append(sig.get("silhouette_profile", {}).get("fit_preference"))
        moods.extend(sig.get("aesthetic_mood", {}).get("mood_keywords") or [])
        price_tiers.append(sig.get("price_positioning", {}).get("tier"))
        eras.append(sig.get("era_influence", {}).get("primary_era"))
        occ = sig.get("occasion_vector") or {}
        if isinstance(occ, dict):
            occasion_count += 1
            for k, v in occ.items():
                if isinstance(v, (int, float)):
                    occasion_totals[k] = occasion_totals.get(k, 0.0) + float(v)

    top_occasions = []
    if occasion_count:
        top_occasions = [
            {"occasion": k, "score": round(v / occasion_count, 4)}
            for k, v in sorted(occasion_totals.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

    return {
        "video_count": max(vector_count, len(signatures)),
        "average_style_vector": average_vector,
        "top_styles": top_styles,
        "account_style_signature": account_style_signature,
        "dominant_colors": _top_counts(colors),
        "temperature": _mode_value(temperatures),
        "primary_materials": _top_counts(materials),
        "fit_preference": _mode_value(fit_values),
        "mood_keywords": _top_counts(moods),
        "top_occasions": top_occasions,
        "price_tier": _mode_value(price_tiers),
        "primary_era": _mode_value(eras),
    }


def _extract_classification_label(classification: dict | None, key: str) -> str | None:
    if not classification:
        return None
    parsed = classification.get("parsed") if "parsed" in classification else classification
    if not isinstance(parsed, dict):
        return None
    block = parsed.get(key) or {}
    label = block.get("label")
    return label if isinstance(label, str) and label else None


def _distribution_for(
    classifications: list[dict],
    key: str,
    remix_label: str,
    unclear_label: str,
) -> dict:
    labels = [
        _extract_classification_label(item, key)
        for item in classifications
        if item and not item.get("error")
    ]
    labels = [l for l in labels if l]
    total = len(labels)
    counts: dict = {}
    for l in labels:
        counts[l] = counts.get(l, 0) + 1
    rows = [
        {"label": l, "count": c, "share": f"{round(c * 100 / total)}%" if total else "0%"}
        for l, c in sorted(counts.items(), key=lambda x: x[1], reverse=True)
    ]
    if not rows:
        final_label = unclear_label
    else:
        top = rows[0]["count"] / total
        second = rows[1]["count"] / total if len(rows) > 1 else 0
        final_label = rows[0]["label"] if top >= 0.5 and second <= 0.4 else remix_label
    return {"final_label": final_label, "total": total, "distribution": rows}


def aggregate_classifications(classifications: list[dict]) -> dict:
    """聚合多视频的分类结果，输出 social_identity 和 occasion 分布。"""
    return {
        "social_identity": _distribution_for(
            classifications,
            "social_identity_classification",
            "Remix 身份型",
            "无明确社会身份型",
        ),
        "occasion": _distribution_for(
            classifications,
            "occasion_classification",
            "Remix Occasion",
            "无明显Occasion",
        ),
    }


def merge_blogger_personal_tags(llm_tags: dict, classification_summary: dict) -> dict:
    """合并 LLM 生成的账号标签和分类聚合结果。"""
    return {
        "basic_demographics": llm_tags.get("basic_demographics") or {},
        "consumption_tier": llm_tags.get("consumption_tier") or "",
        "temperament_psychology": llm_tags.get("temperament_psychology") or "",
        "social_identity": (classification_summary or {}).get("social_identity", {}).get("final_label") or "",
        "occasion": (classification_summary or {}).get("occasion", {}).get("final_label") or "",
        "confidence": llm_tags.get("confidence") or {},
    }


# ── 数据库操作（用于队列服务）──────────────────────────────────────────────────

async def get_blogger_videos(db: AsyncSession, tiktok_blogger_id: uuid.UUID) -> list[dict]:
    """获取博主旗下有视频 URL 和描述的视频列表。
    优先 local_gcs_video_url，兜底 local_video_url。
    """
    from sqlalchemy import or_
    result = await db.execute(
        select(VideoSource).where(
            VideoSource.tiktok_blogger_id == tiktok_blogger_id,
            or_(
                VideoSource.local_gcs_video_url.isnot(None),
                VideoSource.local_video_url.isnot(None),
            ),
        ).order_by(VideoSource.publish_date.desc().nullslast(), VideoSource.created_at.desc())
    )
    videos = result.scalars().all()
    seen: set[str] = set()
    out: list[dict] = []
    for v in videos:
        vid = str(v.id)
        if vid in seen:
            continue
        seen.add(vid)
        description = v.video_desc or v.video_title or ""
        if not description:
            continue
        video_url = v.local_gcs_video_url or v.local_video_url
        out.append({
            "video_id": vid,
            "gcs_url": video_url,
            "description": description,
            "source_url": v.source_url or "",
        })
    return out
