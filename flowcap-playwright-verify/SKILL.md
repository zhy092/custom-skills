---
name: flowcap-playwright-verify
description: 对 FlowCap 纯静态前端（flowcap-app）做无头 Playwright 自测与全量回归的标准工作流，含预览服务、受管 Node 路径、路由守卫绕过、语法检查与常见坑。
agent_created: true
---

# FlowCap 前端 Playwright 自测工作流

用于对 `flowcap-app`（零 CDN 纯静态 HTML+CSS+原生 JS）做自动化验收与回归。

## 何时用
- 修复 bug / 加功能后需要无头浏览器自测
- 跑全量回归（verify*.cjs 链）
- 在交付前确认 0 控制台错误

## 前置与路径（受管运行时，勿用系统 node）
- Node： `/Users/zyb/.workbuddy/binaries/node/versions/22.22.2/bin/node`
- playwright 模块：`NODE_PATH=/Users/zyb/.workbuddy/binaries/node/workspace/node_modules`（已含 playwright）
- 预览服务（在 `flowcap-app/` 下起，驻留后台）：`python3 -m http.server 8080`
- 入口： `http://localhost:8080/pages/login.html`；根 `/` 与 `/pages/` 都跳登录页

## 标准 verify 脚本骨架
```js
const { chromium } = require('playwright');
const BASE = 'http://localhost:8080/pages/';
const results = [];
const ok = (n, c, e) => results.push({ name: n, pass: !!c, extra: e || '' });

(async () => {
  const browser = await chromium.launch();
  const consoleErrors = [];
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text()); });
  page.on('pageerror', e => consoleErrors.push('PAGEERR ' + e.message));
  // 绕过路由守卫：已登录才放行非登录页
  await page.addInitScript(() => { try { localStorage.setItem('flowcap:auth', '1'); } catch (e) {} });
  // ... goto / click / evaluate / assert ...
  await browser.close();
  const total = results.length, passed = results.filter(r => r.pass).length;
  console.log('\nTOTAL: ' + passed + '/' + total + ' passed, consoleErrors=' + consoleErrors.length);
  process.exit(passed === total && consoleErrors.length === 0 ? 0 : 1);
})().catch(e => { console.error('FATAL', e); process.exit(2); });
```

## 必做：改完外壳先语法检查
改 `app.js` 等共享文件后，先跑：
```
NODE --check assets/js/app.js && NODE --check assets/js/data.js && NODE --check assets/js/pages/*.js
```
**模板字符串反引号不配对**会让整个 `app.js` 解析失败、所有页面脚本级联崩溃，且只在运行时暴露（`Unexpected token 'class'` / `Fc.ui is undefined`）。这是最高频的阻断性坑。

## 常见坑
1. `page.evaluate(fn, arg)` 只接受**单参**；要传多个就包成对象 `{ s, q }` 并在 fn 里解构。
2. 选真实目录节点要用 `:not([data-cat=""])`；「我的收藏」(`data-fav`) / 「全部接口」(`data-cat=""`) 是虚拟节点，无 `tree-actions`。
3. 悬浮态 `:hover` 用 `page.hover(selector)` 触发；CSS `:has()` 在现代 Chromium 可用。
4. 连续快速启动多个浏览器实例会**偶发启动崩溃**（非真实失败）；脚本串行跑、或单跑一次确认稳定。
5. 收藏数据模型：`apis[].fav` 布尔；收藏视图 = `apis.filter(a=>a.fav)`；录制页与接口管理共用同一份，闭环靠 `toggleFav` 统一读写。

## 验证清单（第六轮口径，150/150）
- verify.cjs(30) verify2(13) verify3(16) verify4(20) verify5(4) verify6(16) verify7(16) verify8(18) verify9(17)
- verify9 覆盖：固定高度、收藏闭环+星星实心、弹窗锁背景、删除按钮不溢出、JSON 按钮居中、悬浮数量可见、开始录制上下文跳转、树搜索保持过滤、顶部搜索移除。
