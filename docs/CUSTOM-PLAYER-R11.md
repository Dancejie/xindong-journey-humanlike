# R11 · 用自己进入心动之旅

## 交互与边界

从节目介绍、MBTI选择或角色选择进入「创建我的角色」。16 MBTI、男/女性角色、18岁以上年龄、昵称、职业、公开简介、相处偏好与边界，以及一张本人/已授权成年人的照片。

照片仅作外观参考，不做面相、人格、种族、健康、收入或其他属性推断。仅处理JPEG/PNG/WebP单帧图片，上传≤8MB、≤2400万像素；转存最长边1280px JPEG并去除EXIF/GPS。照片不会进入前端公共资源目录。用户可先使用自己的静态照片进入游戏，不用等待视频。

人物卡的事实来自用户表单，DeepSeek/Dots只补写经校验的表达层；没有配置或调用失败会明确标注「根据填写资料整理」，不偷偷切换模型。偏好用于生成玩家可选建议，不能变成NPC凭空知道的过往。游戏规则、角色池、状态、记忆仍由原引擎处理。自定义玩家+7位现有嘉宾共8人，不允许自己与自己聊天。私有角色卡通过请求局部ContextVar解析，不注册到共享32角色库。

## 储存与删除

`backend.init_db` 新增 `custom_characters`、`custom_video_budget_jobs`，不覆盖旧表、旧人物或旧存档。照片、候选和确认后的视频保存在PostgreSQL BYTEA，避免Render重启丢失；局快照保存人物卡，读取时从所有者当前卡刷新批准的媒体。

- 列表/创建/查看/视频/删除API均采用既有 X-Client-Id 或可信SSO所有者验证。
- 本地访客身份保存在当前浏览器；清理浏览器数据后无法找回匿名角色。不要把匿名访客身份当成跨设备正式账户。
- 照片/视频通过64位随机hex能力URL读取，不包含账户token；能力URL本身有访问权，请勿分享。禁止缓存，删除后撤销。
- 删除会同时删除本项目中的人物卡、照片、视频和关联局/记忆。已传给第三方模型/视频服务的数据受其保留政策控制，不能承诺远端撤回。
- 费用账本不含照片/个人资料，删除角色不会清空费用或恢复额度。
- 默认每位访客最多5个自定义角色，全库上限由 `CUSTOM_CHARACTER_GLOBAL_LIMIT` 控制（默认1000）。生产需要按数据库容量设置更低限额或提供对象存储。

## 视频：创建时默认提交一次，审核后使用

默认 Seedance 2.0 Mini（用户明确型号）、10秒、480p、9:16、真人写实的单人动态形象。逐秒director card固定本人参考、轻微自然表情与单一动作；不克隆语音、不强迫生成口型或对白，不替玩家作剧情决定。已提交的旧5秒任务仍按保存的规格查询和验收，不重生成或误标为10秒。480p技术校验包含Mini已验证的496×864输出，不将其误判为超尺寸；未知尺寸不扩大放行。

创建表单默认勾选「同时生成动态形象」，显示模型、规格和单次费用；同一创建按钮同时完成照片传输授权与一次任务授权，无需另外点击生成。取消勾选可只用照片游玩。新前端在创建请求中传 `autoVideo: true` 和已展示的 `maxCostCny`，服务端保存人物卡后原子预留预算并在后台提交。旧客户端未传此标记时不自动提交，避免扩大原有的照片授权。

刷新、重开已保存角色、重复同一个 `requestId`、查看状态均不会开新任务。配置未就绪、报价变化或预算不足时，人物卡和照片仍保存成功，界面明确说明「未提交视频」，也不会在配置恢复后后台补单。旧的、从未提交的角色可通过带明确费用的按钮手动提交一次。生成失败/未知状态没有自动重试入口。

不可用时视频区标为「暂未启用」，显示禁用按钮与原因，不再用「可选」误导用户。可点「重新检查视频通道（不扣费）」读取原角色的新配置，不清表单、不建新角色、不补单；只有通道恢复且角色从未提交时，才显示带明确价格的生成按钮。

2026-09-09只读核对：既有受保护Fumin凭据的 `/v1/models` 返回HTTP200，Seedance列表仅 `seedance-2.0-mini`、`seedance-2.5`，未列出正式2.0。本项目既有片段实际使用2.0 Mini；用户随即明确「我指的就是2.0 mini」，因此修正之前对正式版的误解，精确锁定 `seedance-2.0-mini`。只读恢复一项已结算R9B任务，供应商仍返回succeeded/Mini，确认结果下载域名。没有上传照片或提交任务；模型列表存在不等于新生成已实测成功。

服务器需要配置以下环境变量，真实值只能放安全环境配置，不进git或前端：

