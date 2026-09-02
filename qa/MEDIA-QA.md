# 心动之旅 R4 运行时媒体 QA（2026-08-25）

> R9 当前性说明（2026-09-01）：下述 `25/25` 是历史 R4 快照，不再是当前
> 运行清单的完成口径。本轮严格覆盖复核确认 `23/25`：
> `D1-A3-cast-introductions` 仍处于身份/音频不完整 hold；
> `D1-A3B-cast-first-impressions` 的六人 montage 与严格 identityScope/QA
> evidence 合同不一致。`scripts/validate_event_media_coverage.py` 已在 backend
> 初始化顺序修复后完整复跑；上述三项失败信息是当前证据。

## 终验结论

- Canonical 覆盖：9 个 Day 1 主事件 + 16 个 StoryEvent，严格校验 `25/25`。
- 物理唯一性：25 条 canonical 主合同对应 25 个唯一 R4 master SHA，主合同之间无物理视频复用。
- 历史变体：沈墨备餐、姜米发短信 2 条人物变体仍保留，但不计入 25 条 R4 主合同门禁。
- 运行规格：所有主片均为 15.000 秒 / 360 帧、480×854、24fps、H.264 / yuv420p、AAC 48kHz stereo、faststart，全片解码通过。
- 音频终验：`25/25` 通过，`P0=0`、`P1=0`；综合响度 -23.73 至 -15.72 LUFS，最高 true peak -1.11 dBFS。
- 视觉终验：`25/25` 通过，`P0=0`、`P1=0`；人物身份、无陌生清晰脸、无伪字/伪 UI/水印、动作因果、尾帧与完整解码均通过对应门禁。

## 播放与剧情语义

- 首次进入事件时，视频作为一次性电影段播放：`loop=false`、默认有声，可手动开/关声音或“跳过”。
- 首播期间旁白打字机暂停在第 0 字；视频自然结束后自动关闭电影层，立即从第 1 个字开始逐字旁白。
- 首播层不存在“继续剧情”按钮，剧情不再等待额外确认才推进。
- 首播消费后，同一素材才可作为静音循环的场景背景；该循环只承担动态氛围，不阻塞旁白、选项或主任务推进，用户可主动重新开声。

## 证据

- 音频内容 QA：`media/production/identity-audio-r4/audio-content-qa-r4.json`，SHA-256 `203cf28039bf69589f41abd13ed1b4a3bb0682eb3f92585967ffb988fc178634`。
- 视觉内容 QA：`media/production/identity-audio-r4/visual-content-qa-r4.json`，SHA-256 `863dce2a16c06f3832ce4fe07b4b3713ea83dc014b8be79a1e402882e52e581f`。
- 机器覆盖、规格、唯一性与 QA 绑定校验：`scripts/validate_event_media_coverage.py`。

## 边界

以上结论是当前本地运行时的内部验收，不等于真人身份授权、商业素材清权、公网部署或完整季度制作完成。当前未声称已上传 GitHub、已在 Render 发布或已完成公网端对端 QA。
