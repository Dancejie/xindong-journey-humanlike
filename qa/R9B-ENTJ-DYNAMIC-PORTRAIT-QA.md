# R9B ENTJ 动态肖像修复 QA

日期：2026-09-02
状态：`approved-runtime-local`、`runtime-integrated`；未部署，未宣称公开或商业素材清权

## 范围、提交与结算

- 修复对象：邵峥（`shaozheng`）与 Elena Moreau（`qince`）两条 ENTJ 动态肖像。
- 用户一次性授权：`R9B新增上限¥5`。
- 两个 Seedance 任务在同一并发波次各提交一次，2/2 成功；自动付费重试与实际重试均为 0。
- 实际结算：¥0.7917456，其中每条 ¥0.3958728。
- R9B 是独立修复批次，不改写 R9 的 22 条生成、18 条批准 / 4 条 hold 与 ¥11.0599776 历史结论。

结算证据：
[`budget-ledger.r9b.json`](../media/production/full-mbti-r9/repair-entj-r9b/budget-ledger.r9b.json)。

## Provider 原片裁决

两条 provider 原片均完成下载并通过哈希、H.264、`yuv420p`、竖屏、时长、
静音与完整解码检查，但不能直接进入运行时：

- 两条原片都缺少 faststart，顶层 MP4 atom 中 `moov` 位于 `mdat` 之后。
- 两条原片都包含连续、可见的无声说话口型；单做 faststart 不会修复这一视觉问题。
- Elena 原片还从身份锚点继承了文件夹；初步裁切仍留下棕色封面与白色页边。
- 因此 provider 原片保持 source evidence / hold，未通过改名或封装直接晋级。

原片技术裁决：
[`technical-qa.r9b.json`](../media/production/full-mbti-r9/repair-entj-r9b/technical-qa.r9b.json)。

## 无付费本地安全衍生

未发起新生成或付费重试。两条运行时候选均由已结算原片在本地确定性处理：

| 角色 | 本地处理 | Approved SHA-256 |
| --- | --- | --- |
| 邵峥 / `shaozheng` | 取 `0.3:1.9` 安全段，正放后倒放形成闭环，尾部稳定 0.85 秒；移除音轨并以 H.264、`yuv420p`、faststart 输出 | `5b8140d2998a60fddefc19c5fe81719b40adadd5a7fbb1d0038e8475a08e3e7f` |
| Elena Moreau / `qince` | 取 `2.7:3.8` 安全段，`crop=380:676:0:0` 后缩放至 480×854，正放后倒放形成闭环，尾部稳定 0.85 秒；移除音轨并以 H.264、`yuv420p`、faststart 输出 | `9fac252381abdfd2149df7258becda7d9d08bd2c28880766b92cbc62113dab4b` |

Elena 的 approved 衍生是克制微笑动态肖像，不再声称完成原 DirectorCard
中的开放掌动作。

处理配方与 source/output 哈希：
[`postprocess.r9b.json`](../media/production/full-mbti-r9/repair-entj-r9b/postprocess.r9b.json)。

## 技术与视觉 QA

- 技术：2/2 完整解码、单 H.264 视频流、`yuv420p`、零音轨、faststart 通过。
- 邵峥：496×864、4.000000 秒；身份、自然倾听与开放掌动作稳定。
- Elena：480×854、4.041667 秒；身份稳定，文件夹与页边已完全移除。
- 两条均逐帧检查完整时间轴：无说话口型、纸张/文件夹、伪字、Logo、UI、水印或第二张清晰人脸。
- 正放转倒放没有可见跳切或明显反物理感；手部可见处结构自然，尾部冻结稳定。
- `object-fit: cover` 在 390×844、390×720、390×620 三档均保持人物身份与主体安全。

技术证据：
[`technical-qa.normalized.r9b.json`](../media/production/full-mbti-r9/repair-entj-r9b/technical-qa.normalized.r9b.json)。
视觉证据：
[`visual-audio-qa-report-r9b.md`](../media/production/full-mbti-r9/repair-entj-r9b/visual-audio-qa-report-r9b.md) 与
[`visual-audio-qa-allowlist.r9b.json`](../media/production/full-mbti-r9/repair-entj-r9b/visual-audio-qa-allowlist.r9b.json)。

## 当前运行时核验

本文件编写时已重新核对当前工作区：

| Runtime ID | 本地目标 | 当前状态 |
| --- | --- | --- |
| `CHAR-shaozheng-portrait` | `frontend/public/media/video/CHAR-shaozheng-portrait.mp4` | 文件存在；SHA-256 与 approved 衍生及 runtime manifest 一致；`approved-runtime` / `runtime-integrated` |
| `CHAR-qince-portrait` | `frontend/public/media/video/CHAR-qince-portrait.mp4` | 文件存在；SHA-256 与 approved 衍生及 runtime manifest 一致；`approved-runtime` / `runtime-integrated` |

- `media/runtime-media-manifest.json` 当前登记 32 条动态肖像，两条 ENTJ 修复均为本地衍生来源。
- `media/character-asset-registry.v1.json` 已为 `shaozheng` 与 `qince` 绑定各自动态肖像路径。
- 以上只证明当前本地工作区运行时接入，不证明 Render、Cowork 或其他公网环境已部署。
- Approved 范围仅限当前私有 Demo；本地衍生必须保留 provider 原片、处理配方、输入输出哈希与 QA 证据链，不能冒充 provider 原始成片。

## 自动化与浏览器回放

- Runtime manifest：165 项，其中动态肖像 32；两条 R9B 记录的本人绑定、静音状态、路径与 SHA-256 通过 `jq` 门禁。
- Character asset registry：197 项（32 静态、32 动态、133 事件路由），32 人均为 `runtime-identity-covered`；专项测试 7/7 通过。
- Backend：`python -m unittest discover -s backend -p 'test_*.py'`，130/130 通过。
- Frontend：TypeScript `--noEmit` 通过；仓库现有 Vite 5.4.21 二进制 production build 通过，产物 251 文件、271,407,290 bytes。
- 本地 API：`/health` 正常；`/api/bootstrap` 返回 32 人、32 `ready`、0 `planned`；两条 MP4 的 HTTP Range 请求均为 206。
- 实际页面：ENTJ 选择页的邵峥与 Elena Moreau 各自加载本人 `CHAR-*-portrait.mp4`，均为 `readyState=4`、正在播放、静音循环；390×844、390×720、390×620 三档 `object-fit: cover` 无横向溢出，控制台无 warning/error。
- Bundle 扫描：未发现 API Key、provider task ID、用户绝对路径、`.work-candidates` 或 Fumin 内部标记。

`pnpm build` 在本机受到 pnpm 的 ignored-builds 策略阻止安装阶段执行 `esbuild` 脚本；这不是源码编译失败。为避免修改用户的全局 pnpm 策略，本轮用仓库现有、已安装的 `./node_modules/.bin/vite build` 完成等价生产构建。

## 清理

在运行时文件与 manifest SHA-256 再次一致、账本与 QA 报告均已保留后，定点删除：

- `repair-entj-r9b/.work-candidates/`：3,968 KiB；
- `/tmp/xindong-r9b-qa.5GFzV4/`：10,392 KiB。

合计回收 14,360 KiB（约 14.02 MiB）。保留运行时 master、静态身份锚、prompts、预算/结算、postprocess 配方、技术/视觉报告、promotion 记录和媒体清单。仓库当前没有 `cleanup:dry-run` / `cleanup:apply` package script，因此没有伪造执行结果，也没有用广域删除替代。
