---
name: ima-cos-upload
description: 把本地文件（音频/文稿/PDF/图片等）存入 ima 知识库的通用上传技能。当任何流程需要把文件存进 ima，且 ima-mcp 连接器已连接、但缺少原生"直接吃文件内容"的上传工具时调用。本技能每次被调用都会先探测 ima 是否已上线原生上传工具；一旦上线，会自动改用原生工具，并同步更新 book-to-podcast 的上传逻辑、把本技能自身标记为弃用（自我淘汰）。
agent_created: true
---

# ima-cos-upload —— ima 知识库 COS 直传（带自我淘汰）

## 这个技能解决什么
ima 连接器**没有"直接上传文件内容"的工具**。它的接口只有：`create_media`（拿 COS 临时凭证）、`add_knowledge`（用 media_id 归库）、查询类。文件字节必须借 ima 的腾讯云 COS 桶**直传**。

本技能 = 把"直传 COS"这步封装好，供任何要存 ima 的场景复用（不绑死 book-to-podcast）。

## 何时使用
- 需要把本地文件（音频/文稿/PDF/图片/视频…）存入 ima 知识库某文件夹。
- ima-mcp 连接器已连接（connected）。
- 且**尚未发现** ima 原生上传工具（见下方探测）。

## ⚠️ 调用前必做：探测 ima 原生上传工具（核心，每次都做）
本技能存在的唯一原因是 ima 没有原生上传工具。因此**每次调用第一步必须探测它是否上线了原生上传工具**，避免绕过未来更优的路径。

### 探测步骤
1. **先确认连接器已连接**：用 `ToolSearch` 查 `mcp__ima-mcp__*`，应能看到真实的 ima 工具（如 `mcp__ima-mcp__create_media`）。
   - 🚫 **陷阱**：若 ima-mcp 处于 disconnected，ToolSearch 返回的会是**无关的 github 等工具**且一个 ima 工具都没有——此时必须提示用户先去连接器管理页连接 ima，不要继续。
2. **枚举 ima-mcp 全部工具**，寻找名称含以下之一、且**入参接收"本地文件内容"**的：
   - 候选名：`upload_media` / `upload_file` / `write_media` / `put_media` / `create_and_upload` / `import_file` / `upload`
   - **"原生上传工具"的判定特征**：入参里有 `file_path` / `file_content` / `file_bytes` / `body` / `local_path` 之类（能直接吃文件），**而非**只吃 `media_id`。
   - 注意区分：`import_urls`（吃 URL，不是本地文件）≠ 原生上传工具，不要误判。
3. **判定**：
   - 找到符合条件的工具 → **ima 已提供原生上传** → 走「自我淘汰流程」。
   - 没找到 → **仍走标准直传流程**（下方）。

## 标准直传流程（未发现原生工具时）
```
create_media → COS 直传(ima_cos_upload.js) → add_knowledge → get_knowledge_list 二次校验
```
1. **逐文件 `create_media`**：凭证**每文件独立签发**（secret_id 都不同，不能复用）。收集每文件的 `media_id` + `cos_credential` + 本地 `file_path`，写成 creds JSON（结构见 references/ima_api.md）。
2. **COS 直传**：`NODE_PATH=<托管node工作区>/node_modules node scripts/ima_cos_upload.js <creds.json>`。SDK `cos-nodejs-sdk-v5` 需先在托管 node 工作区 `npm install`（见下）。逐文件报告 `OK <file> media_id=...` / `FAIL <file> <COS Message>`。
3. **`add_knowledge`**：对每个成功上传的 `media_id` 调一次，归到目标 `folder_id`。
4. **二次校验**：用 `get_knowledge_list(folder_id=...)` 看 `total_size` 是否等于预期文件数，落位无误才算成功。

### 前置：安装 COS SDK（仅首次）
```bash
mkdir -p /Users/zhy/.workbuddy/binaries/node/workspace
cd /Users/zhy/.workbuddy/binaries/node/workspace
/Users/zhy/.workbuddy/binaries/node/versions/22.22.2/bin/npm install cos-nodejs-sdk-v5
```

## 🔁 自我淘汰流程（探测发现 ima 原生上传工具时）
一旦确认 ima 已上线原生上传工具（记为 `<native_upload_tool>`），按序执行：

