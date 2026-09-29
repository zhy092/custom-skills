---
name: ima-api-key-manager
description: "IMA Skills API Key 生命周期管理规范。当 IMA Skills 调用返回错误码 20004（Key 过期）、任何 IMA 操作报鉴权失败、或用户主动告知 Key 已过期时，触发此 Skill，执行标准化的 Key 识别、通知用户、接收新 Key、更新所有配置、验证、记录全流程，确保 ima-skill、腾讯ima:notes、腾讯ima:knowledge-base 等所有 IMA 相关 Skill 恢复正常工作。"
agent_created: true
---

# IMA Skills API Key 管理规范

## 一、Key 基本信息

| 属性 | 说明 |
|------|------|
| 用途 | 调用用户 IMA 账号（笔记、知识库等功能）的密钥 |
| 有效期 | 约 3 个月，到期后必须重新生成 |
| 获取地址 | https://ima.qq.com/agent-interface （登录后点击"获取API Key"）|
| 更新原则 | Key 更新后，**必须同步更新所有配置位置** |

## 二、过期识别条件

满足以下任一条件，判定为 Key 已过期，立即进入更新流程：

- 调用 IMA Skills 接口返回 **错误码 20004**，提示"API Key 过期"
- 任何 IMA Skill 操作（笔记读写、知识库查询等）**报鉴权失败**
- **用户主动告知** Key 已过期

一旦识别到 Key 过期，立即进入更新流程，**不要反复重试旧 Key**。

## 三、Key 更新流程

### 第 1 步：通知用户生成新 Key

向用户发送以下提示：

"你的 IMA Skills API Key 已过期，请前往 https://ima.qq.com/agent-interface 登录后点击'获取API Key'生成新 Key，然后将新 Key 发给我。"

### 第 2 步：接收用户提供的新 Key

等待用户将新 Key 发送过来，然后进入第 3 步。

### 第 3 步：更新所有 Key 配置位置

**必须同时更新以下所有位置**，确保一致性，避免旧 Key 被优先读取导致反复报错：

| 配置位置 | 优先级 | 更新方式 |
|---------|--------|---------|
| 系统环境变量 `IMA_OPENAPI_APIKEY` | **最高（优先读取）** | 写入 shell 配置（`~/.zshrc` 或 `~/.bashrc`） |
| 配置文件 `~/.config/ima/api_key` | 次之 | 直接覆写文件内容为新 Key |
| 其他 Skill/插件配置中的 Key 字段 | — | 如有其他存储该 Key 的位置，一并更新 |

**关键提醒**：环境变量优先级最高！如果只更新配置文件而不更新环境变量，下次调用仍会读到旧 Key，导致反复报 20004 错误。

**具体更新命令（将 YOUR_NEW_KEY 替换为实际 Key）：**

```bash
# 1. 更新当前终端环境变量（立即生效）
export IMA_OPENAPI_APIKEY="YOUR_NEW_KEY"

# 2. 写入 shell 配置文件（持久化）
# 先检查 ~/.zshrc 中是否已有该变量
grep -n "IMA_OPENAPI_APIKEY" ~/.zshrc

# 如果已有，用 sed 替换；如果没有，追加
# 替换已有行：
sed -i '' "s|export IMA_OPENAPI_APIKEY=.*|export IMA_OPENAPI_APIKEY=\"YOUR_NEW_KEY\"|" ~/.zshrc

# 或追加（没有该变量时）：
echo 'export IMA_OPENAPI_APIKEY="YOUR_NEW_KEY"' >> ~/.zshrc

# 3. 更新配置文件
mkdir -p ~/.config/ima
echo "YOUR_NEW_KEY" > ~/.config/ima/api_key
```

### 第 4 步：验证新 Key

更新完成后，执行一次简单的 IMA Skills 调用（如读取笔记列表）验证新 Key 是否生效：

- **调用成功** → 通知用户"Key 已更新并验证通过"
- **调用失败** → 按第五节故障排查清单逐项检查

### 第 5 步：记录更新时间

在工作记忆（`MEMORY.md`）中记录本次 Key 更新日期，格式：

```
IMA API Key 最后更新：YYYY-MM-DD，有效期约至 YYYY-MM-DD（+3个月）
```

## 四、主动提醒机制

在以下场景主动提醒用户检查 Key：

- 距上次 Key 更新已超过 **80 天**（快到期前 10 天提醒）
- 长期未使用 IMA Skills 后**首次调用前**

提醒话术：

"你的 IMA Skills API Key 可能即将过期/已过期，请检查是否需要更新。更新地址：https://ima.qq.com/agent-interface"

## 五、故障排查清单

Key 更新后仍报错时，按以下顺序排查：

- [ ] 环境变量 `IMA_OPENAPI_APIKEY` 是否已更新为新 Key？
  ```bash
  echo $IMA_OPENAPI_APIKEY
  ```
- [ ] 配置文件 `~/.config/ima/api_key` 是否已同步？
  ```bash
  cat ~/.config/ima/api_key
  ```
- [ ] 当前进程/终端是否需要重启才能读取新的环境变量？
  ```bash
  source ~/.zshrc
  ```
- [ ] 新 Key 是否在 IMA 后台显示为"有效"状态？（访问 https://ima.qq.com/agent-interface 确认）
- [ ] 是否有多个环境（如多个终端、多个自动化任务）使用了不同的旧 Key？
