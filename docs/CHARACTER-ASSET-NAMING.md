# 人物卡与媒体资源命名规范

这套规范同时服务代码调用和人物审核。现有大文件不做物理复制或重命名；
`media/character-asset-registry.v1.json` 提供稳定别名，并保留真实的
`sourcePath` 与 `runtimePath`。

## 双轨名称

- 机器名（`assetId`）：只用小写 ASCII、数字和连字符。
- 文件别名（`canonicalFilename`）：`assetId` 加原始扩展名。
- 审核名（`displayName`）：中文姓名、MBTI、三位序号、动作、场景、变体。

通用格式：

```text
hj-{characterId|shared}-{mbti|multi}-{sequence}-{action}-{scene}[-variant]
{中文名|多角色}-{MBTI|MULTI}-{sequence}-{中文动作}-{中文场景}[-变体]
```

例如黎川的人物首页动态形象：

```text
assetId:           hj-lichuan-esfj-001-first-appearance-character-profile
canonicalFilename: hj-lichuan-esfj-001-first-appearance-character-profile.mp4
displayName:       黎川-ESFJ-001-初次登场-人物主页
runtimePath:       /media/video/CHAR-lichuan-portrait.mp4
```

这就对应产品同学提出的“黎川-esfj-001-初次登场”，同时补充场景，避免同一动作在
不同页面或剧情节点中冲突。

## 序号段

| 序号 | 含义 |
| --- | --- |
| `000` | 静态人物定妆照 / 身份审核锚点 |
| `001` | 人物初次登场动态形象 |
| `101`–`109` | Day 1 主线与首次记忆回声 |
| `201`–`216` | 中后期 Story Event |

这些编号由生成脚本中的显式事件表维护。新增事件时分配新编号，不因排序或插入而重排
已有资源。

## 人物卡命名

人物卡继续集中存储在 `content/character_cards.v3.json`，不拆成 16 份重复文件。
每个角色都有稳定虚拟 ID：

```text
character-card-{characterId}-{mbti}-v3
```

例如：`character-card-lichuan-esfj-v3`。Registry 的 `characters` 目录和每个单人资产的
`characterCardRef` 都使用这一 ID，可从媒体反查人物卡，也可从人物卡反查定妆照和动态
形象。

## 关键审核字段

每条资产记录都包含：

- `characterId` / `characterName` / `mbti` / `gender`：明确主视角；没有可靠主视角时为
  `null` / `多角色` / `MULTI` / `混合`，不从演员数组顺序猜测。
- `identityCast` / `identityScope`：实际允许出现的角色集合与身份范围。
- `sequence` / `action` / `scene`：剧情定位。
- `mediaType` / `usage`：资源类型与前端用途。
- `sourcePath` / `runtimePath`：仓库母版与线上调用路径。
- `sha256` / `duration` / `dimensions` / `audio`：技术验收证据。
- `status` / `rightsReview` / `rights`：运行时状态与权利边界。
- `legacyAssetId` / `baseAssetId` / `rotationSlot`：回查旧运行时 manifest 和 R6 路由。

`sharedAsset: true` 只表示该资产没有一个可证明的唯一主角，不表示可以任意替换人物。
相同 SHA-256 只有在 `identityCast` 完全一致时才允许复用。

## 生成与验证

在仓库根目录运行：

```bash
python3 scripts/build_character_asset_registry.py
python3 scripts/validate_character_asset_registry.py
python3 scripts/test_character_asset_registry.py
```

Validator 会检查：

1. 16 人静态定妆照和 16 人动态形象完整；
2. 每一条现有 runtime media 都被 registry 收录；
3. `assetId`、规范文件名和旧 runtime ID 唯一；
4. 文件存在且 SHA-256 与 manifest 一致；
5. 姓名、MBTI、性别、人物卡引用与角色 ID 一致；
6. 单人资源严格满足 `identityCast == [characterId]`；
7. 不同身份集合不得复用同一文件内容；
8. 尺寸、时长、音频与 rights 状态有明确记录。

该验证证明结构、文件和声明身份的一致性；人物长相是否真正与参考图一致仍需逐帧人工视觉
审核，不能仅靠文件名或 SHA-256 自动判定。
