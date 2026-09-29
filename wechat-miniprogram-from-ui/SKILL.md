---
name: wechat-miniprogram-from-ui
description: Convert a UI design (Ardot/PNG screenshot) into a complete WeChat Mini Program project with native WXML/WXSS/JS, including pages, components, mock data, test cases, and deployment guide.
agent_created: true
---

# 微信小程序从 UI 稿到可运行项目

## 概述

将移动端 UI 设计稿或截图转化为微信小程序原生项目（WXML/WXSS/JS），严格还原布局、配色、圆角、间距，输出可直接导入微信开发者工具的完整代码、测试用例与发布指南。

## 适用场景

- 用户提供了设计稿/截图，要求「帮我开发成微信小程序」。
- 需要完整的小程序页面、组件、数据层、交互和发布流程。
- 目标是高审美、高还原度的消费级小程序界面。

## 工作流程

### 1. 确认需求与技术方案

- 明确页面数量、TabBar 结构、是否需要自定义导航栏。
- 确认金额颜色规则（如收入红 #EF4444，支出绿 #10B981）。
- 确认主色、背景色、卡片色、分类色等设计 Token。
- 决定输出目录（默认 `/Users/zyb/Desktop/bill-miniprogram`）。

### 2. 初始化项目结构

创建以下文件与目录：

```
project/
├── app.js / app.json / app.wxss
├── project.config.json / sitemap.json
├── custom-tab-bar/          # 自定义 TabBar（如需）
├── components/              # 公共组件
├── pages/                   # 页面
├── utils/                   # 数据、格式化、存储
├── images/                  # 图标资源（优先 SVG）
└── docs/                    # 测试用例与部署文档
```

### 3. 全局配置

- `app.json` 注册所有页面，配置 `tabBar.custom: true`、自定义导航栏 `navigationStyle: custom`、全局 `usingComponents`。
- `app.wxss` 定义 CSS 变量：主色、语义色、圆角、阴影、安全区工具类。
- `app.js` 在 `onLaunch` 获取系统信息（状态栏高度、安全区）。

### 4. 数据层

在 `utils/data.js` 中实现：

- 分类配置（支出/收入）。
- Mock 账单数据（使用真实生活场景）。
- 增删改查、按月份过滤、分类统计、搜索。
- `utils/storage.js` 封装 `wx.getStorageSync`。
- `utils/format.js` 提供金额、日期、月份格式化。

### 5. 公共组件

按需创建：

- `status-bar`：状态栏高度占位。
- `category-icon`：分类 emoji + 彩色圆形背景。
- `transaction-item`：交易列表项（支出绿/收入红）。
- `amount-keyboard`：自定义数字键盘。
- `month-picker`：底部月份选择弹窗。
- `custom-tab-bar`：底部导航（使用 cover-view/cover-image）。

### 6. 页面实现

按设计稿顺序实现页面：

1. **首页**：月份选择、搜索、余额卡片、快捷操作、按日期分组列表。
2. **记账**：金额显示、支出/收入切换、分类网格、日期备注、数字键盘。
3. **语音记账**：麦克风动画、波形、模拟识别、自动分类结果卡片。
4. **统计**：收支卡片、CSS conic-gradient 环形图、分类排行（可点击）。
5. **分类明细**：大图标、总额占比、交易列表。
6. **我的**：授权、导出、恢复/清空数据。
7. **搜索**：关键词过滤、热门标签。

### 7. 视觉还原要点

- 严格使用设计 Token，避免硬编码。
- 金额颜色：支出绿色、收入红色（与用户明确后确定）。
- 自定义导航栏需处理 `statusBarHeight` 与胶囊按钮高度。
- 所有滚动视图设置 `flex: 1` + `min-height: 0`（或 `height: 0`）确保正常滚动。
- TabBar 图标优先使用 SVG，避免 PNG 生成依赖。
- 使用 `env(safe-area-inset-bottom)` 适配底部指示条。

### 8. 校验与测试

- 使用 Node.js 校验所有 `*.json` 文件。
- 使用 `node --check` 校验所有 `*.js` 语法。
- 编写 Node 测试脚本，用 mock `wx` 全局对象测试数据层（金额汇总、分类统计、搜索、新增）。
- 编写 `docs/test-cases.md`，用日常生活场景覆盖所有页面。

### 9. 部署文档

编写 `docs/deploy.md`，包含：

- 导入微信开发者工具。
- 预览、真机调试。
- 代码上传、提交审核、正式发布。
- 常见审核注意事项。

## 输出检查清单

- [ ] 项目可导入微信开发者工具并编译通过。
- [ ] 所有 JSON/JS 语法校验通过。
- [ ] 数据层单元测试通过。
- [ ] 首页、记账、语音、统计、分类明细、搜索、我的页面均可访问。
- [ ] 自定义 TabBar 在三个 Tab 页正确高亮。
- [ ] 金额配色符合用户要求。
- [ ] 项目主包大小 < 2MB。
- [ ] README.md、test-cases.md、deploy.md 齐全。
