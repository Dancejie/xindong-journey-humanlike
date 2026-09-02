# Dots / DeepSeek 人物对白与剧情对比

## 目的

在不替换 DeepSeek、不改变人物卡和 Story Engine 权限边界的前提下，让同一套角色 Agent 与 Story Director 可以选择 Dots 或 DeepSeek。比较对象是模型的可见人物表演与合法结构化输出，不是让模型接管事件资格、StatePatch、route、ending 或数据库写入。

```text
同一人物卡 + 同一公开快照 + 同一合法记忆 + 同一 Prompt/输出合同
                              |
                    LLM_PROVIDER 默认值
                 或 X-LLM-Provider 单次覆盖
                        /             \
                  DeepSeek            Dots
                        \             /
                  同一 JSON/业务校验器
                              |
                通过后才原子提交；失败不写状态
```

## 两套配置

| 用途 | DeepSeek | Dots |
| --- | --- | --- |
| API Key | `DEEPSEEK_API_KEY` | `DOTS_API_KEY` |
| Base URL | `DEEPSEEK_API_BASE=https://api.deepseek.com` | `DOTS_API_BASE=https://note3-prev-api.askdiandian.com/v1` |
| Model | `DEEPSEEK_MODEL=deepseek-v4-flash` | `DOTS_MODEL=dots3-note-prev` |
| 思考开关 | 沿用现有 DeepSeek 行为 | `DOTS_ENABLE_THINKING=false` |
| 服务端认证 | 现有 DeepSeek 链路 | HTTP 请求头 `api-key` |

Dots Base URL 已包含 `/v1`。适配器只应在其后拼接 `chat/completions`，不能形成重复的 `/v1/v1/chat/completions`。`DOTS_ENABLE_THINKING=false` 是对白 A/B 的建议默认值：减少额外时延，并让比较集中在可见台词；它不是人物质量结论。

## 安全地同时配置

```bash
cp -n .env.llm.local.example .env.llm.local
```

只编辑 `.env.llm.local`：

```dotenv
LLM_PROVIDER=dots
DOTS_API_KEY=在本机填写真实值
```

仓库已有 `.env.deepseek.local` 时不需要打开、复制或迁移旧 Key。`scripts/run-local-preview.sh` 会按以下顺序分层加载：

1. 若存在，先加载旧 `.env.deepseek.local`，保留 DeepSeek 链路；
2. 若设置 `LLM_ENV_FILE`，再加载该文件；否则再加载 `.env.llm.local`；
3. 后加载的非空或显式变量覆盖同名旧变量。

示例文件故意不写真实 Key，也不会用空的 `DEEPSEEK_API_KEY` 覆盖旧配置。不要把 `.env.llm.local` 加入 Git，不要在 shell 中执行 `set -x`、`env`、`printenv` 或带认证头的 `curl -v` 来“证明配置”。

启动：

```bash
./scripts/run-local-preview.sh
```

也可以把第二层私密文件放在仓库外：

```bash
LLM_ENV_FILE=/绝对路径/llm-private.env ./scripts/run-local-preview.sh
```

脚本错误信息不会回显文件内容或 Key。

## 两种切换方式

### 进程默认值

```dotenv
LLM_PROVIDER=deepseek
```

或：

```dotenv
LLM_PROVIDER=dots
```

这决定没有请求级覆盖时使用哪一套配置。旧环境没有 `LLM_PROVIDER` 时继续以 DeepSeek 为默认，避免改变已有行为。

### 单次请求覆盖

对受支持的 LLM 请求添加：

```http
X-LLM-Provider: dots
```

或：

```http
X-LLM-Provider: deepseek
```

这样可以在同一个正在运行的本地服务里比较，不必重启。该请求头只允许两个固定值，不接受 URL、模型名或 Key。未提供时回到 `LLM_PROVIDER`；选择了未配置 Key 的供应商时应明确失败，不能静默跨供应商回退。

当两套 Key 都可用时，页面顶部的“台词模型”选择器会写入同一个请求头，适合人工试玩切换。它只影响之后的生成；已经提交的剧情、关系、独立记忆和 revision 不会被回写。`/health.llmProviders` 与 `/api/bootstrap.llmProviders` 只返回供应商名称，可用于确认选择器为何显示或隐藏，不会暴露认证配置。

角色回合示意：

```bash
curl -sS -X POST \
  "http://127.0.0.1:4184/api/runs/$RUN_ID/agents/$CHARACTER_ID/messages" \
  -H 'Content-Type: application/json' \
  -H "X-Client-Id: $CLIENT_ID" \
  -H 'X-LLM-Provider: dots' \
  --data '{"message":"我今天其实有点不想逞强。","revision":12}'
```

Story Director 示意：

```bash
curl -sS -X POST \
  "http://127.0.0.1:4184/api/runs/$RUN_ID/story-director" \
  -H 'Content-Type: application/json' \
  -H "X-Client-Id: $CLIENT_ID" \
  -H 'X-LLM-Provider: deepseek' \
  --data '{"revision":24}'
```

示例中的 run 必须已经位于对应合法节点，revision 也必须来自当前快照；否则业务层会先拒绝，不会调用模型。

### 离线台本与风味脚本

三条离线链路也复用同一适配器、认证规则与 `reasoning_content` 丢弃边界：

```bash
# 人物卡驱动的角色对白横向样片
python3 scripts/sample_character_flavor.py --provider dots

# 三个隔离 Story Director 场景
python3 scripts/sample_story_director.py --provider dots

# 首日台本缓存；对比时先写 /tmp，避免覆盖当前审核缓存
python3 scripts/generate-day1-script-cache.py \
  --provider dots \
  --output /tmp/dots-day1-cache.json
```

