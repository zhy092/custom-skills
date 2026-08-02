---
name: github-skill-store
description: 把 WorkBuddy 技能（目录）存入用户的 GitHub 仓库 zhy092/custom-skills。当用户说"把技能存到 GitHub""新增技能到我的仓库""push 技能到 github""归档这个技能"时使用。技能本身可由本机 ~/.workbuddy/skills/<name>/ 提供，也可从其他路径传入。
version: 1.1.0
author: zhy
tags: [github, skill-distribution, version-control]
category: devops
license: MIT
---

# github-skill-store —— 把技能存进 GitHub（跨平台版）

用户决定：技能不再传官方市场，**统一存放在 GitHub 公开仓库 `zhy092/custom-skills`**。
每个技能一个子目录，仓库根有 `README.md` 作索引。

> 仓库地址：https://github.com/zhy092/custom-skills

---

## ⚠️ 前置条件、能力边界与已知坑

### 运行环境能力矩阵

| 能力 | macOS（当前） | Windows | Linux / 鸿蒙 |
|------|-------------|---------|-------------|
| 取 GitHub Token | ✅ 钥串 `security` | ❌ 无钥匙串 | ❌ 无钥匙串 |
| 取 Token 备选 | 环境变量 `GITHUB_TOKEN` | ✅ 环境变量 / `gh auth token` / `git credential-manager` | ✅ 环境变量 / `gh auth token` / `~/.git-credentials` |
| `git` 命令 | ✅ 已安装 | ✅ Git for Windows / Git Bash | ✅ 通常已装 |
| `tar` 排除语法 | ✅ BSD tar | ⚠️ Git Bash 的 tar 行为略有不同 | ✅ GNU tar |
| `security` 命令 | ✅ macOS 原生 | ❌ 不存在 | ❌ 不存在 |
| `gh` CLI | ⚠️ 未安装（可选） | ⚠️ 可选 | ⚠️ 可选 |

### 开工前自检清单（5 项）

| # | 检查项 | 正常 ✅ | 缺失 ❌ | 注意 ⚠️ |
|---|--------|--------|--------|---------|
| 1 | `git --version` | ≥ 2.x | 安装 Git | Windows: `choco install git` 或 Git for Windows |
| 2 | Token 可获取 | 见下方「取 Token」各平台方法 | 必须有其一 | Token 需 `repo` 权限 |
| 3 | 网络可达 `github.com` | `ping github.com` 通 | 检查代理/VPN | 中国大陆需代理 |
| 4 | 目标技能目录存在 | `ls <skill_dir>/SKILL.md` 成功 | 路径错误 | 确认技能名 |
| 5 | 仓库可访问 | `curl -s -o /dev/null -w "%{http_code}" https://api.github.com/repos/zhy092/custom-skills` → 200 | 404 说明仓还不存在 | 首次需建仓 |

### Top 10 坑对照表

| # | 坑 | 症状 | 正确做法 |
|---|---|------|---------|
| 1 | **macOS 钥匙串命令在 Windows/Linux 上不存在** | `command not found: security` | 用环境变量或 `gh auth token`（见下方取 Token 各平台方法） |
| 2 | **Token 过期或权限不足** | `401 Bad credentials` 或 `403 Resource not accessible` | 重新生成 Personal Access Token (PAT)，确保有 `repo` scope |
| 3 | **硬编码了仓库所有者 `zhy092`** | 别人的技能推到了你的仓库下 | 把 `REPO_OWNER` 抽成变量，按实际用户名替换 |
| 4 | **推送后 `/tmp` 残留含 token 的 `.git/config`** | 安全隐患 | 推送完必须 `rm -rf /tmp/custom-skills`；用 `credential.helper=""` 覆盖 |
| 5 | **`tar --exclude` 在 Windows Git Bash 下行为不一致** | 排除规则不生效，venv 被打包进去 | Windows 上改用 `robocopy /XD .venv __pycache__` 或 PowerShell `Copy-Item -Exclude` |
| 6 | **网络不通（尤其中国大陆）** | `git clone` / `curl` 超时 | 设置 `https_proxy` 或 `GIT_PROXY_COMMAND`；提示用户检查代理 |
| 7 | **忘记同步到 `.agents/skills/`** | 只更新了 `~/.workbuddy/skills/`，其他 agent 加载的是旧版 | 每次更新后必须同步两处（见下方「三路同步」） |
| 8 | **忘记推 GitHub** | 本地更新了但 GitHub 仓库还是旧的 | 用户认可沉淀后，必须走一遍本技能的 push 流程 |
| 9 | **仓库 `.gitignore` 缺失或不全** | venv/pyc/.DS_Store 被提交上去 | 首次建仓时补 `.gitignore`（见下方模板） |
| 10 | **commit 时没设 user.name/email** | git 报 `Please tell me who you are` | 用 `-c user.name=` `-c user.email=` 内联指定，不改全局配置 |

