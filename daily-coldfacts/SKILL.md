---
name: daily-coldfacts
description: |
  每日一个为什么 · 冷知识自动化技能。当用户提到"每日一个为什么"、"冷知识"、"生成今天的冷知识"、"每天的为什么"，
  或者自动化任务触发每日冷知识创作时，使用本技能。
  执行完整流程：冷知识选题 → 海报设计 → Playwright截图 → 上传 ima 知识库 → iCloud 本地归档 → 记忆更新。
agent_created: true
---

# 每日一个为什么 · 冷知识自动化

## 核心规则

**ima 知识库：只上传图片，不创建笔记**

ima 知识库只有图片，没有笔记。图片命名必须用问题标题：
- `create_media` → `file_name` = `【问题标题】.png`（例如：`为什么蝙蝠眼睛几乎瞎却能在黑暗中高速飞行不撞墙.png`）
- `add_knowledge` → `title` = `问题标题`（不加 .png）
- **禁止使用** `daily-coldfacts-YYYY-MM-DD.png` 这类通用文件名

ima 凭证读取：`~/.config/ima/client_id` 和 `~/.config/ima/api_key`

**iCloud 本地归档（必须执行，不允许跳过）**

归档路径：`~/Library/Mobile Documents/com~apple~CloudDocs/iMA/notes/冷知识库/每日一个为什么/【问题全文】/`
必须创建两个文件：
1. `问题与答案.txt` — 包含完整问题和答案
2. `知识海报.png` — 海报截图副本

## 完整执行流程

### Step 1：选题（从历史记录中选未做过的主题）

科学、生活、历史、自然、食物、文化、动物、人体等领域均可。
历史选题记录在 `references/history.md`，执行前查阅避免重复。

### Step 2：生成问答内容

问题：一句话悬念式提问，引发好奇心
答案：100字左右，打比方+具体数据，让大人也忍不住想知道

### Step 3：生成海报 HTML

- 风格每天变换（复古科学图鉴/赛博朋克/手绘水彩/极简几何/波普艺术/禅意水墨/深夜暗黑插画风等）
- HTML 标题（`<title>` / 首行标题）用**问题全文**
- 色调呼应主题

### Step 4：Playwright 截图

viewport 800×1200，执行后得到 `daily-coldfacts-YYYY-MM-DD.png`

### Step 5：上传 ima 知识库

上传顺序：`create_media` → COS上传 → `add_knowledge` → `get_media_info`

知识库 ID：`SaPGqniApLW6iL0aN7t4e4y8D8I8FD2OiWHm5YDOmIk=`
文件夹 ID：`folder_7457749126377154`

具体参数：
- `create_media`：file_name = 问题标题+.png，content_type = image/png，file_ext = png
- `add_knowledge`：title = 问题标题（不加.png），media_type = 9，folder_id = folder_7457749126377154

### Step 6：iCloud 本地归档

Python 脚本：
```python
import os, shutil
folder = '/Users/zyb/Library/Mobile Documents/com~apple~CloudDocs/iMA/notes/冷知识库/每日一个为什么/' + question
os.makedirs(folder, exist_ok=True)
with open(os.path.join(folder, '问题与答案.txt'), 'w', encoding='utf-8') as f:
    f.write(content)
shutil.copy2(poster_png_path, os.path.join(folder, '知识海报.png'))
```

### Step 7：更新记忆

写入 `.workbuddy/memory/YYYY-MM-DD.md`：
- 主题、问题、答案摘要
- 海报风格、文件名
- ima media_id、iCloud 归档状态

## 执行完毕检查清单（共 11 项）

- [ ] 冷知识内容已生成（问题+答案，100字左右）
- [ ] 海报HTML已创建（标题=问题全文，非"每日一个为什么"）
- [ ] 海报已截图保存为PNG
- [ ] **【ima知识库】图片文件名已用问题标题**（file_name = 问题+.png）
- [ ] **【ima知识库】add_knowledge title已用问题标题**
- [ ] **【ima知识库】图片已上传成功，获得 media_id**
- [ ] **【iCloud归档】已创建文件夹**
- [ ] **【iCloud归档】已写入 问题与答案.txt**
- [ ] **【iCloud归档】已复制 知识海报.png**
- [ ] 执行记录已写入 .workbuddy/memory/YYYY-MM-DD.md
- [ ] 历史选题已追加到 references/history.md
