# R9 完整 MBTI 本地交付 QA

日期：2026-09-02
状态：`experience-verified-local`，未部署，未宣称商业素材清权

## 人物与区分度

- 32 张人物卡，完整 16 种 MBTI，每型一男一女。
- 16/16 组同型角色通过五字段差异门禁：第一注意对象、修复动作、互动策略、记忆偏好、四类反应话术。
- 32/32 张卡包含独立 `distinctiveVoiceGate`；人物不能借用别人的职业物件、口头禅、亲密策略或冲突修复。
- 六位欧洲大陆生活背景角色为项目原创成年人；背景用于制造真实生活约束，不把国籍直接等同性格。

## 媒体、预算与回退

- R9 Seedance：22 个 480p 候选、112 秒；实际结算 CNY 11.0599776 / 用户授权硬上限 CNY 500。
- 自动付费重试 0，promotion 阶段付费调用 0。
- 技术 QA：22/22 通过；身份连续性：22/22 通过。
- 人工裁决：18 个进入运行时，包括 14 个动态肖像与 4 个精确主角事件片。
- 4 个带前景伪文字的候选保持 hold；`qince`、`shaozheng` 使用本人 480×854 静态图，事件使用精确人物既有或静态回退，不借他人镜头。
- 当前注册表：32 静态肖像、30 动态肖像、133 条事件路由，共 195 项；零人物无媒体。

## 自动验证

- Backend + registry + provider：117/117 通过。
- 角色近似换皮专项：2/2 通过。
- R9 media QA/promotion：25/25 通过。
- Portrait binding：3/3 通过。
- Frontend TypeScript：通过。
- Frontend production build：通过；249 文件、269,941,596 bytes、163 视频、32 肖像。
- Bundle 检查：Key、私密本地绝对路径、source map、candidate/reference-only 标记均为 0。
- 本地运行健康：`contentVersion=4.0.0-full-mbti-r9`、`characterCardContentVersion=3.4.0-distinct-character-cores`。
- 新动态媒体 Range 请求返回 HTTP 206。

## 体验验证

- 16 种 MBTI 均显示男女双角色与各自真人头像。
- 角色选择页能看见同型角色不同职业、判断顺序与关系边界。
- 已抽查 `qince` 静态 hold 回退与 `jiheng` 动态肖像；均绑定本人身份。
- 动态肖像播放结束后自动进入逐字旁白；旁白完成后才出现三项选择与自由输入。
- 主角本人不可私聊；浏览器控制台无 warning/error。

## 清理与证据边界

- 删除前逐个校验 18 个运行时 MP4 与 16 个 R9 静态身份图 SHA-256。
- 已删除候选波次、contact sheet、抽帧与 ASR 临时目录，共回收 42.95 MiB。
- 保留身份锚点、运行时 master、prompts、结算账本、manifest、allowlist、promotion 记录与紧凑 QA。
- 运行时接入不等于公网部署，也不等于公开或商业使用权已清理。

## R9B 后续修复跳转

本文件保留 R9 结项时的历史快照：18 条进入运行时、4 条 hold，`qince` 与
`shaozheng` 当时使用静态回退；这些数字不因后续修复而回写。

R9B 在独立预算、提交、原片裁决与本地衍生证据链下补齐了两条 ENTJ 动态肖像。
当前工作区已核实两条 approved 衍生文件与 runtime manifest 哈希一致并完成本地
运行时接入；没有据此宣称任何公网部署。完整结算、faststart / 口型 / 道具问题、
安全循环处理与最终 QA 见
[`R9B-ENTJ-DYNAMIC-PORTRAIT-QA.md`](R9B-ENTJ-DYNAMIC-PORTRAIT-QA.md)。