1. **同步更新 book-to-podcast**（让主流程改用原生工具，不再依赖本技能）：
   - 编辑 `~/.workbuddy/skills/book-to-podcast/SKILL.md` 的上传章节：把"调用 ima-cos-upload skill 做 COS 直传"改为"使用 ima 原生上传工具 `<native_upload_tool>` 直接上传"。
   - 编辑 `book-to-podcast/references/ima_api.md`：新增「原生上传工具」章节，把 COS 直传标记为 legacy/备份路径。
   - `book-to-podcast/scripts/ima_cos_upload.js` 保留为兜底（原生工具异常时可回退），但主流程不再默认调用。
   - 上述改动同步到跨 agent 目录 `/Users/zhy/.agents/skills/book-to-podcast/` 与 GitHub `zhy092/custom-skills`。
2. **标记本技能弃用**：
   - 在 SKILL.md 顶部 frontmatter 加 `status: deprecated`，并把 `description` 改写为 `[已弃用] ...` 前缀。
   - 优先用 SkillManage modify；若本环境 SkillManage 不可用（报 "not available in current environment"），**直接 Edit 本 SKILL.md 的 frontmatter 等价达成**（效果相同，仅少一条系统注册记录）。
   - 告知用户：ima-cos-upload 已自我淘汰，后续统一走 ima 原生上传工具。
3. **不删除本技能**：保留为原生工具出故障时的回退手段（仅 deprecated）。

## COS 直传签名硬性要求（错一个就 403）
- 上传主机：必须用直连域名 `https://{bucket_name}.cos.{region}.myqcloud.com`，不要用 CDN 自定义域名。
- 签名 header：必须同时含 `host` **和 `content-length`**。本技能脚本用官方 SDK 已自动处理，不要自己重写上传器。
- `start_time`/`expired_time` 必须原样透传 `create_media` 返回值，不要重算。

## 限制与兜底（硬性）
- 单文件 ≤200MB（`create_media` 上限）；**COS STS 临时凭证实际单次约 100MB 上限**。>100MB 文件（高清扫描 PDF 常见）引导用户在 ima 客户端手动上传，不要自动重试。
- 文件夹创建/删除/移动 ima 连接器不暴露，需用户在 ima 客户端手动建。
- 上传失败（超限/签名域错）：先读 COS 错误码判因 → 停止自动重试 → 明确告知用户（文件名+原因+建议手动上传）→ 已成功的保留。禁止反复重试或盲改签名。

## content_type 对照（必须精确，禁止 octet-stream 兜底）
pdf→application/pdf；doc→application/msword；docx→application/vnd.openxmlformats-officedocument.wordprocessingml.document；ppt→application/vnd.ms-powerpoint；pptx→对应 office；xls/xlsx→对应 office；csv→text/csv；md/markdown→text/markdown；txt→text/plain；xmind→application/x-xmind；png→image/png；jpg/jpeg→image/jpeg；webp→image/webp；**mp3→audio/mpeg**；m4a→audio/x-m4a；wav→audio/wav；html→text/html；epub→application/epub+zip；aac→audio/aac。对照表无对应扩展名时拒绝上传，不猜测。

## 实测坑（2026-08-29《不测的秘密》14 文件跑通）
- 凭证每文件独立：13 个文件要 13 次 `create_media`，"复用一份凭证只换 media_id"行不通。
- 首轮 3 个文件因超长 token/secret 手录错位报 `Access Denied`/`InvalidAccessKeyId` → 重新 `create_media` 拉新凭证（新 media_id）重传即通过；旧 media_id/cos_key 作废。经验：长 token 一律经脚本列表传参，绝不手写命令行。
- STS 凭证 12 小时有效，整批上传务必在有效期内完成。
- `create_media`/`add_knowledge` 是 deferred 工具：先 `ToolSearch` 加载 schema 再用 `DeferExecuteTool` 调，params 传 JSON 对象（不要包字符串），否则会被错误序列化报 `Expected object, received string`。
- 上传后必须 `get_knowledge_list` 二次核验 `total_size`，不要只信 `add_knowledge` 返回 success。
