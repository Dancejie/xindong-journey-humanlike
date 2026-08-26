# INFJ / ENFP / ISFJ / ESFJ 人物卡「人味」研究片段

## 交付边界

- 范围：`jiangwan`、`hechuan`、`jiangmi`、`peiran`、`linyu`、`yecheng`、`sunnian`、`lichuan`，共 8 张卡。
- 数据入口：`research/humanlike-feeling-fragment.json`。这是供并发任务合并的片段，不直接覆盖 `content/character_cards.v3.json` 或 `content/research_sources.v3.json`。
- 每张卡含 4 条原创结构化 few-shot，依次覆盖初见、支持、挑战、边界或修复。
- 文学只提供可观察的行为序列，不提供可复用台词、人物身份、情节模板或作者文风。运行时只能检索 `dialogue` 等项目原创字段，不能把来源原文放入模型上下文。

## 类型证据与迁移规则

| 类型 | 官方证据 | 可迁移行为 | 禁止简化 |
|---|---|---|---|
| INFJ | [The 16 MBTI Personality Types](https://www.myersbriggs.org/my-mbti-personality-type/the-16-mbti-personality-types/home.htm)；[Type Dynamics: Ni / Fe](https://www.myersbriggs.org/unique-features-of-myers-briggs/type-dynamics-processes/) | 从细节形成假设，但先核验；用清楚的个人选择代替温柔绕行；判断错误后显式作废并重建对话 | 读心、谜语人、冷淡等同深刻 |
| ENFP | [The 16 MBTI Personality Types](https://www.myersbriggs.org/my-mbti-personality-type/the-16-mbti-personality-types/home.htm)；[Type Dynamics: Ne / Fi](https://www.myersbriggs.org/unique-features-of-myers-briggs/type-dynamics-processes/) | 提供多种可能、制造参与感；热闹后回到真实偏好；承诺被打断时做可验证修复 | 永远亢奋、把尴尬当笑料、靠新鲜感跳过责任 |
| ISFJ | [The 16 MBTI Personality Types](https://www.myersbriggs.org/my-mbti-personality-type/the-16-mbti-personality-types/home.htm)；[Type Dynamics: Si / Fe](https://www.myersbriggs.org/unique-features-of-myers-briggs/type-dynamics-processes/) | 记住具体偏好并落实；先询问再帮助；把隐性劳动改成可协商分工 | 没有自己需要的照顾工具人、沉默等于同意 |
| ESFJ | [The 16 MBTI Personality Types](https://www.myersbriggs.org/my-mbti-personality-type/the-16-mbti-personality-types/home.htm)；[Type Dynamics: Fe / Si](https://www.myersbriggs.org/unique-features-of-myers-briggs/type-dynamics-processes/) | 主动组织关系并公开规则；用具体分工维护群体；犯错后补偿并持续跟进 | 控场等于恋商、热情等于无边界服务 |

以上官方页面用于类型偏好与功能动态研究，权利状态为 `research-only`；不复制定义、示例或页面表述到运行时台词。

## 同类型角色的区分

| 类型 | 角色 A | 角色 B | 核心差异 |
|---|---|---|---|
| INFJ | 江晚：心理咨询师；想少猜、多表达；拒绝职业读心与未授权公开 | 贺川：纪录片剪辑；想停止把自己剪掉；拒绝把别人剪成漂亮结论 | 她限制解释权，他修正叙事权；两人都安静，但主动选择的落点不同 |
| ENFP | 姜米：靠好奇与声音日记连接；需要安静状态也被看见；失约必须按时修复 | 裴然：儿童博物馆体验策展；擅长把物件变成共同游戏；拒绝拿他人尴尬换效果 | 她从情绪与故事进入关系，他从体验设计进入关系；她怕表演常态化，他怕魅力遮住亲密 |
| ISFJ | 林屿：建筑工程师；可靠并重视完成；需要直接提出自己的劳动与饮食偏好 | 叶澄：古籍修复师；重视顺序、授权和物件边界；拒绝体贴成为默认职责 | 他强调共同分工与兑现，她强调先问、慢做和专业顺序 |
| ESFJ | 苏念：插画师；喜欢让陌生人变熟；要求群体劳动轮值 | 黎川：酒店餐饮运营；习惯看服务缺口；想被当作约会对象而非经理 | 她用规则保护创作与休息，他从服务系统退回个人欲望与安全责任 |

## 公共领域文学来源

| 来源 | URL / 定位 | 权利状态 | 用于人物 | 允许迁移 | 明确禁止 |
|---|---|---|---|---|---|
| George Eliot, *Middlemarch* | [Project Gutenberg #145](https://www.gutenberg.org/ebooks/145)，Book VIII, Chapter LXXXI | PG 标注美国公版；作者 1880 年去世，底层文本也已超过中国大陆著作权期限；再分发 PG 文件仍须遵守其商标/许可 | 江晚、贺川 | 受伤后仍用事实行动；新事实出现时改判并修复 | 原句、婚姻误会、人物身份、Eliot 叙述腔 |
| Mark Twain, *The Adventures of Tom Sawyer* | [Project Gutenberg #74](https://www.gutenberg.org/ebooks/74)，Chapter II | PG 标注美国公版；作者 1910 年去世，底层文本也已超过中国大陆著作权期限；再分发 PG 文件仍须遵守其商标/许可 | 裴然 | 把普通物件重新定义为自愿参与的共同体验 | 欺骗、制造稀缺、诱导代劳、儿童口吻、原句 |
| Elizabeth Gaskell, *Cranford* | [Project Gutenberg #394](https://www.gutenberg.org/ebooks/394)，Chapters XIII–XIV | PG 标注美国公版；作者 1865 年去世，底层文本也已超过中国大陆著作权期限；再分发 PG 文件仍须遵守其商标/许可 | 叶澄、苏念、黎川 | 具体分工、照顾体面、按接受方式提供帮助 | 阶级语境、银行情节、人物身份、原句、Gaskell 叙述腔 |
| Kenneth Grahame, *The Wind in the Willows* | [Project Gutenberg #289](https://www.gutenberg.org/ebooks/289)，Chapter V, “Dulce Domum” | PG 标注美国公版；作者 1932 年去世，底层文本也已超过中国大陆著作权期限；再分发 PG 文件仍须遵守其商标/许可 | 林屿 | 发现微小变化、恢复熟悉条件、无催促帮助 | 动物身份、河岸场景、原句、Grahame 文风 |
| Charles Dickens, *A Christmas Carol* | [Project Gutenberg #46](https://www.gutenberg.org/ebooks/46)，Stave Five | PG 标注美国公版；作者 1870 年去世，底层文本也已超过中国大陆著作权期限；再分发 PG 文件仍须遵守其商标/许可 | 黎川 | 用补偿、复核和长期一致性验证修复 | 鬼魂结构、圣诞场景、人物身份、原句、Dickens 文风 |

复用现有来源：[*Jane Eyre*](https://www.gutenberg.org/ebooks/1260)（自主与平等边界，江晚/贺川）；[*Anne of Green Gables*](https://www.gutenberg.org/ebooks/45)（具体、鲜活、先征求同意的初见与主动修复，姜米/裴然）；[*Little Women*](https://www.gutenberg.org/ebooks/514)（共同劳动、承担过失并以行动修复，姜米/叶澄）。三者同样只迁移可观察行为，不复制台词、角色、情节或文风。

## 合并与检索建议

1. 按 `cardId` 合并；`sourceRefIdsAppend` 和 `researchAnchorsAppend` 去重追加。
2. 片段中的 4 条 `fewShots` 建议替换旧的两条泛化 few-shot，而不是与低质量示例混用。
3. 每次 DeepSeek 生成只检索与当前阶段最接近的 2–3 条示例；优先匹配 `situation`、`playerMove`、`observableCue` 和 `repairOrExit`，不要把八张卡全部塞入上下文。
4. 要求模型先给可观察动作，再给一句自然口语；禁止人格标签代替行为，禁止谜语式隐喻，禁止复述文学来源。
5. 输出后检查：是否有事实抓手、明确选择、对方可拒绝的空间、错误后的具体修复；任一缺失就重写。

## 验收口径

- 8 个目标 `cardId` 均存在，每卡 4 条场景覆盖齐全。
- 每条示例同时保留旧运行时字段 `context/player/attitude/reply` 和新研究字段，便于渐进合并。
- 所有 `sourceEvidenceIds` 可解析到片段中的证据条目；所有新增 `sourceRefIdsAppend` 可解析到 `newSources`。
- 运行时表达全部为本项目原创，不包含来源长引或角色模仿。
