---
name: weread-ima-book-pipeline
description: 从"想拆哪本书"到"播客入库"的完整流水线：微信读书找书/查重/加书架 → ima 知识库建文件夹 → 抓全文 → 双人对话脚本 → 渲染 → 上传归档。当用户说"帮我找书拆播客""把某本书做成播客""批量做拆书电台"，或需要判断某本书能不能做（付费墙）、知识库里是否已做过时使用。
version: 1.0.0
author: zhy
tags: [weread, ima, podcast, pipeline, automation]
category: content
license: MIT
---

# 微信读书 → ima 拆书播客流水线

一条被验证过的链路，六个环节，每个环节都有坑。按顺序走，别跳步。

## 前置条件

| 依赖 | 怎么确认 | 缺了怎么办 |
|---|---|---|
| Chrome 已登录 weread.qq.com | `python3 scripts/wr_session.py` 输出 `OK ...`，再用 `node scripts/wr_cookies_live.js` 刷新一次 | 让用户在 Chrome 扫码登录，再重跑 |
| ima OpenAPI 凭证 | `~/.config/ima/{client_id,api_key}` 存在 | 到 https://ima.qq.com/agent-interface 取，**存文件不放 env** |
| ima 知识库 ID | `ima_openapi.py folders` 有输出 | 用 `search_knowledge_base` 查库名 |
| 渲染环境 | `book-to-podcast` skill 的 venv 可用 | 见该 skill |

## 五个环节

### 1. 找书 + 查重

```bash
python3 scripts/find_books.py "行为经济学" --limit 15
python3 scripts/plan_books.py candidates.txt --json state/candidates.json
```

- 搜索接口免登录就能用：`GET /web/search/global?keyword=`，返回 `books[].bookInfo`（bookId/title/author/newRating/newRatingDetail/publisher）。
- 评分字段 `newRating` 是放大十倍的整数（879 = 87.9 分），`newRatingDetail.title` 是"好评如潮/神作"这种标签。
- **查重必须做**：书名归一化（去《》、标点、空格、全半角 NFKC）后做包含比对，基准三处 = ima 文件夹 + 本地成品目录 + 书架。`norm()` 在 `ima_openapi.py` 里。


### 登录态会「看着有效其实过期」

- `wr_session.py` 从 Chrome 的 cookie 库解密，拿到的 `wr_skey` / `wr_fp` **可能是上一次会话的旧值**：浏览器用着正常，但直接调 API 会返回 `-2012 登录超时`。
- 判断方法：用浏览器 context 打开书架，页内 `fetch('/web/shelf/sync')` 能拿到 `bookCount`，而 Python 调同一接口 401/超时 —— 就是这个问题。
- 解法：跑 `node scripts/wr_cookies_live.js`，它用 Playwright 载入页面后把**运行时真实 cookie** 写回 `/tmp/wr_cookies3.json`，覆盖率 100%。抓取脚本也认这个文件。

### 2. 判断可读性（最容易翻车的一步）

```bash
FLIPS=60 NODE_PATH=<node_modules> node scripts/probe_readable.js <readerHash>
```

- **只看前十几页会误判**。试读墙常在几十页后才出现，必须翻够 60 页并每十页查一次 `试读结束|付费会员卡可读`。
- 输出 `可读` 才能排期；`试读墙` 记进候选表状态，等用户开会员或换书。
- 同一本书常有多个版本（新旧版/不同出版社），**新版被墙不代表旧版也墙**，换版本往往能读。

### 3. 加入书架

```bash
node scripts/shelf_add.js "https://weread.qq.com/web/reader/<hash>"
```

- **不要用 `POST /web/shelf/add`**：它返回 `{"succ":1}` 但书架数量不变，书根本没进去。这是本流水线最大的假信号。
- 正确做法是 Playwright 打开 `readerLink`，点页面上的"加入书架"，再回查 `/web/shelf/sync` 的 `bookCount` 是否 +1。
- `readerLink` 形如 `https://weread.qq.com/web/reader/<hash>`，hash 不是 bookId；`/web/reader/<bookId>` 会 404。

