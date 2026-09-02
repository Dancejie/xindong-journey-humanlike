# 心动之旅：MBTI 恋综模拟器

移动端优先的 EchoDrama 垂直切片，用同一份持久化状态验证三层产品能力：

1. **文字互动剧情**：先介绍七天六夜，再按“选择 MBTI—选择同型男性/女性角色—抵达—自我介绍—破冰—指定私聊—组队—心动短信”推进；每局从 32 张人物卡中确定性选出 8 位嘉宾（4 男 4 女），引擎只接受固定 ID、Intent、Patch 和下一节点。
2. **情感陪伴 Agent**：32 位嘉宾各有 EchoCore v3 人物卡；配置 DeepSeek 或 Dots 后，同一回合生成台词、态度、七轴关系变化、独立记忆与事件建议，服务端负责白名单校验、限幅和原子提交。
3. **AI 互动影游**：只有状态提交成功后才播放对应过场，媒体触发带状态回执。
4. **恋综剧情导演 Agent**：服务端先按阶段、关系、态度、记忆、冷却和隐私条件筛出事件候选；当前选择的 LLM 只能在合法候选与输出合同内工作，确定性状态机负责激活、完成或退出主任务。

核心实现：

- `content/character_cards.v3.json`：32 张证据分层、可跨文字游戏/陪伴 Agent/互动影游互通的人物母版；当前覆盖完整 16 种 MBTI，每型一男一女，并用角色级区分门禁防止同型人物只换皮。
- `content/day1_script_flavors.v1.json`：原始 8 位角色经合同校验和人物风味复核的首日台本缓存；新增角色在缓存扩充前使用确定性人物卡台本，不会为开局偷偷触发付费生成。
- `scripts/generate-day1-script-cache.py`：使用受保护的本地 LLM 配置并发生成/复核台本缓存，不把密钥写入内容或前端。
- `content/research_sources.v3.json`：原始 DOCX、MBTI 与公共领域文学行为参考的来源、证据层级和版权用途。
- `research/HUMANLIKE-FEWSHOT-RESEARCH.md` 与 `research/HUMANLIKE-FEELING-RESEARCH.md`：首批 8 种 MBTI、16 位角色的检索记录；新增 16 位角色的来源定位、研究证据和原创 few-shot 直接绑定在人物卡与 R9 构建源中。文学只迁移可观察的决策顺序，不复制台词、人物或作者文风。
- `docs/EXPRESSION-AND-ROMANCE-CONTRACT.md`：把“活人日常感”和女本位关系节拍固化为两种模型共用的人话、恋商、连续性与一票重写合同。
- `backend/game_content.py` 与 `backend/day1_script.py`：确定性剧情节点、LLM 表层台本合同、非 self/目标白名单校验、事件门槛与 StatePatch。
- `content/story_event_catalog.v1.json`：16 个带前置条件、玩家任务、失败出口、回调与媒体提示的恋综事件模板，包含“水上踏板”同意边界与反差成长事件。
- `content/story_event_sources.v1.json`：恋综机制研究证据与设计用途，不复制具体节目剧情。
- `backend/story_director.py`：事件资格过滤、供应商中立的导演提示、输出校验、主任务提交与解决。
- `backend/app.py`：SSO、PostgreSQL、Agent 网关与业务 API。
- `frontend/src/App.tsx`：节目序章、完整 16 种 MBTI 选择、同型男女双角色选择、当局 8 人 Dock、两阶段打字机、推荐路线加自由输入、地点筛选、同地群聊、手机式心动短信收发、非 self Agent 私聊、过场和联通回执。
- `frontend/public/media/`：保留经 R4/R6/R9/R9B 内容与技术 QA 的全部 165 条运行时视频、性别匹配与精确主角事件轮换，以及 32 位嘉宾各自的真人静态与动态肖像；R10 仅把交付副本转为移动端 Lite 编码，不删剧情或音轨。运行时会继续核对人物身份、当局名单、性别、事件和音频合同，未满足时只回退到玩家本人的精确动态或静态肖像。
- `media/production/identity-audio-r4/`：R4 生成、候选裁决、主角形象引用、音频/视觉 QA 与运行时集成证据；25 条主片均为 15.000 秒 / 360 帧，AAC 原生音轨保留。
- `scripts/validate_event_media_coverage.py`：保留历史 R4 的 25 条 canonical 合同校验。
- `scripts/validate_r6_runtime_media.py`：独立校验 R6 的 100 个四套事件轮换与 108 项 promotion/allowlist 源绑定，并允许后续 R10 Lite 交付衍生；`--decode` 会全片解码该轮受管运行时文件。
- `scripts/build_lite_runtime_media.py`：以 360×640、H.264 High@3.1、`yuv420p`、CRF 29、faststart 生成 R10 移动端交付副本，严格保留原有 129 条有声音轨和 36 条静音素材的存在性。

## DeepSeek / Dots 双链路

两种模型共用同一套人物卡、Prompt、结构化输出校验和确定性状态提交。模型密钥只存在于服务端环境；浏览器发送的 `X-LLM-Provider` 只包含 `deepseek` 或 `dots` 这个选择值，不包含 Key。

