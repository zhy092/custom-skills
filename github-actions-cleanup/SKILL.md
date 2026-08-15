---
name: github-actions-cleanup
description: 排查并清理 GitHub 账户的 Actions 存储占用（artifacts 构建产物 + caches 依赖缓存），释放 0.5GB 免费配额。当用户收到 GitHub "Actions storage 已用 X%" 告警、询问"哪个仓库占用了 Actions 空间 / 存储满了 / 清理 Actions 缓存 / 删除 artifacts"，或需要定位某个 GitHub 账户/组织下 Actions 存储的占用来源时使用。
agent_created: true
---

# GitHub Actions 存储清理

## Overview

GitHub 免费账户的 Actions 存储配额仅 **0.5 GB**，包含两类占用：**artifacts（构建产物）** 与 **caches（依赖缓存）**。告警里统称 "Actions storage"，容易误以为是缓存。本技能用于定位占用来源、按风险分级判断是否可删、并在获得用户确认后安全地清理，释放配额。

两类数据都是 CI 的副产品（非源码、可重建），从"释放空间"角度**一般都能删**，但必须按下方「安全判断规则」分级处理，且删除属 destructive 操作，必须向用户列出明细并确认后再执行。

## When To Use（触发条件）

- 用户收到 GitHub 通知 "You've used X% of your Actions storage" 或 "Actions storage 即将用尽"。
- 用户问："GitHub 哪个仓库占用了 Actions 空间 / 存储满了 / 清理 Actions 缓存 / 删除 artifacts"。
- 需要排查某个 GitHub 账户或组织下 Actions 存储（artifacts + caches）的占用来源。
- 用户主动要求清理 GitHub Actions 构建产物或缓存以释放配额。

不处理：源码、Releases、Tags、Packages —— 这些不在 Actions storage 额度内。

## 安全判断规则（核心，务必先判断再删）

GitHub Actions 存储含两类，删除前必须分清：

**1. Artifacts（构建产物）** —— 来自 `upload-artifact` 的 CI 输出（测试报告、打包产物、截图/录屏等）。
- `expired: true`（已过保留期，默认 90 天）：**零风险，直接删**。过期即代表无保留价值。
- `expired: false`（仍在保留期）：**低风险，仍可删**，但删后不可恢复。删除前需确认其中不含团队仍需下载的内容（如手动触发的性能基线、对外分发的包）。注意：**Releases 发布物走 Releases 而非 artifact，删除 artifact 不影响已发布的 release。**

**2. Caches（依赖缓存）** —— 来自 `cache` action，缓存 node_modules / ~/.m2 / pip 等。
- **可删，低风险**：删后下次构建需重新下载依赖，会变慢并可能多耗 Actions minutes，但**不影响构建正确性，也不破坏任何产物**。
- 适合空间紧张、且近期不再频繁构建时清理。

**禁止 / 避免删的：**
- 正在运行的 workflow 当前 step 正在写入的 artifact/cache（API 通常拒绝并返回 409/422，遇到跳过即可，不要当作失败重试）。
- 源码、Releases、Tags、Packages —— 不在本技能范围内。

**默认立场：** Actions storage 全部可重建。可删，但按分级判断，且删除前必须向用户列出明细并获确认。

## Workflow

### 步骤 1：获取 token
macOS 从钥匙串取 GitHub token（仅注入变量，不打印明文）：
```bash
export TOKEN="$(security find-internet-password -s github.com -w)"
```
> 前提：钥匙串存有 github.com 凭据。缺失则会报 401，需让用户提供 token。

### 步骤 2：列出全部仓库（含 private / fork / 协作）
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.github.com/user/repos?per_page=100&affiliation=owner,collaborator,organization_member"
```
用返回的 `full_name`、`private`、`fork` 字段决定要排查的仓库列表。

### 步骤 3：逐仓库统计 caches 与 artifacts
对每个仓库分别请求（累加 `size_in_bytes`）：
```bash
# caches
curl -s -H "Authorization: Bearer $TOKEN" "https://api.github.com/repos/{owner}/{repo}/actions/caches?per_page=100"
# artifacts
curl -s -H "Authorization: Bearer $TOKEN" "https://api.github.com/repos/{owner}/{repo}/actions/artifacts?per_page=100"
```
- `total_count` 为 0 的仓库跳过。
- 有占用的仓库，记录每个 artifact 的 `id`、`name`、`size_in_bytes`、`expired`、`created_at`。
- **定位占用最大的仓库**（通常是某个私有仓库堆积了大体积 CLI/APP 构建包）。

### 步骤 4：按「安全判断规则」评估并列出明细
- 区分 `expired` 与 `active`，给出风险等级。
- 用表格或列表向用户展示：仓库、artifact/cache 名称、大小、是否过期、删除风险。
- 明确告知：已过期 = 零风险可直接删；caches = 低风险（仅下次变慢）；active artifact = 需确认。

### 步骤 5：删除（须用户确认后执行）
删除单个 artifact：
```bash
curl -s -o /dev/null -w "%{http_code}" -X DELETE \
  -H "Authorization: Bearer $TOKEN" \
  "https://api.github.com/repos/{owner}/{repo}/actions/artifacts/{id}"
```
- `204` = 成功；`404` = 已不存在（可忽略）；`409/422` = 正在被使用（跳过）；`401` = token 无效/为空。
> 注意：删除 caches 用 `DELETE /repos/{owner}/{repo}/actions/caches/{cache_id}`（端点类似）。

### 步骤 6：复核
删除后再请求一次 `actions/artifacts` 与 `actions/caches`，确认 `total_count` 归零或降至预期。

## 环境注意 / 踩坑

- **bash 变量不会自动传给 node 子进程**：若在 node 脚本里用 `execSync` 调 curl，必须先 `export TOKEN=...`，node 才能用 `process.env.TOKEN` 读到；否则 curl 带空 token 报 401。直接用 bash 循环调 curl（内联 `$TOKEN`）则无此问题。
- **token 权限**：能读取私有仓库说明带 `repo` scope，删除 artifact/cache 也够用。
- **Billing 仪表盘有延迟**：删除后 GitHub Settings → Billing/Usage 页面**不会立即**刷新用量，通常 5–30 分钟，极端情况几小时。API 层面 `total_count` 已归零即代表删除成功，不必因页面未更新而重复删除。
- 跨平台：脚本依赖 `curl` + `security`（macOS 取 token）；Linux/Windows 需改用对应凭据获取方式（如环境变量 `GITHUB_TOKEN`）。

## 安全确认（硬性）

删除前**必须**向用户展示将要删除的明细（仓库、名称、大小、过期状态、风险），并获得明确确认。不要默认全删；对 active（未过期）artifact 要特别提示"删除不可恢复"。
