# R8 人物—媒体身份绑定审计

审计对象：`xindong-journey-humanlike` 线上基线 `6fdae82`（2026-08-27）
范围：16 张人物卡、16 条动态肖像、25 个剧情媒体基类、100 条 R6 轮换事件视频，以及 Day 1 / Story Director 的运行时媒体解析。

## 结论

用户看到“选择黎川，序章却出现程野”不是视频文件贴错标签，而是运行时复用规则把“同性别”误当成“同一人物”。

- `D1-A1-island-hotel-establish--rotation-M-A-chengye.mp4` 的文件、hash、`identityCast=["chengye"]` 和抽帧人物均为程野；资产自身登记正确。
- 线上基线的 `media_rotation_for()` 对黎川 + `D1-A1-island-hotel-establish` 稳定选择 `M-A-chengye`。
- `resolve_identity_safe_media()` 旧门禁只要求轮换锚点与主角同性、且该锚点在当局 8 人阵容中，没有要求 `rotation_anchor == perspective_character_id`，因此把程野的已审片作为黎川的主角演出返回。
- Story Director 复用同一个 resolver，所以问题不只在序章，也覆盖后续事件。

## 影响面

R6 有 25 个剧情媒体基类，每个基类各有姜米、陆遥、程野、贺川四个轮换锚点，共 100 条已批准运行视频。

按线上基线的稳定路由静态计算：

| 审计矩阵 | 请求锚点不是所选主角 | 比例 |
| --- | ---: | ---: |
| 16 人 × 25 个剧情媒体 | 347 / 400 | 86.75% |
| 16 人 × Day 1 九个节点 | 126 / 144 | 87.50% |

- 12 个非锚点人物（包括黎川）均为 `25/25` 指向别人的轮换锚点。
- 四个锚点人物也会因逐事件交替而错指另一位同性锚点：程野 `11/25`、姜米 `14/25`、陆遥 `10/25`、贺川 `12/25`。
- 实际一局是否播放错片还受“被选锚点是否恰好进入本局 8 人阵容”影响；锚点不在阵容时旧代码会退回主角肖像。因此上表是有问题的路由请求面，不代表每次开局都一定可见错片。

## 资产层验证

- 16 / 16 静态肖像路径存在，文件名与人物 `id` 一致，hash 均唯一。
- 16 / 16 动态肖像路径存在，manifest hash 与运行文件一致，hash 均唯一；静态肖像与视频中帧逐对视觉核对，未发现交叉身份。
- 100 / 100 轮换事件视频存在；manifest hash 全部匹配，0 个重复 hash，`rotationSlot`、`leadCharacterId` 与 `identityCast` 彼此一致。
- 黎川、程野肖像以及程野 / 贺川序章轮换片均抽取首帧和中帧人工检查；用户截图中的人物与程野序章轮换片一致，而与黎川动态肖像明显不同。
- 既有 R6 视觉 allowlist 记录 108 个批准资产、0 个 identity hard failure；本轮没有重新逐帧复审 100 条事件视频，也没有发起新的付费生成。

## Manifest / 命名缺口

- 八条 legacy 动态肖像（沈墨、林屿、程野、顾言、江晚、姜米、苏念、陈叙）只有 `id/kind/path/sha256/duration`，缺少 `status`、`identityCast`、`identityScope` 和来源字段；运行时目前靠人物卡内的精确路径兜底。
- 现有 116 条人物/轮换资产都没有统一的 `characterName`、`mbti`、`sequence`、`action`、`scene`、`canonicalFilename`、`displayName` 字段，不利于代码和人工审核快速定位。
- 建议保留现有 runtime path，新增 canonical registry，避免复制或重命名大视频。机器名示例：`lichuan-esfj-001-first-arrival-hotel-entrance.mp4`；审核显示名：`黎川-ESFJ-001-初次登场-酒店玄关`。

## 修复验收合同

1. 事件片只有在 `identityCast` 精确包含所选主角，且符合本事件的参与者合同时才可播放。
2. “同性别”只可用于生产计划/覆盖统计，不能作为人物身份替代。
3. 没有精确事件片时，必须退回该主角自己的 `CHAR-{id}-portrait` 或静态肖像，声音关闭；不能借用另一位嘉宾的视频。
4. 四位 R6 锚点固定使用自己的 event set，不再按事件交替到另一位同性锚点。
5. 回归测试必须覆盖 16 人 × 25 个媒体基类，并断言任何返回的单主角媒体都满足 `identityCast == [perspectiveCharacterId]`；另外覆盖参与者、group-current-eight 和 Story Director 路径。

## 工作树修复验证

- `python3 -m unittest backend.test_game_content`：74 / 74 通过。
- 以 16 人全部纳入 `current_cast_ids` 的最大风险条件复跑 16 人 × 25 个媒体基类：400 / 400 返回媒体都包含所选主角，0 个身份失败。
- 其中四位精确锚点使用 100 条本人 approved rotation；其余 12 人的 300 条事件请求均安全降级到本人的 `CHAR-{id}-portrait`，没有借用同性交叉人物。
- 临时首/中帧与 contact sheet 已在结论记录后删除，回收约 700 KiB；未保留可再生逐帧 QA 图。

## 证据位置

- 根因：`backend/game_content.py` 的 `media_rotation_for()` 与 `resolve_identity_safe_media()`。
- Story Director 调用：`backend/story_director.py` 的 `_event_media()`。
- 资产事实源：`media/runtime-media-manifest.json`。
- R6 既有视觉记录：`media/production/gender-rotation-r6/visual-qa-allowlist.r6.json` 与 `visual-qa-report-r6.md`。
