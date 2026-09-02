# 人物卡 v3.0 历史研究与生成 QA

## 结论

本文记录首批 8 张人物卡在 `3.0.0-local-research` 阶段的历史 QA，不能代表当前完整角色库。当前版本为 `3.4.0-distinct-character-cores`，包含 32 张卡、完整 16 种 MBTI、每型一男一女；当前同型男女区分门禁见 [`R9-CHARACTER-DISTINCTION-QA.md`](R9-CHARACTER-DISTINCTION-QA.md)。本历史轮没有部署、没有写线上数据库，也没有把 Key 写进代码或产物。

## 证据分层

人物卡按以下优先级解释冲突：

1. 用户提供的《心动之旅：恋综模拟器》游戏系统 DOCX；
2. 当前运行时为海报、立绘和既有剧情做的改编；
3. 已发生剧情、角色独立记忆与七轴关系状态；
4. Myers & Briggs Foundation 的类型偏好与类型动态；
5. 公共领域文学作品中可观察的决策/表达结构；
6. 本项目原创 few-shot。

文学微引文只留在作者研究层，运行时提示明确禁止 DeepSeek 复述、翻译、改写或仿写。

## 原稿对齐审计

- 沈墨、林屿、程野、顾言：姓名与 MBTI 可直接对齐原始 DOCX。
- 江晚：对应原稿“姜晚”INFJ，属于改名适配。
- 姜米：原始 DOCX 没有同名同型人物，标记为 `runtime-original`，不得移植苏念或宋知意的秘密。
- 苏念：原稿为 ENFP，当前运行时为 ESFJ，标记为 `type-adapted`；敏感心理健康背景不得轻佻化或自动披露。
- 陈叙：原稿为 ENTP，当前运行时为 ISTP，标记为 `name-and-type-adapted`；原稿法律纠纷和毒舌人设不自动继承。

## 每张卡新增合同

- `sourceProfile`：原稿对齐状态、可继承事实、改编边界；
- `cognitiveStyle`：输入过滤、决策规则、压力失真、修复动作；
- `knowledge`：知道、不知道、私人事实披露门槛；
- `reactionMatrix`：支持、追问、挑战、越界四类反应；
- `dialoguePolicy`：长度、句式、每轮必须推进的事件单位；
- `memoryPolicy.writeRules/doNotStore`：只保存会影响未来选择的事实，不把猜测变成事实；
- `researchAnchors`：作品、短引文、可迁移模式和禁止复制规则。

## 研究来源

- [Myers & Briggs Foundation: 16 Types](https://www.myersbriggs.org/my-mbti-personality-type/the-16-mbti-personality-types/home.htm)
- [Myers & Briggs Foundation: Type Dynamics](https://www.myersbriggs.org/unique-features-of-myers-briggs/type-dynamics-processes/)
- [The Count of Monte Cristo](https://www.gutenberg.org/ebooks/1184)
- [A Study in Scarlet](https://www.gutenberg.org/ebooks/244)
- [Jane Eyre](https://www.gutenberg.org/ebooks/1260)
- [Little Women](https://www.gutenberg.org/ebooks/514)
- [Anne of Green Gables](https://www.gutenberg.org/ebooks/45)
- [The Three Musketeers](https://www.gutenberg.org/ebooks/1257)
- [The Mysterious Island](https://www.gutenberg.org/ebooks/8993)

## DeepSeek 历史 8 人样片验收

- 同一句玩家输入成功生成 8 个结构化回合；
- 8/8 通过对白长度、态度白名单、意图白名单、七轴范围、记忆结构和事件白名单校验；
- 冷启动实际提交值全部限制在每轴 `-1..1`，即使模型提出更大变化也会被本地引擎收紧；
- 人物动作已优先绑定自己的道具与任务，减少“看窗外、轻轻一笑”等通用动作；
- 样片只做本地风味验证，事件提议没有写入持久数据库。

## 当前边界

这份 8 人样片是 `local-research-candidate` 历史证据，不能外推成当前 32 人都经过 DeepSeek 实模验收。当前 32 卡版本另外通过结构、同型字段差异、人物门禁和运行时绑定测试；后续仍应选跨文化与同型异性角色做三回合连续盲测，检查记忆回收后的差异，而不是只看单轮金句。