### 4. 建文件夹（不可逆）

```bash
python3 scripts/ima_openapi.py find "《书名》"
python3 scripts/ima_openapi.py create "《书名》"          # 预演
python3 scripts/ima_openapi.py create "《书名》" --apply  # 真建
```

- 端点：`POST https://ima.qq.com/openapi/wiki/v1/create_folder`，header 用 `ima-openapi-clientid` / `ima-openapi-apikey`。
- **凭证优先读 `~/.config/ima/` 两个文件**；环境变量里的 key 可能是旧的，会 401。
- 返回体键名容易踩错：`search_knowledge_base` → `data.info_list`（`kb_id`/`kb_name`）；`get_knowledge_list` → `data.knowledge_list`，条目名字段是 **`title` 不是 `name`**，`media_type == 99` 才是文件夹。
- **没有删除接口**，建错了只能人工去 ima 里删。所以默认预演，`--apply` 才落库，且必须先 `find` 查重。
- 建完把 `书名 → folder_id` 写进 `state/folder_map.json`，这是后续归档的唯一真相源。

### 5. 抓全文 → 切块 → 写稿 → 渲染 → 入库

```bash
node scripts/grab_web.js <hash> "books/<书名>/raw" --max-flips 900
```

- 抓取靠 hook canvas 的 fillText 还原文字，不需要 OCR。
- 正常结束的标志是日志出现"完成：N 屏 / M 字"；如果中途出现"连续无内容"，先怀疑试读墙，别以为到书末。
- 抓完 `cp` 到 `books/<书名>/book_raw.txt`，按计划集数均分切块到 `podcast/<书名>/chunks/`。
- 写稿、渲染、合并、PDF、上传照 `book-to-podcast` skill 走；上传到 `folder_7523659023397328` 这种该书 `folder_id`，不是知识库根。

## 五个反复踩到的坑

1. **渲染卡在最后一步**：片段数齐了但 `render_manifest.json` 没生成，进程不退出。别等超时，kill 掉，查零字节片段（`find audio/epNN -size 0`），补渲染后用 `rebuild_manifest.py . epNN` 反向补清单。
2. **一次性派太多写手**：每本一次派 2–4 集，4 个并发写手比较稳；派 8 集会互相重复实验、抢素材。
3. **写手跨块取材料**：切块按字数均分，章节会被切断。要求写手"按章节标题定位，可在相邻块取材料，但必须汇报实际用了哪几章"，否则会出现两集讲同一个实验。
4. **书名长短不一**：音频里是《产品的视角》，文件夹是《产品的视角：从热闹到门道》，查重必须用包含比对而不是相等。
5. **假空列表**：`get_knowledge_list` 偶发返回空，首屏为空要重试 2–3 次再判定为空，否则会误判文件夹没内容。

## 交付口径

每本书的阶段固定为：`候选 → 已批准 → 已建文件夹 → 抓取中 → 写作中 → 渲染中 → 已入库`。
看板/清单页读 `state/candidates.json` 与 `state/folder_map.json`，别再手写状态。

## 附：文件上传路径（原 ima-cos-upload 技能已并入此处）

把音频/PDF 存进 ima 只有一条推荐路径，不需要 COS SDK、不需要 STS 凭证：

1. `create_media` 传 `apply_upload_mode: 1`，拿到 `upload_url.presigned_url` 与 `auth_headers`（含 Content-Length，必须与 `file_size` 完全一致）；
2. 对 `presigned_url` 发 HTTP PUT，body 是文件二进制，header 原样带上 `auth_headers`；
3. `add_knowledge` 传 `media_id` + `folder_id` 归档；
4. `get_knowledge_list(folder_id=...)` 看 `total_size` 是否等于预期条数，落位才算成功。

- 预签名链接有效期约 12 小时（`url_expired_ts`），过期重新 `create_media`。
- 若哪天不返回 `upload_url`（只给 `cos_credential`），才需要回退到 STS + COS SDK 上传。
- 批量时每 5 个文件一批走完 1→2，再统一 3，往返最少。
