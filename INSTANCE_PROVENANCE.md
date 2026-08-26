# 心动之旅双版本边界

## 原版（冻结，不在本次发布范围）

- GitHub：`https://github.com/Dancejie/xindong-journey-echo`
- Render：`https://xindong-journey-echo.onrender.com/`
- 本次分叉基线：`cc0c157`
- 本次工作不向原仓库推送，也不修改原 Render Web Service、数据库或环境变量。

## 人味增强版（本次独立发布）

- GitHub：`https://github.com/Dancejie/xindong-journey-humanlike`
- Render Web Service：`xindong-journey-humanlike`
- Render PostgreSQL：`xindong-journey-humanlike-db`
- 角色 Agent：DeepSeek 只读取当前人物卡、当前剧情节点、已提交 memory 与当前会话上下文；结构化台词、态度、策略候选仍由确定性合同校验后才可落库。
- 开局：优先使用已校验台本缓存；新增角色缓存未命中时立即安装确定性首幕，不在“正在开启”阶段等待完整九节点 LLM 生成。后续已提交节点按需请求人物化改写。

## 密钥边界

- `.env.deepseek.local` 只用于本地，不加入 Git。
- `DEEPSEEK_API_KEY` 只可写入人味增强版 Render 服务的 Secret 环境变量。
- 不复制、读取或变更原 Render 服务的密钥。