### 输出规范

- 仓库结构固定为：
  ```
  custom-skills/
  ├── README.md              # 索引（每个技能一行）
  ├── .gitignore             # 排除规则
  └── <skill-name>/
      ├── SKILL.md           # 技能文档
      ├── scripts/           # 脚本（如有）
      ├── references/        # 参考文档（如有）
      └── assets/            # 资源文件（如有）
  ```
- **禁止提交**：`.venv/`、`__pycache__/`、`*.pyc`、`.DS_Store`、`*.skill`、`*.zip`、token 文件、任何密钥。

---

## 流程（分步骤，带跨平台适配）

### 0. 取 Token（按平台选择方法，仅注入变量，绝不打印）

```bash
# ====== 方法 A：macOS 钥匙串（本机默认） ======
TOKEN=$(security find-internet-password -s github.com -w 2>/dev/null)

# ====== 方法 B：环境变量（通用，所有平台首选备选） ======
# 用户提前 export GITHUB_TOKEN=ghp_xxxx
TOKEN="${GITHUB_TOKEN:-}"

# ====== 方法 C：gh CLI（需预先 gh auth login） ======
if command -v gh &>/dev/null; then
  TOKEN=$(gh auth token 2>/dev/null)
fi

# ====== 方法 D：~/.git-credentials（Linux 常用） ======
# 格式：https://<user>:<token>@github.com
if [ -z "$TOKEN" ] && [ -f ~/.git-credentials ]; then
  TOKEN=$(grep -oP 'github.com:\K[^@]+' ~/.git-credentials | head -1)
fi

# ====== 校验 ======
[ -z "$TOKEN" ] && { echo "NO_TOKEN: 无法获取 GitHub Token"; exit 1; }
```

> **新人注意**：优先级 A > B > C > D。macOS 本机走 A 即可；其他系统至少要有 B 或 C 其中之一。
> **Windows 用户**：推荐在 PowerShell 里 `$env:GITHUB_TOKEN="ghp_..."` 再执行脚本。

### 1. 确保仓库存在（不存在才建）

```bash
REPO_OWNER="zhy092"          # ⚠️ 其他用户请改成自己的 GitHub 用户名
REPO_NAME="custom-skills"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME")

if [ "$HTTP_CODE" = "404" ]; then
  echo "仓库不存在，正在创建..."
  curl -s -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$REPO_NAME\",\"description\":\"WorkBuddy 自定义技能仓库\",\"auto_init\":true,\"private\":false}" \
    "https://api.github.com/user/repos"
  # 期望返回 201
fi
```

> **坑**：如果 MCP 连接器有 `create_repository` 工具且权限够，也可以用它；但已知 GitHub MCP 连接器报 403，所以用 `curl` 更可靠。

### 2. 克隆到临时目录

```bash
# macOS / Linux
TMP_DIR="/tmp/custom-skills"
rm -rf "$TMP_DIR"
git clone "https://$TOKEN@github.com/$REPO_OWNER/$REPO_NAME.git" "$TMP_DIR"

# Windows（Git Bash 或 CMD）
# set TMP_DIR=%TEMP%\custom-skills
# rmdir /s /q "%TMP_DIR%"
# git clone "https://%GITHUB_TOKEN%@github.com/%REPO_OWNER%/%REPO_NAME.git" "%TMP_DIR%"
```

