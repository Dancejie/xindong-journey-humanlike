# 心动之旅：GitHub + Render 公网部署

这个仓库包含完整 React/FastAPI 版本、32 张人物卡（完整 16 种 MBTI，每型一男一女）、单局 8 人/4 男 4 女阵容、32 位真人静态身份图、32 位动态肖像、性别匹配与精确主角剧情事件视频、事件驱动剧情状态机，以及可切换 DeepSeek/Dots 的服务端角色 Agent。

本文件只描述独立的“人味增强版”部署。原版 `Dancejie/xindong-journey-echo` 与 `xindong-journey-echo.onrender.com` 保持不变；两个服务共用账号现有的免费 PostgreSQL 实例，但人味增强版固定使用独立 schema `xindong_journey_humanlike`，不会读写原版表。可审计边界见 `INSTANCE_PROVENANCE.md`。

## 架构

- 前端：`frontend/dist/`，由 FastAPI 同源托管，运行时视频位于 `frontend/dist/media/video/`；R10 Lite 包为 54.99 MiB，并保留全部 165 条视频。Render 构建会显式检查该目录已经随发布提交存在。
- 剧情与记忆：PostgreSQL 保存每位访客的剧情快照、角色独立记忆、七轴关系、专属事件、心动短信，以及包含人物、时间、地点和频道的对话历史。
- 角色 Agent：后端通过同一供应商适配层调用 DeepSeek 或 Dots Chat Completions API；进程默认由 `LLM_PROVIDER` 选择，也可由单次请求的 `X-LLM-Provider` 切换。两种模型共用人物卡、Prompt、输出校验与状态提交合同。
- 公开身份：浏览器生成匿名访客 ID，不依赖小红书内网 SSO。

## Render Blueprint 部署

仓库根目录的 `render.yaml` 会创建：

1. Python Web Service：`xindong-journey-humanlike`

它会通过 Render 的 `fromDatabase` 引用同一 Workspace 中已有的 `xindong-journey-db`，并把所有表创建在独立 schema `xindong_journey_humanlike`。这是为了遵守 Render 每个账号只能同时拥有一个活跃 Free PostgreSQL 的限制，同时保持两套应用的数据表隔离。

在 Render Dashboard 新建 Blueprint，选择本仓库。`render.yaml` 已声明两套非密钥默认值，并把两个 Key 都标记为 `sync: false`。首次同步时按需填写：

```text
DEEPSEEK_API_KEY=你的有效 DeepSeek API Key
DOTS_API_KEY=你的有效 Dots API Key
```

为了随时对比，建议两项都保留在 Render Secret 环境变量中，再用 `LLM_PROVIDER=deepseek|dots` 设置进程默认值；受支持的 LLM 请求也可携带 `X-LLM-Provider: deepseek|dots` 单次切换，不需要为了 A/B 重启服务。这个请求头只是供应商名称，绝不能承载 API Key。

两套 Key 都配置后，页面顶部会显示“台词模型”选择器。`/health` 与 `/api/bootstrap` 的 `llmProviders` 只公开默认、当前和可用的供应商名称，不返回 Key、Base URL 或模型名。

Dots 默认配置为：

```text
DOTS_API_BASE=https://note3-prev-api.askdiandian.com/v1
DOTS_MODEL=dots3-note-prev
DOTS_ENABLE_THINKING=false
```

Dots 的基础 URL 已包含 `/v1`；后端通过服务端 `api-key` 请求头认证。密钥必须只填在 Render 环境变量中，不要提交到 GitHub。未配置所选供应商、调用失败或输出未通过人物卡合同时，本轮明确失败且不会写入关系、记忆或事件，也不会静默改用另一供应商。

若 DeepSeek 请求返回 `http-402`，请在 DeepSeek Billing 检查账户状态，或在 Render 中替换 `DEEPSEEK_API_KEY`；不需要把 Key 写回 GitHub。Dots 失败同样只应报告供应商与安全错误类别，不应把响应头、请求体或 Key 写入日志。

Blueprint 默认使用 Free Web Service，并复用账号现有的 Free PostgreSQL，适合演示。Render 官方当前说明 Free PostgreSQL 会在创建 30 天后到期，长期运行应升级数据库计划。

通过 R5 人物与内容审核的剧情片首次播放为一次性有声过场；自然结束后自动进入逐字旁白。同一素材只在正文阶段作为静音循环背景，不承担剧情推进闸门。旧姜米自我介绍因没有可辨人物台词已被暂时下线，等待八位嘉宾各自的有声版本。

