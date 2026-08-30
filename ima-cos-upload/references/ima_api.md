# ima-mcp API 速查（COS 直传用）

> 工具以 MCP 形式暴露（`mcp__ima-mcp__*`），宿主自动鉴权。下方为调用参数与返回要点。

## 1. create_media —— 预占配额，拿 COS 临时凭证
入参：
```json
{
  "knowledge_base_id": "<KB_ID>",
  "file_name": "<含扩展名的原文件名>",
  "file_size": <字节数, 必须与磁盘一致>,
  "content_type": "audio/mpeg",
  "file_ext": "mp3"
}
```
返回：`media_id`（下一步提交用）+ `cos_credential`。
> ⚠️ **deferred 工具**：先 `ToolSearch` 加载 schema → 再用 `DeferExecuteTool` 调用，`params` 传 JSON 对象（不要包成字符串），否则报 `Expected object, received string`。

### cos_credential 字段 → ima_cos_upload.js 映射
| cos_credential 字段 | ima_cos_upload.js 对应 |
|---|---|
| `secret_id` | `COS({SecretId})` |
| `secret_key` | `COS({SecretKey})` |
| `token` | `COS({XCosSecurityToken})` |
| `bucket_name` | `putObject({Bucket})` |
| `region` | `putObject({Region})` |
| `cos_key` | `putObject({Key})` |
| `start_time` / `expired_time` | 原样透传，不要重算 |

## 2. add_knowledge —— 提交入库
入参：
```json
{
  "knowledge_base_id": "<KB_ID>",
  "media_id": "<create_media 返回的 media_id>",
  "folder_id": "<目标 folder_id>",
  "duplicate_name_strategy": "DUPLICATE_NAME_STRATEGY_SAVE"
}
```
- 无 `title` 参数：ima 以 `file_name` 作标题，保持原文件名即可。

## 3. get_knowledge_list —— 列文件夹/文件 + 二次校验
列某文件夹内文件：加 `"folder_id": "<folder_id>"`，去 filters。返回每项含 `media_id`/`title`/`media_type`/`file_size`。
**上传后必须查此接口看 `total_size` 是否等于预期文件数**，确认落位。

## creds JSON 结构（传给 scripts/ima_cos_upload.js）
```json
{
  "items": [
    {
      "media_id": "soundrecording_9cb4..._4f61156ae355...",
      "file_name": "ep01_xxx.mp3",
      "file_path": "/abs/path/output/ep01_xxx.mp3",
      "content_type": "audio/mpeg",
      "cos_credential": {
        "secret_id": "AKID...", "secret_key": "...", "token": ".....",
        "bucket_name": "ima-share-kb-1258344701", "region": "ap-shanghai",
        "cos_key": "data/.../xxx.mp3", "start_time": 1756..., "expired_time": 1756...
      }
    }
  ]
}
```

## 限制
- ❌ 创建文件夹 / 删除 / 移动 / 重命名 —— 文件夹需用户在 ima 客户端手动建；上传后不可逆。
- ✅ `create_media` 单文件 ≤200MB、≤2 小时；**COS STS 实际约 100MB 上限** → 自动上传安全阈值 <100MB，超限引导手动上传。
- 🔁 **原生上传工具探测**：本技能每次调用先探测 ima-mcp 是否上线 `upload_media`/`write_media`/`put_media`/`upload_file`/`import_file` 等"直接吃文件内容"的工具；一旦上线即触发 SKILL.md 的「自我淘汰流程」。