### 3. 放入技能（排除环境/缓存文件）

```bash
SRC=~/.workbuddy/skills/<name>   # 或用户传入的任意路径
DST="$TMP_DIR/<name>"
mkdir -p "$DST"

# ====== macOS / Linux（tar 方式） ======
(cd "$SRC" && tar --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.DS_Store' --exclude='*.skill' --exclude='*.zip' -cf - .) | (cd "$DST" && tar xf -)

# ====== Windows（PowerShell 方式，tar 不稳定时用） ======
# Copy-Item -Path "$SRC\*" -Destination "$DST\" -Recurse -Exclude '.venv','__pycache__','*.pyc','.DS_Store','*.skill','*.zip'
```

> **验证**：放入后跑一下 `find "$DST" -name '.venv' -o -name '__pycache__'`（Linux/macOS）或 `dir /s /b "$DST\.venv"`（Windows），确认没有漏网之鱼。

### 4. 更新根 README 索引 + 确保 .gitignore

```bash
cd "$TMP_DIR"

# .gitignore（如果缺失则创建）
cat > .gitignore << 'EOF'
# Python
**/.venv/
**/__pycache__/
*.pyc

# macOS
.DS_Store

# 技能产物
*.skill
*.zip

# 密钥/凭证
*.pem
*.key
.env
*token*
EOF

# README 追加新技能条目（如果还没有的话）
if ! grep -q "<name>" README.md; then
  cat >> README.md << 'EOF'

## <name>
> 一句话描述该技能的功能
- [查看](./<name>/)
EOF
fi
```

### 5. 提交并推送

```bash
cd "$TMP_DIR"
git add -A

# 检查是否有变更（避免空 commit）
if git diff --cached --quiet; then
  echo "无变更，跳过提交"
else
  git -c user.name="$REPO_OWNER" -c user.email="$REPO_OWNER@users.noreply.github.com" \
    commit -m "feat: add <name> skill"
  # credential.helper="" 防止 token 写入 ~/.git-credentials 全局存储
  git -c credential.helper="" push "https://$TOKEN@github.com/$REPO_OWNER/$REPO_NAME.git" main
fi
```

### 6. 清理 + 校验

```bash
rm -rf "$TMP_DIR"
# 校验：确认远程已有该目录
curl -s "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/contents/<name>" | grep -o '"name":"SKILL.md"' && echo "✅ 推送成功" || echo "❌ 推送可能失败"
```

---

## 三路同步规则（重要！每次更新技能都必须执行）

当你在任何一个位置修改了技能内容，**必须同步其余两个位置**：

```
┌─────────────────────────┐
│  ① ~/.workbuddy/skills/ │ ← WorkBuddy 全局（你写/改的地方）
├─────────────────────────┤
│  ② ~/.agents/skills/    │ ← 跨 agent 共享（Trae 等其他 agent 读的地方）
├─────────────────────────┤
│  ③ GitHub (remote)      │ ← 远程备份 / 分享给别人（用户认可后才推）
└─────────────────────────┘
```

**同步顺序**（修改后的标准动作）：
1. 在 ① 完成修改（代码修复 / 文档增强 / 新增文件）
2. **立即同步到 ②**：`cp -r ①/<name> ②/<name>`（排除 `.venv` 等）
3. 用户认可质量后 → **推送到 ③**：走本技能的流程 0→6

**绝对不能只改一处就结束**——否则其他 agent 加载的是旧版，GitHub 上也是旧版。

## 安全底线
- token 只存在于 shell 变量 `$TOKEN`，**禁止 echo / 写入文件 / 出现在回复里**。
- 推送用 `https://$TOKEN@...` 内联，推送后删除临时目录，避免 token 残留在磁盘。
- 仓库为**公开**，注意不要塞入密钥/个人数据（venv、token 文件等已排除）。
- **绝不在 commit message / README 中包含 token 或密码**。

## 新增 vs 更新
- **新增技能**：建 `<name>/` 目录 + 更新 README 索引 + commit message 用 `feat:`。
- **更新已有技能**：直接覆盖 `<name>/` 下文件 + commit message 用 `update: <name>: ...`（简述改了什么）。
