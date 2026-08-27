# 回声剧场图标系统

## 目标

当前前端使用一套轻量、克制的线性图标，视觉语言参考 Streamline 在 Figma Community 发布的 [1,000 Free UI/UX Icons](https://www.figma.com/design/icDIhas4ZRJPihZAM5mh9S/1-000-Free-UI-UX-Icons---Download-vector-svg-and-png-icons--Community-?node-id=1843-108&p=f&t=awAv292kljehT8ew-0)。图标服务于交互识别，不代替正文，也不把产品变成可下载的图标素材库。

## 实现规范

- 入口：`frontend/src/ui/Icon.tsx`
- 基准画板：`24 × 24`
- 线宽：`1.5`
- 端点与转角：`round`
- 默认颜色：继承 `currentColor`
- 双调强调：`rose` 映射 `--rose`，`lavender` 映射 `--lavender`
- 当前必要子集：`heart`、`arrow-right`、`arrow-left`、`arrow-up-right`、`close`、`volume-on`、`volume-off`、`check`、`radio-empty`、`plus`、`status-dot`

所有 SVG 都固定为装饰元素：`aria-hidden="true"`、`focusable="false"`。可点击控件必须由按钮文字或 `aria-label` 提供可访问名称，不能依赖图标本身传达名称。

## 使用规则

```tsx
import { Icon } from './ui/Icon'

<button aria-label="关闭私聊">
  <Icon name="close" />
</button>
```

1. 只在有明确操作语义时添加图标；正文标点、数字正负号等内容字符保留为文本。
2. 图标尺寸变化不能改变触控目标。关闭、发送、声音等图标按钮维持至少 `40 × 40px`；按钮的 active、disabled、loading 状态不得重新排版。
3. 不直接在页面粘贴新的 SVG。需要新增图标时，先扩展 `IconName` 和 registry，再在组件中调用。
4. 不把 registry 暴露为浏览、批量下载或复制图标路径的用户功能。

## 来源与边界

本实现采用的是风格参考，并非从 Figma 文件下载或复制 SVG path。`Icon.tsx` 中的路径由本项目基于基础几何重新绘制，仅覆盖当前产品所需的 11 个语义。参考来源及 CC BY 4.0 署名信息见根目录 `THIRD_PARTY_NOTICES.md`。
