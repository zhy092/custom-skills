// collect_doc_images.js — 从虚拟滚动富文档中"边滚边收"所有图片 URL
//
// 为什么需要脚本：文档用懒加载 + 虚拟列表，一次性 querySelectorAll 只能拿到
// 当前视口附近的图片。必须**分屏滚动 + 每屏收集**，否则会漏掉后段图片
// （实测：一次性收集 45 个，分屏滚动后有效图片 22 张，且分布在不同章节）。
//
// 用法：huashu-chrome 的 eval 工具**只接受单表达式**（带分号的多语句会报
// `Unexpected token ';'`）。因此：**分步调用，每步传一个 IIFE**，不要整段粘贴。
//
//   步 0（初始化，调用一次）
//     (() => { window.__imgs = new Set(); window.__y = 0; return 'init' })()
//
//   步 1（重复 N 次，直到返回的 y 不再增长；每次推进 600px）
//     (() => {
//       const push = (root) => {
//         try {
//           root.querySelectorAll('img').forEach(im => {
//             const s = im.currentSrc || im.src;
//             if (s && !s.startsWith('data:')) window.__imgs.add(s);
//           });
//         } catch (e) {}
//       };
//       push(document);
//       document.querySelectorAll('iframe').forEach(f => { push(f.contentDocument); });
//       window.scrollTo(0, window.__y);
//       window.__y += 600;
//       return JSON.stringify({ count: window.__imgs.size, y: window.__y,
//                               max: document.body.scrollHeight });
//     })()
//
//   步 2（取结果；把 returned 的 JSON 存下来给下一步下载用）
//     (() => JSON.stringify([...window.__imgs], null, 1))()
//
// 下载（关键）：
//   ❌ curl 直接请求 → 0 字节（无登录态）
//   ✅ 用 huashu-chrome 的 fetch 工具：binary: true + savePath=<绝对路径>
//      逐个下载，文件名按「来源章节 + 序号」命名，便于与正文章节对照。
//
// 注意：
//   - 跨域 iframe 访问 contentDocument 会抛异常 → 已用 try/catch 兜底，
//     这种情况改用「截图 + 逐屏 read_text」的兜底路径。
//   - 遇到 data: 开头的内联图（图标、占位符）直接跳过，不要下载。
//   - 停scroll 条件：返回的 y 已经 >= max，或 count 连续两次不增长。