本地配置：

```bash
cp -n .env.llm.local.example .env.llm.local
# 只编辑被 Git 忽略的 .env.llm.local，填入 DOTS_API_KEY，并按需设置：
# LLM_PROVIDER=dots
./scripts/run-local-preview.sh
```

启动脚本会先兼容加载已有的 `.env.deepseek.local`，再加载 `.env.llm.local`，因此可以保留原 DeepSeek Key、只在新文件补充 Dots。也可以用 `LLM_ENV_FILE=/绝对路径/私密配置.env ./scripts/run-local-preview.sh` 指定覆盖文件；脚本不会输出环境变量值。

- 进程默认供应商：`LLM_PROVIDER=deepseek|dots`。
- 单次受支持请求切换：`X-LLM-Provider: deepseek|dots`，无需重启服务。
- 两套 Key 都配置后，页面顶部会显示“台词模型”选择器；选择只影响后续生成，不重写已经提交的剧情、关系或记忆。
- Dots 默认：`DOTS_API_BASE=https://note3-prev-api.askdiandian.com/v1`、`DOTS_MODEL=dots3-note-prev`、`DOTS_ENABLE_THINKING=false`。基础 URL 已包含 `/v1`，不要再重复拼接。
- DeepSeek 的 `DEEPSEEK_API_BASE`、`DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL` 原链路继续保留。

离线人物对白、剧情导演样片和首日台本缓存也走同一适配层，可用 `--provider` 显式选择；这些命令会真实调用所选 API：

```bash
python3 scripts/sample_character_flavor.py --provider dots
python3 scripts/sample_story_director.py --provider dots
python3 scripts/generate-day1-script-cache.py --provider dots --output /tmp/dots-day1-cache.json
```

建议用两个隔离、初始快照一致的 run 做 A/B；角色回合会写入关系和记忆，不应把两种模型依次提交到同一个 run 后再比较。完整配置、比较记录模板和证据边界见 [`docs/DOTS-PROVIDER-COMPARISON.md`](docs/DOTS-PROVIDER-COMPARISON.md)。

## 当前验证边界

- 已实现：32 张详细人物卡、完整 16 种 MBTI 的男女双视角入口、每局 8 人/4 男 4 女确定性阵容、同 MBTI 异性嘉宾同场、自己与局外角色禁止私聊、首日强引导流程、七轴关系、LLM 结构化角色回合、16 个研究型恋综主任务模板、独立记忆、旧存档迁移，以及按玩家本人安全降级的事件媒体路由。
- 事件媒体闭环：服务端先验证并提交 `StoryEvent`，再把白名单 `runtimeAsset` 随回执返回。媒体首播是一次性电影段：不循环、默认有声，播放期间暂停旁白打字机；视频自然结束后自动关闭并从第 1 个字开始逐字旁白，只保留可选“跳过”，不存在“继续剧情”阻塞按钮。
- 后续背景语义：同一素材在正文阶段才转为静音循环的场景背景，仅提供动态氛围、不控制剧情进度；用户可手动重新开声。
- R4 历史门禁：25 条 canonical 主合同对应 25 个唯一 master SHA，另保留 2 条人物变体；当时的技术/内容报告为 `25/25`。R5 复核不沿用“文件存在即覆盖”的结论：D1-A3 因没有可辨自我介绍而下线，D1-A3B 因只有六位已确认人物而不能充当八人混剪。
- R5 已归档且永久禁止提交：它的 188 条逐人语义矩阵预算过大，不再作为生产方案。
- R6 已完成：81 个 480p Seedance 任务、3 个本地双人混剪与 24 个既有母片复用，共 108 个审核源已按哈希写入运行时；100 个事件轮换首播有声、16 位嘉宾均有动态肖像。四套方案保证画面主角与玩家性别一致；运行时还要求片中可辨人物属于本局八人名单，不满足时回退所选主角本人的动态肖像。它不宣称 16 位人物各自拥有完整的 25 事件精确本人脸套装。
- R10 Lite 已完成：165/165 条运行时视频均保留，129 条有声音轨与 36 条静音素材的存在性不变；视频部分从 266,177,881 B 降为 52,434,743 B（减少 80.30%），完整前端包从 258.83 MiB 降为 54.99 MiB。首页先绘制 poster 再挂载视频，离场层不预载；`/media/` 支持 Range 206 和 7 天缓存。完整解码、SHA 与清单校验见 `qa/LITE-RUNTIME-MEDIA-R10.md`。
- 在线 Agent：只调用本轮显式选择或服务端默认的 DeepSeek/Dots。未配置、超时或输出未通过人物卡合同时，本轮明确失败且不写入任何关系参数或记忆；不会静默改用另一供应商污染 A/B 结果。
- 原始 DOCX 已重新定位并用于证据对齐；角色库现为 16 男 16 女，覆盖完整 16 种 MBTI，每型一男一女。单局仍确定性抽取 8 人并保持 4 男 4 女，不会把 32 人同时塞进一季小屋。
- 本地剧情导演样片：`python3 scripts/sample_story_director.py --provider deepseek|dots`；默认分别输出到 `qa/DEEPSEEK-STORY-DIRECTOR-FLAVOR.md` 或 `qa/DOTS-STORY-DIRECTOR-FLAVOR.md`，使用本机忽略的 LLM 配置，不会写入线上数据库。
- 未声称：完整恋综季度、多端社区/UGC、跨剧永久记忆、商业素材清权或实时生成视频。