R5 起，事件片还必须通过人物身份路由：只有所选主角、当前搭档与资产审核记录精确一致时才播放事件母片；否则使用正确人物的动态立绘等待对应 Seedance 变体审核，绝不回退到姜米或其他嘉宾的错误镜头。人物身份牌由前端渲染姓名、职业、MBTI 和性格提示，首次出现约三秒后淡出，循环背景不会重复弹出。

R6 进一步要求媒体方案与玩家所选性别一致，并且片中可辨人物属于本局八人名单；不满足时只回退到玩家本人动态肖像并隐藏声音按钮。108 个审核源已通过哈希绑定写入运行时：100 个事件轮换与 8 个新增动态肖像；100 个首播事件源为有声 AAC，16 个动态肖像循环均静音。它保证主角性别匹配，但不把四套共享事件镜头描述成 16 人各自的完整精确脸套装。

R6 本轮在“R6新增上限¥60”的人工确认下结算 CNY 41.0770200、付费重试 0。规划 manifest 永久保持 `doNotSubmit=true`，防止再次付费提交；未来新增或重试仍受 `media/production/BUDGET_POLICY.md` 的 CNY 200 人工确认规则约束。

R9 把目录扩展到完整 16 MBTI × 两性。22 个 480p 候选在用户明确授权 CNY 500 硬上限后生成，实际结算 CNY 11.0599776，自动付费重试 0；人工审核后 14 个动态肖像与 4 个精确主角事件视频接入运行时，4 个伪文字候选保持 hold。`qince`、`shaozheng` 使用自己的静态身份图，不会借用其他角色镜头。这里记录的是本地源码和运行时集成状态；只有新的 Git 提交实际触发 Render 且公网健康检查通过后，才能称为 R9 已部署。

R9B 随后在独立 CNY 5 硬上限下，只补 `qince` 与 `shaozheng` 两条 4 秒静音动态肖像；一次提交结算 CNY 0.7917456，自动付费重试 0。原始回传未直接接入，只有通过本地安全循环衍生、faststart 重封装、完整解码、身份与移动裁切复核的 `001b` master 被 add-only 写入运行时，因此当前本地目录为 32/32 动态肖像。R9B 仍只是本地源码/运行时状态，未在本轮触发 Render 部署。

R10 Lite 只优化交付层，不删除多媒体：165/165 条视频、129 条有声音轨和 36 条静音素材全部保留，完整解码通过。视频从 266,177,881 B 降为 52,434,743 B，前端包从 258.83 MiB 降为 54.99 MiB；首页先显示 poster，短暂延后视频挂载，离场视频不预载。FastAPI 对媒体返回 Range 206 和 7 天缓存，对哈希前端资产返回一年 immutable 缓存。机器报告与紧凑结论分别位于 `qa/LITE-RUNTIME-MEDIA-R10.json`、`qa/LITE-RUNTIME-MEDIA-R10.md`。

## 本地运行

```bash
cp -n .env.llm.local.example .env.llm.local
# 在 .env.llm.local 中填 Key，并设置 LLM_PROVIDER=dots 或 deepseek
cd frontend
pnpm build
cd ..
./scripts/run-local-preview.sh
```

启动脚本会先加载旧 `.env.deepseek.local`，再用 `.env.llm.local` 补充或覆盖，因此新增 Dots Key 不会要求复制现有 DeepSeek Key。也可通过 `LLM_ENV_FILE=/绝对路径/私密配置.env` 指定第二层配置。默认打开 `http://127.0.0.1:4184/`。

## 安全边界

- GitHub 不包含 `.redInfo`、数据库口令、DeepSeek/Dots Key、Cowork 配置缓存或本地 `.env`；`.env.llm.local.example` 只有空值和公开默认值。
- 每个匿名访客默认每 10 分钟最多触发 20 次 LLM 调用，整个服务同期最多 200 次；可分别用 `AGENT_RATE_LIMIT` 与 `AGENT_GLOBAL_RATE_LIMIT` 调整。
- Dots 返回中的 `reasoning_content` 不进入人物记忆、剧情状态、前端或比较报告；只消费通过合同校验的可见 `content`。
- 玩家输入最大 240 字；Agent 只提出人物卡允许的结构化变化，服务端才拥有状态写入权。
- 浏览器访客 ID 不是账号系统；清理站点数据会得到新的体验身份。

供应商 A/B 的隔离 run、记录字段、评分维度和“已实现/已实模验证/已部署”证明边界见 [`docs/DOTS-PROVIDER-COMPARISON.md`](docs/DOTS-PROVIDER-COMPARISON.md)。修改 Blueprint 文件或 Dashboard 变量本身都不等于已经完成公网部署或 Dots 实模验证。
