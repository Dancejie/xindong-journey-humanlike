# 心动之旅：MBTI 恋综模拟器

移动端优先的 EchoDrama 垂直切片，用同一份持久化状态验证三层产品能力：

1. **文字互动剧情**：先介绍七天六夜，再按“选择 MBTI—选择同型男性/女性角色—抵达—自我介绍—破冰—指定私聊—组队—心动短信”推进；每局从 16 张人物卡中确定性选出 8 位嘉宾（4 男 4 女），引擎只接受固定 ID、Intent、Patch 和下一节点。
2. **情感陪伴 Agent**：16 位嘉宾各有 EchoCore v3 人物卡；配置 DeepSeek 后，同一回合生成台词、态度、七轴关系变化、独立记忆与事件建议，服务端负责白名单校验、限幅和原子提交。
3. **AI 互动影游**：只有状态提交成功后才播放对应过场，媒体触发带状态回执。
4. **恋综剧情导演 Agent**：服务端先按阶段、关系、态度、记忆、冷却和隐私条件筛出事件候选；DeepSeek 只能在候选中选择参与者并生成桥段，确定性状态机负责激活、完成或退出主任务。

核心实现：

- `content/character_cards.v3.json`：16 张证据分层、可跨文字游戏/陪伴 Agent/互动影游互通的人物母版；当前覆盖 8 种 MBTI，每型一男一女。
- `content/day1_script_flavors.v1.json`：原始 8 位角色经合同校验和人物风味复核的 DeepSeek 首日台本缓存；新增角色在缓存扩充前使用确定性人物卡台本，不会为开局偷偷触发付费生成。
- `scripts/generate-day1-script-cache.py`：使用受保护的本地 DeepSeek 配置并发生成/复核台本缓存，不把密钥写入内容或前端。
- `content/research_sources.v3.json`：原始 DOCX、MBTI 与公共领域文学行为参考的来源、证据层级和版权用途。
- `research/HUMANLIKE-FEWSHOT-RESEARCH.md` 与 `research/HUMANLIKE-FEELING-RESEARCH.md`：8 种 MBTI、16 位独立角色的检索记录、来源定位、权利边界与原创微场景；文学只迁移可观察的决策顺序，不复制台词、人物或作者文风。
- `docs/EXPRESSION-AND-ROMANCE-CONTRACT.md`：把“活人日常感”和女本位关系节拍固化为 DeepSeek 的人话、恋商、连续性与一票重写合同。
- `backend/game_content.py` 与 `backend/day1_script.py`：确定性剧情节点、DeepSeek 表层台本合同、非 self/目标白名单校验、事件门槛与 StatePatch。
- `content/story_event_catalog.v1.json`：16 个带前置条件、玩家任务、失败出口、回调与媒体提示的恋综事件模板，包含“水上踏板”同意边界与反差成长事件。
- `content/story_event_sources.v1.json`：恋综机制研究证据与设计用途，不复制具体节目剧情。
- `backend/story_director.py`：事件资格过滤、DeepSeek 导演提示、输出校验、主任务提交与解决。
- `backend/app.py`：SSO、PostgreSQL、Agent 网关与业务 API。
- `frontend/src/App.tsx`：节目序章、8 种 MBTI 选择、同型男女双角色选择、当局 8 人 Dock、两阶段打字机、推荐路线加自由输入、地点筛选、同地群聊、手机式心动短信收发、非 self Agent 私聊、过场和联通回执。
- `frontend/public/media/`：保留经 R4/R6 内容与技术 QA 的 Seedance master、四套性别匹配事件轮换、16 位嘉宾动态肖像与稳定帧；运行时会继续核对人物身份、当局名单、性别、事件和音频合同，未满足时只回退到玩家本人动态肖像。
- `media/production/identity-audio-r4/`：R4 生成、候选裁决、主角形象引用、音频/视觉 QA 与运行时集成证据；25 条主片均为 15.000 秒 / 360 帧，AAC 原生音轨保留。
- `scripts/validate_event_media_coverage.py`：保留历史 R4 的 25 条 canonical 合同校验。
- `scripts/validate_r6_runtime_media.py`：独立校验 R6 的 100 个四套事件轮换、16 个动态肖像、108 项 promotion/allowlist 绑定、文件 SHA、编码和音轨；`--decode` 会全片解码全部运行时文件。

## 当前验证边界