## GitHub / Render 公网版本

本仓库是与原版并行维护的“人味增强版”，不会覆盖 [`Dancejie/xindong-journey-echo`](https://github.com/Dancejie/xindong-journey-echo) 或原 Render 服务。它由独立仓库 [`Dancejie/xindong-journey-humanlike`](https://github.com/Dancejie/xindong-journey-humanlike) 的 `main` 部署到 `xindong-journey-humanlike.onrender.com`，保留 MP4、PostgreSQL 角色独立记忆、地点/群聊/短信状态与服务端 Agent 接口，并以匿名访客身份替代 Cowork 内网 SSO。部署方式、两个版本的边界和密钥规则见 `README_RENDER.md`、`INSTANCE_PROVENANCE.md` 与根目录 `render.yaml`。DeepSeek/Dots 密钥只配置在新服务的服务端环境变量中，前端、人物卡和 GitHub 均不含密钥。

R5 媒体规则要求运行时人物与审核过的 `identityCast` 精确匹配；缺少某位主角或搭档的事件母片时，只显示该角色的动态立绘，不使用姜米或其他人物的错误镜头。完整语义媒体矩阵与付费生成门禁位于 `media/production/cast-perspective-r5/`。

R6 的计划、人工授权、实际费用台账、技术 QA、视觉 allowlist 与 promotion 记录位于 `media/production/gender-rotation-r6/`。本轮在用户明确授权“R6新增上限¥60”后完成，最终结算 CNY 41.0770200、付费重试 0；canonical 规划 manifest 仍永久保持 `doNotSubmit=true`，避免误重跑。项目预算规则见 `media/production/BUDGET_POLICY.md`：外部生成预计或累计超过 CNY 200 时，必须先展示费用并获得写明最高金额的人工确认；自动付费重试始终关闭。

R9 完成完整 16 MBTI × 两性扩展。16 位新增角色都有 480×854 真人写实身份锚点；本轮在用户明确授权硬上限 CNY 500 后生成 22 个 Seedance 480p 候选，实际结算 CNY 11.0599776，付费自动重试 0。人工视觉与身份连续性复核后，14 个动态肖像和 4 个精确主角事件视频进入运行时；另 4 个含伪文字的候选保持 hold，其中 `qince`、`shaozheng` 使用本人静态锚点，不错配他人。完整候选与供应商证据保留在本地 `media/production/full-mbti-r9/`，为避免扩大 Lite 部署体积与暴露供应商内部信息，不随公开仓库发布。

R9B 是独立、一次性的 ENTJ 动态肖像修复轮次。在用户明确确认“R9B新增上限¥5”后，仅提交 `shaozheng` 与 `qince` 两条 4 秒、480p、静音 Seedance 任务，2/2 一次成功，实际新增结算 CNY 0.7917456，付费重试 0。原始回传因 faststart、无声口型和道具残留未直接上线；经记录化的本地裁切、安全循环与封装后，两条衍生 master 通过完整解码、移动端裁切和人工身份复核，并以新 `001b` source ID add-only 接入。当前人物目录为 32/32 静态肖像与 32/32 动态肖像；这只证明本地运行时接入，不代表新一轮公网部署或商业素材清权。

R10 Lite 不调用付费生成服务，只优化审核后运行时副本与浏览器加载。165 条视频全部转为 360×640 H.264 faststart，原有音轨存在性保持不变；前端包缩减至 54.99 MiB。它不改变 R4/R6/R9/R9B 的视觉审核、身份绑定与版权证明边界。

## Mini Tool 1.4.1 离线包

独立于完整 Cowork 版的离线投影位于 `frontend/minitool-src/`。它不携带 MP4、后端、密钥或网络调用：10 段 Seedance 运行时视频被投影为动画 WebP，8 个角色通过包内确定性角色 Agent 即时回应，并把每个角色的记忆、好感与信任分别写入本机状态，再回流到 DAY 2 剧情。

- 编码动态媒体：`cd frontend && pnpm minitool:motion`
- 构建离线运行时：`cd frontend && pnpm minitool:build`
- 严格校验：`cd frontend && pnpm minitool:validate`
- 校验并打包：`cd frontend && pnpm minitool:package`
- 上传产物：`release/xindong-journey-minitool-1.4.1.zip`

平台边界：Mini Tool 1.4.1 禁止联网，因此这里的“即时 Agent”是包内角色规则与独立记忆，不等同于完整 Cowork 版的在线模型 Agent；本地记忆也不承诺跨设备或永久保存。