```dotenv
CUSTOM_VIDEO_API_KEY=
CUSTOM_VIDEO_MODEL=seedance-2.0-mini
CUSTOM_VIDEO_BASE_URL=https://fumin.ai
CUSTOM_VIDEO_UNIT_COST_CNY=
CUSTOM_VIDEO_BUDGET_CNY=
CUSTOM_VIDEO_BUDGET_APPROVAL=
CUSTOM_VIDEO_DOWNLOAD_HOSTS=
CUSTOM_VIDEO_GENERATE_AUDIO=false
```

可以复用安全环境已有的 `FUMIN_API_KEY`。新生成精确模型ID固定为 `seedance-2.0-mini`，提交前再次探测 `/v1/models`。ID检查本身不是通道可用的证据；未查到精确型号就不上传照片。正式版/Fast/2.5或未知别名在上传前拒绝，不静默换模。`CUSTOM_VIDEO_DOWNLOAD_HOSTS` 只接受供应商实际结果的精确域名，不能用 `*`、内网IP或绕过安全校验。服务器须安装 `ffprobe`；缺少校验工具时视频功能关闭，文本和照片正常可玩。

本地启动脚本另支持被git忽略的 `.env.custom-video.local`。其中 `CUSTOM_VIDEO_CREDENTIALS_FILE` 指向已授权且权限600/400的Fumin dotenv；只解析 `FUMIN_API_KEY`，不执行该文件。当前LaunchAgent不能直接读取Documents里的原文件，因此仅将已授权Fumin配置提供至 `.local-runtime/private/`（目录700、文件600、git忽略；原文件不变），不改变系统访问权限，也不把凭据放入跟踪源码。凭据读取失败不能退出整个游戏，必须降级为照片可玩。LaunchAgent不继承交互shell的Homebrew PATH；脚本补充已安装ffprobe的目录，不绕过视频校验。生产仍用平台安全环境变量，不依赖开发机路径。当前本地已接型号/凭据/已验证下载域名；2026-09-09按用户「以后这个链路无需确认」的持续授权启用本地配置。

费用依据：最近Mini无视频输入480p已结算档与历史8秒档一致，但日志未返回时长，因此不是当前10秒合同报价。历史保守10秒估计约¥1.24，当前设置每次¥2经验性预留、本地累计保守上限¥5；不挪用旧批次预算，不自动提高或补充额度。真实费用以供应商结算为准，经验预留不能声称是供应商保证的封顶价。

2026-09-09新增授权：用户明确指定Mini并要求此链路以后无需确认。因此「创建人物」默认安排一次任务，旧planned角色的一次生成按钮直接执行，不增加第二次付费确认。`CUSTOM_VIDEO_BUDGET_APPROVAL` 保存本次持续授权的范围标签；照片授权和生成后形象验收仍保留。额度账本包含失败/未知提交的保守预留，不能通过删除角色或刷新绕过。范围仅Mini/480p/10s自定义动态形象，不扩大至其他型号、媒体批次或无限预算；其他项目超过¥200的人工复核规则不变。价格不明或变化时不可用旧5秒价/低估价绕过额度限制。

创建按钮或旧角色的手动生成按钮显示费用，服务端锁定预算并绑定参考图hash、prompt/spec hash、model、授权模式（创建自动/旧角色手动）、审核时间、费用上限后才提交。各worker共享PostgreSQL事务锁与持久费用账本；重复点击只返回原任务，不会重新生成。失败和不确定状态不自动重试，不自动释放预留。任务ID、provider URL和内部director只在服务器保存；UI可见请求型号、供应商实际返回型号（若有）和该任务原始时长，不用当前配置覆盖旧任务的规格。

```text
planned → reserved → submitted → processing → candidate → approved
                                        ↘ failed / needs_review
```

查询原任务不受以后降低新增预算影响。未知提交/服务重启后先核查原job，不能重新POST。视频须通过HTTPS域名、公网IP、大小、MIME、ffprobe时长/编码/尺寸校验；再让用户预览确认像自己，才标记 `approved-runtime`。未经确认不会出现在游戏里。网络失败保留原任务；永久无效结果进入 `needs_review`。管理员核对供应商账单/作业状态后再人工处理，勿直接重置 `planned`。

## 本地验证与部署

```sh
python -m backend.init_db
PYTHONPATH=.:backend python -m unittest discover -s backend -p 'test_*.py' -q
# 仅显式提供本地测试库时运行真实PG集成测试，自动使用并清理随机隔离schema：
CUSTOM_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:5432/cowork_dev PYTHONPATH=.:backend python -m unittest backend.test_custom_api -v
cd frontend
npx tsc --noEmit
npm run build
```

视频测试均mock provider，包括成功、超时、未知提交、下载/安全校验和审核；另用本地ffmpeg生成无人物测试片检查真实ffprobe。两者均不等于真实Seedance生成/人脸验收。版本 `4.2.2-custom-video-availability-r11` 的当前交付是本地实现与验证；没有推送GitHub或替换任何线上实例。现有Render启动命令会执行schema初始化；部署前另需核对数据库容量、服务商数据保留政策、ffprobe可用性和当前项目预算。
