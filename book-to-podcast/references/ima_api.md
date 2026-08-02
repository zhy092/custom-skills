# ima-mcp API 速查（本技能使用的 4 个工具）

> 工具以 MCP 形式暴露（`mcp__ima-mcp__*`），宿主自动鉴权。下方为调用参数与返回要点。

## 1. get_knowledge_base_list —— 列出知识库
入参：
```json
{ "params": [ { "type": "KBT_MINE_KB", "limit": 50, "cursor": "" } ] }
```
返回：各 KB 的 `id`、`basic_info.name`、`user_permission_info.can_add_knowledge`。
目标：`can_add_knowledge == true` 且名称匹配（本机默认「书籍播客」）。

## 2. get_knowledge_list —— 列出文件夹/文件
列出根目录或某文件夹内容；`filter_type=MEDIA_TYPE_FILTER_TYPE` + `media_type=["FOLDER"]` 可只列文件夹。
入参：
```json
{
  "knowledge_base_id": "<KB_ID>",
  "limit": 50,
  "cursor": "",
  "filters": [ { "filter_type": "MEDIA_TYPE_FILTER_TYPE", "media_type_filter": { "media_type": ["FOLDER"] } } ]
}
```
列出某文件夹内文件：加 `"folder_id": "<folder_id>"`，去掉 filters。
返回：每项含 `media_id`/`folder_info.folder_id`、`title`、`media_type`（15=SOUND_RECORDING 录音；99=FOLDER）、`file_size`。

## 3. create_media —— 预占配额，拿 COS 临时凭证
入参：
```json
{
  "knowledge_base_id": "<KB_ID>",
  "file_name": "<含扩展名的原文件名>",
  "file_size": <字节数, 必须与磁盘一致>,
  "content_type": "audio/mpeg",   // 必须精确，见下方 MIME 表
  "file_ext": "mp3"
}
```
返回：`media_id`（下一步提交用）+ `cos_credential`。

### cos_credential 字段 → cos-upload.cjs 参数映射
| cos_credential 字段 | cos-upload.cjs 参数 |
|---|---|
| `secret_id` | `--secret-id` |
| `secret_key` | `--secret-key` |
| `token` | `--token` |
| `bucket_name` | `--bucket` |
| `region` | `--region` |
| `cos_key` | `--cos-key` |
| `start_time` | `--start-time` |
| `expired_time` | `--expired-time` |

> `start_time`/`expired_time` **必须原样透传**，不要重新计算，否则签名过期报 403。

## 4. add_knowledge —— 提交入库
入参：
```json
{
  "knowledge_base_id": "<KB_ID>",
  "media_id": "<create_media 返回的 media_id>",
  "folder_id": "<目标 folder_id>",
  "duplicate_name_strategy": "DUPLICATE_NAME_STRATEGY_SAVE"
}
```
- 无 `title` 参数：ima 以 `file_name` 作为标题，故**保持原文件名**即可（拆书播客已是 `ep{NN}_{章节范围}_{主题}.mp3`）。
- 重名策略：`SAVE` 保留 / `REPLACE` 覆盖 / `CANCEL` 取消。

## content_type 对照表（必须精确）
pdf→application/pdf；doc→application/msword；docx→application/vnd.openxmlformats-officedocument.wordprocessingml.document；ppt/pptx→对应 office 类型；xls/xlsx→对应 office 类型；csv→text/csv；md/markdown→text/markdown；txt→text/plain；xmind→application/x-xmind；png→image/png；jpg/jpeg→image/jpeg；webp→image/webp；**mp3→audio/mpeg**；m4a→audio/x-m4a；wav→audio/wav；html→text/html；epub→application/epub+zip；aac→audio/aac。
对照表中找不到扩展名时应拒绝上传，不要猜测。

## 限制（连接器未暴露的接口）
- ❌ 创建文件夹 / 删除 / 移动 / 重命名 —— 文件夹需用户在 ima 客户端手动建。
- ❌ 上传后不可再整理（不可逆）。
- ✅ `create_media` 入参上限：单文件 ≤200MB、≤2 小时。
- ⚠️ **COS STS 临时凭证实际单次上传上限约 100MB**（经验：39MB PDF 成功，191MB PDF 被 `AccessDenied` 拒绝；凭证有效、签名正确，纯因文件超上限）。**自动上传安全阈值 <100MB**；超限文件（高清扫描 PDF 常 150–200MB）请引导用户在 ima 客户端手动上传，不要自动重试。

## COS 直传签名硬性要求（错一个就 403）
- **上传主机**：必须用直连域名 `https://{bucket_name}.cos.{region}.myqcloud.com`，**不要用** `custom_domain`（CDN 域名）。
- **签名 header 列表**：必须同时包含 `host` **和 `content-length`**（`q-header-list=host;content-length`）。只签 `host` 会被 COS 拒。
- 本技能 `scripts/ima/cos-upload.cjs` 已按上述实现，**直接用它**传字节，不要自己重写上传器。
- `start_time`/`expired_time` 必须原样透传 `create_media` 返回值，不要重新计算。

## 上传失败兜底（硬性）
超限 / 签名域错导致上传失败时：先读取 COS 返回的错误码判定原因 → 停止自动重试 → 明确告知用户（文件名 + 原因 + 建议手动上传到「书籍播客 / 书名」文件夹）→ 已成功入库的保留。禁止反复重试或盲目改签名"碰运气"。