- 已实现：16 张详细人物卡、8 种 MBTI 的男女双视角入口、每局 8 人/4 男 4 女确定性阵容、同 MBTI 异性嘉宾同场、自己与局外角色禁止私聊、首日强引导流程、七轴关系、DeepSeek 结构化角色回合、16 个研究型恋综主任务模板、独立记忆、旧存档迁移，以及按玩家本人安全降级的事件媒体路由。
- 事件媒体闭环：服务端先验证并提交 `StoryEvent`，再把白名单 `runtimeAsset` 随回执返回。媒体首播是一次性电影段：不循环、默认有声，播放期间暂停旁白打字机；视频自然结束后自动关闭并从第 1 个字开始逐字旁白，只保留可选“跳过”，不存在“继续剧情”阻塞按钮。
- 后续背景语义：同一素材在正文阶段才转为静音循环的场景背景，仅提供动态氛围、不控制剧情进度；用户可手动重新开声。
- R4 历史门禁：25 条 canonical 主合同对应 25 个唯一 master SHA，另保留 2 条人物变体；当时的技术/内容报告为 `25/25`。R5 复核不沿用“文件存在即覆盖”的结论：D1-A3 因没有可辨自我介绍而下线，D1-A3B 因只有六位已确认人物而不能充当八人混剪。
- R5 已归档且永久禁止提交：它的 188 条逐人语义矩阵预算过大，不再作为生产方案。
- R6 已完成：81 个 480p Seedance 任务、3 个本地双人混剪与 24 个既有母片复用，共 108 个审核源已按哈希写入运行时；100 个事件轮换首播有声、16 位嘉宾均有动态肖像。四套方案保证画面主角与玩家性别一致；运行时还要求片中可辨人物属于本局八人名单，不满足时回退所选主角本人的动态肖像。它不宣称 16 位人物各自拥有完整的 25 事件精确本人脸套装。
- 在线 Agent：只调用服务端配置的 DeepSeek。未配置、超时或输出未通过人物卡合同时，本轮明确失败且不写入任何关系参数或记忆。
- 原始 DOCX 已重新定位并用于证据对齐；角色库现为 8 男 8 女，单局阵容固定 4 男 4 女。这里的“16 人”是 8 种已开放 MBTI × 每型一男一女，不是完整 16 种 MBTI × 两性（32 人）。
- 本地剧情导演样片：`python3 scripts/sample_story_director.py`，输出到 `qa/DEEPSEEK-STORY-DIRECTOR-FLAVOR.md`；读取本机忽略文件 `.env.deepseek.local`，不会写入线上数据库。
- 未声称：完整恋综季度、多端社区/UGC、跨剧永久记忆、商业素材清权或实时生成视频。

## GitHub / Render 公网版本

本仓库是与原版并行维护的“人味增强版”，不会覆盖 [`Dancejie/xindong-journey-echo`](https://github.com/Dancejie/xindong-journey-echo) 或原 Render 服务。它由独立仓库 [`Dancejie/xindong-journey-humanlike`](https://github.com/Dancejie/xindong-journey-humanlike) 的 `main` 部署到 `xindong-journey-humanlike.onrender.com`，保留 MP4、PostgreSQL 角色独立记忆、地点/群聊/短信状态与服务端 Agent 接口，并以匿名访客身份替代 Cowork 内网 SSO。部署方式、两个版本的边界和密钥规则见 `README_RENDER.md`、`INSTANCE_PROVENANCE.md` 与根目录 `render.yaml`。DeepSeek 密钥只配置在新服务的服务端环境变量中，前端、人物卡和 GitHub 均不含密钥。

R5 媒体规则要求运行时人物与审核过的 `identityCast` 精确匹配；缺少某位主角或搭档的事件母片时，只显示该角色的动态立绘，不使用姜米或其他人物的错误镜头。完整语义媒体矩阵与付费生成门禁位于 `media/production/cast-perspective-r5/`。

R6 的计划、人工授权、实际费用台账、技术 QA、视觉 allowlist 与 promotion 记录位于 `media/production/gender-rotation-r6/`。本轮在用户明确授权“R6新增上限¥60”后完成，最终结算 CNY 41.0770200、付费重试 0；canonical 规划 manifest 仍永久保持 `doNotSubmit=true`，避免误重跑。项目预算规则见 `media/production/BUDGET_POLICY.md`：外部生成预计或累计超过 CNY 200 时，必须先展示费用并获得写明最高金额的人工确认；自动付费重试始终关闭。

## Mini Tool 1.4.1 离线包

独立于完整 Cowork 版的离线投影位于 `frontend/minitool-src/`。它不携带 MP4、后端、密钥或网络调用：10 段 Seedance 运行时视频被投影为动画 WebP，8 个角色通过包内确定性角色 Agent 即时回应，并把每个角色的记忆、好感与信任分别写入本机状态，再回流到 DAY 2 剧情。

- 编码动态媒体：`cd frontend && pnpm minitool:motion`
- 构建离线运行时：`cd frontend && pnpm minitool:build`
- 严格校验：`cd frontend && pnpm minitool:validate`
- 校验并打包：`cd frontend && pnpm minitool:package`
- 上传产物：`release/xindong-journey-minitool-1.4.1.zip`

平台边界：Mini Tool 1.4.1 禁止联网，因此这里的“即时 Agent”是包内角色规则与独立记忆，不等同于完整 Cowork 版的在线模型 Agent；本地记忆也不承诺跨设备或永久保存。
