# R8 人味表达 few-shot 研究与落地说明

版本：`3.2.0-humanlike-fewshots`（2026-08-26）

## 结论与阵容边界

- 当前 16 张卡、8 种 MBTI，每种一男一女；每卡 4 条项目原创结构化 few-shot，共 64 条。
- 四个场景槽固定为：真人初见、具体接住支持/示好、分歧或挑战、边界/修复。
- 用户举例提到 ENTP，但当前运行时阵容对应类型是 ESTP。本轮保留 `INTJ / ISFJ / ESTP / INTP / INFJ / ENFP / ESFJ / ISTP`，未静默改型。
- MBTI 只用于“人物先注意什么、怎样作决定、压力下容易歪到哪里”的非诊断镜头；姓名、年龄、职业、欲望、秘密、边界和关系历史始终由人物卡事实层决定。

## 结构化 few-shot 字段

每条示例保留运行时兼容字段 `context / player / attitude / reply`，并增加：

| 字段 | 用途 |
| --- | --- |
| `id` | 唯一、可审计的示例 ID |
| `situation` | 发生了什么，不写隐藏推理 |
| `playerMove` | 玩家本轮可观察输入 |
| `observableCue` | 角色真正看见或听见的事实 |
| `publicInterpretation` | 可修正的公开解释，不作为客观真相 |
| `chosenTactic` | 本轮可观察的交流策略 |
| `stageDirection` | 镜头可见的小动作 |
| `dialogue` | 项目原创台词，与 `reply` 同步 |
| `repairOrExit` | 边界被拒或修复失败时的下一步 |
| `sourceEvidenceIds` | 指向 `research_sources.v3.json` 的证据卡 |
| `copyBoundary` | 固定为 `original-project-expression` |

这些字段不是思维链；DeepSeek 只获得角色可观察事实、已提交 memory、人物策略与原创示例。

## 同型角色的可区分迁移

| 类型 | 男角色 | 女角色 | 明确区分 |
| --- | --- | --- | --- |
| INTJ | 沈墨：投行、长期规划、学会少预判 | 陆遥：智能硬件、系统约束、学会不替人安排 | 同为长程判断，职业抓手、欲望和边界不同 |
| INTP | 顾言：游戏策划、观察与暂定假设 | 温序：城市气候数据、小实验与撤回结论 | 一个从关系定义落回选择，一个从实验落回坦白 |
| ESTP | 程野：品牌创业、用幽默救场后认真表态 | 唐梨：户外现场、风险确认与减速 | 一个处理公开起哄，一个处理实际风险与同意 |
| ISTP | 陈叙：职业待确认、修旧相机、用餐/散步中补沟通 | 乔岚：舞台机械、初见安全检查、餐桌/散步中明确偏好 | 陈叙不再被写成摄影师；两卡都避免四轮只聊设备 |
| INFJ | 江晚：心理咨询、限制解释权 | 贺川：纪录片剪辑、不把自己剪掉 | 一个防止职业读心，一个练习给出自己的选择 |
| ENFP | 姜米：热烈外向但允许安静 | 裴然：体验策展、把普通物件变自愿游戏 | 不把活力写成幼态、操纵或永远开心 |
| ISFJ | 林屿：建筑、低压力具体照料 | 叶澄：古籍修复、先说自己的偏好 | 记住细节不等于无限服务 |
| ESFJ | 苏念：插画、透明分工与拒绝读心 | 黎川：餐饮运营、停止永久主持 | 协调关系不等于强迫和谐 |

## 核验来源与迁移边界

官方类型资料（现代版权、仅研究抽象）：

- [Myers & Briggs Foundation: The 16 MBTI Personality Types](https://www.myersbriggs.org/my-mbti-personality-type/the-16-mbti-personality-types/home.htm)
- [Myers & Briggs Foundation: Type Dynamics Processes](https://www.myersbriggs.org/unique-features-of-myers-briggs/type-dynamics-processes/)

公共领域文学原文（只抽象行为顺序，不复制台词、人物、情节或文风）：

- [The Count of Monte Cristo, eBook #1184](https://www.gutenberg.org/ebooks/1184)
- [A Study in Scarlet, eBook #244](https://www.gutenberg.org/ebooks/244)
- [The Three Musketeers, eBook #1257](https://www.gutenberg.org/ebooks/1257)
- [The Mysterious Island, eBook #1268](https://www.gutenberg.org/ebooks/1268)
- [Twenty Thousand Leagues under the Seas, eBook #164](https://www.gutenberg.org/ebooks/164)
- [The Time Machine, eBook #35](https://www.gutenberg.org/ebooks/35)
- [Around the World in Eighty Days, eBook #103](https://www.gutenberg.org/ebooks/103)
- [Jane Eyre, eBook #1260](https://www.gutenberg.org/ebooks/1260)
- [Middlemarch, eBook #145](https://www.gutenberg.org/ebooks/145)
- [Anne of Green Gables, eBook #45](https://www.gutenberg.org/ebooks/45)
- [Little Women, eBook #514](https://www.gutenberg.org/ebooks/514)
- [The Adventures of Tom Sawyer, eBook #74](https://www.gutenberg.org/ebooks/74)
- [The Wind in the Willows, eBook #289](https://www.gutenberg.org/ebooks/289)
- [Cranford, eBook #394](https://www.gutenberg.org/ebooks/394)
- [A Christmas Carol, eBook #46](https://www.gutenberg.org/ebooks/46)
- [Project Gutenberg License / jurisdiction policy](https://www.gutenberg.org/policy/license)

逐来源 URL、章节 locator、`rightsStatus`、`targetJurisdictionReview`、`transferRule` 与 `prohibitedTransfer` 见 `content/research_sources.v3.json`。Project Gutenberg 只确认美国状态并要求美国以外用户自行核对；本项目不把其文本打包进运行时，目标法域、具体译本和商标仍需分发前复核。

## 可重放构建

- `content/character_fewshot_overrides.v1.json` 是 16 卡 few-shot、来源引用和审计研究包的可重放覆盖层。
- `scripts/build_character_cards_v3.py` 先执行旧的 v3/双阵容构建，再按 `cardId` 替换 `fewShots / sourceRefIds / researchAnchors`，最后写入同一版本的研究包。
- 覆盖层会拒绝重复或不存在的 `cardId`；因此重跑构建脚本不会恢复旧的两条泛化示例，也不会丢掉 feeling 8 卡片段。

## 运行时约束

- 对话必须承接玩家上一句里的具体词，并推进一个新事实、行动、问题、反价、边界或退出。
- 禁止谜语人、职业说明书、MBTI 术语直出、诊断、无事件暧昧空话和几轮后绕回第一话题。
- 角色只能读取自己的已提交 memory；研究来源和文学锚点不进入用户可见台词。