把 `dots` 改为 `deepseek` 即可生成另一组。样片默认文件名包含供应商；正式替换 `content/day1_script_flavors.v1.json` 前，仍需完成合同校验、人物风味复核和当前项目 QA。执行这些命令会真实调用所选 API；仅做语法或配置检查时不要运行。

## 公平比较流程

角色回合会写入关系、态度和独立记忆，Story Director 可能提交事件。因此不能在同一个 run 上先调用 DeepSeek、再调用 Dots，然后把第二次输出当成同条件结果。

1. 建立两个隔离 run，选择相同玩家、相同阵容路径和相同剧情操作。
2. 比较前确认 `contentVersion`、人物卡 hash、Prompt 版本、节点、公开事实、关系轴、合法记忆和 revision 的语义输入一致。
3. A run 的请求固定 `X-LLM-Provider: deepseek`，B run 固定 `X-LLM-Provider: dots`。
4. 发送完全相同的玩家文本；不要边看结果边修改另一边输入。
5. 每个场景至少重复 3 次独立样本，避免用一条随机“金句”下结论。
6. 先跑结构化合同与事实边界，再做盲评；合同失败的输出不能凭主观喜欢放行。
7. 延时、Token 和错误率单独记录，不与“人味”总分混成一个维度。

建议至少覆盖：初见、支持、追问、挑战、越界、修复、一次具体行动、一次记忆回收、同一句中性输入的跨角色对照，以及 early/middle/late Story Director 快照。

## “更有人味”评分表

每项可用 `0=不成立 / 1=部分成立 / 2=稳定成立`，隐藏供应商名称后盲评。

| 维度 | 观察问题 |
| --- | --- |
| 人物可辨识 | 隐去姓名和 MBTI 后，还能凭取舍、语序和行动认出角色吗？ |
| 具体性 | 是否说清人、物、时间、地点、条件或下一动作，而不是只给气氛？ |
| 主体性 | 角色是否表达自己的利益、犹豫、拒绝或反价，而非永远服务玩家？ |
| 情绪承接 | 是否先回应玩家真实情绪，再处理字面任务；有没有复读和空泛安慰？ |
| 对话自然度 | 是否像人在当场说话，允许短句、停顿和轻微不完美，而非诗化谜语或说明书？ |
| 推进性 | 本轮是否推动一个事实、行动、条件、关系或合法事件？ |
| 连续性 | 是否正确使用允许看到的历史与记忆，没有串角或遗忘当前场景？ |
| 边界与事实 | 是否不编造设定、创伤、他人私密记忆或未授权剧情状态？ |
| 合同通过率 | JSON、枚举、Intent、关系限幅、memory fact/belief 是否全部通过服务端校验？ |

## 最小记录字段

每条 A/B 证据应记录：

```text
caseId
contentVersion / characterCardHash / promptVersion
provider / model / enableThinking
隔离 runId / 输入快照 hash / revision
相同的玩家输入
通过校验后的可见 dialogue / stageDirection / public reason
contractPass / failureCategory / committed
latencyMs / usage（供应商返回时）
盲评人 / 各维分数 / 简短理由
```

不要记录：API Key、完整认证请求头、Cookie、数据库 URL、全量私密记忆、原始系统 Prompt、供应商返回的 `reasoning_content`。Dots 的 `reasoning_content` 不进入前端、人物记忆、剧情状态或比较报告；只比较 `message.content` 中通过合同校验的可见结果。

## Render 配置与切换

根目录 `render.yaml` 同时声明：

- `LLM_PROVIDER` 及两套公开 Base URL / Model 默认值；
- `DEEPSEEK_API_KEY` 和 `DOTS_API_KEY` 均为 `sync: false`；
- `DOTS_ENABLE_THINKING=false`。

在 Render Dashboard 手工填写 Secret 后，可以保留两个 Key。修改 `LLM_PROVIDER` 会改变进程默认值；现场 A/B 仍优先用 `X-LLM-Provider` 单次覆盖，避免为了每条样本反复重启。不要把 Dashboard 的 Secret 复制回 Blueprint、GitHub Issue、QA Markdown 或浏览器 localStorage。

本文件与 `render.yaml` 的修改不执行 Blueprint 同步、不触发部署，也不证明公网服务已经使用 Dots。

## 失败与状态提交边界

- 供应商值不在 allowlist：请求应拒绝，不发网络调用。
- 所选供应商 Key 未配置：明确报告 `unconfigured` 类错误，不尝试另一供应商。
- 远端超时、限流、鉴权或解析失败：记录安全错误类别，不记录响应头或请求体。
- JSON/业务合同失败：整轮不提交关系、记忆、事件或 revision。
- 角色 Agent 只能提出 allowlisted Intent 和受限关系变化。
- Story Director 只能在服务端给出的合法候选和表层输出白名单内工作；状态机仍负责原子提交。
- 模型可见文本更自然，不等于模型获得了剧情状态写权限。

## 证明等级

| 能说什么 | 至少需要的证据 |
| --- | --- |
| `configured` | 本地或 Render 环境变量存在；Key 值未泄露 |
| `implemented` | 选择器、两套适配器与调用点代码存在 |
| `tested` | 供应商选择、认证头、错误隔离和合同测试通过 |
| `live-provider-verified` | 使用真实 Key 完成一次受控调用并通过合同；这仍不是人味结论 |
| `comparison-reviewed` | 隔离快照、多样本、盲评记录完成 |
| `experience-verified` | 真实角色回合与 Story Director 的完整本地路径走通，状态与 UI 回执正确 |
| `deployed` | 目标 Render URL、时间、health 与公网 smoke 均有当前证据 |

单元测试、mock、配置文件或一次远端 `200` 都不能单独证明“Dots 更有人味”；同样，编辑 `render.yaml` 不能证明已部署。
