---
name: book-to-podcast
description: 一体化技能：把任意格式书籍（PDF/EPUB/MOBI/TXT/DOCX/HTML…）拆解成结构化知识要点，并自动生成多集双人对话播客音频（MP3）、文稿与 RSS 订阅源，还可一键存入 ima 知识库「书籍播客」按书名归档。当用户说"拆书""解读这本书""把这本书做成播客/音频/有声节目""生成读书笔记音频""book to podcast""听书稿"，或提供书籍文件希望转成可收听内容，或想把生成的播客音频"上传到 ima 知识库/存进 ima"时，应使用本技能。支持 edge-tts（免费）、阿里云百炼 Qwen-TTS、火山引擎豆包、MiniMax、OpenAI 等多种语音引擎。
version: 1.0.0
author: zhy
tags: [拆书, 播客, 音频, 知识库, ima, book-to-podcast, RSS]
category: media
license: MIT
agent_created: true
---

# Book to Podcast（一体化拆书播客技能）

把一本书变成一档**带章节命名**的可收听拆书电台，并（按需）存入 ima 知识库。

本技能是**单包一体化**的，包含三块能力，安装一次即可全部使用：

1. **拆解 + 合成**：解析 → 切块 → 精读 → 分集 → 写对话脚本 → 语音合成 → 拼接 → 生成 RSS。
2. **总控编排**：`scripts/pipeline.py` 把确定性本地步骤（抽取/切块/合成/重命名/RSS）一键串起来。
3. **ima 入库**：把成品音频按章节顺序上传到 ima 知识库指定文件夹（自带零依赖 `cos-upload.cjs` + MCP 工具流程）。

**分工原则**：脚本负责确定性 I/O（解析、切块、语音合成、音频拼接、上传），
模型负责智力工作（知识提炼、分集编排、口语化脚本写作）。不要试图让脚本"理解"书，
也不要手写代码去做解析和合成——脚本已处理好编码、章节识别、断点续渲、多引擎适配这些坑。

---

## ⚠️ 前置条件、能力边界与已知坑（所有 agent 开工前必读）

> **本节基于真实踩坑记录编写。** 以下状况均在 2026-08-01~02 的实际运行中复现过，
> 不是理论推测。**开工前先逐条核对环境，缺一项就注定卡住。**

### 你是谁？你能做到什么程度？

| 运行环境 | 能力范围 | 必须具备的前提 |
|---|---|---|
| **WorkBuddy（本机）** | ✅ 全流程：解析 → 切块 → 精读 → 分集 → 脚本 → TTS → 拼接 → 重命名 → RSS → ima 入库 | `.venv` 已建、`ima-mcp` 连接器已连、可调用并行子代理 |
| **其他 agent（Trae/Claude/通用）** | ⚠️ **有限可用**：①②③⑤（解析/切块/分集编排/写脚本）+ 调用脚本做⑥⑦（TTS/拼接/RSS） | 能执行 bash / Python、有 `.venv` 或系统 ffmpeg + edge-tts |
| **无运行环境的纯文本 agent** | ❌ 只能做④⑤（读 chunk 写笔记/编 episodes/写 script.json） | 能读写文件即可 |

**关键结论：阶段 8（ima 入库）只有 WorkBuddy + ima-mcp 连接器能完成。**
其他 agent 做到阶段 7（产出本地 mp3 + podcast.xml）就是终点。

### 开工前自检清单（逐项打勾）

- [ ] **Python venv 就位**：`<技能目录>/.venv/bin/python` 存在且能跑。
  - ❌ 缺失 → 执行 `bash <技能目录>/scripts/setup_env.sh`（只需一次）。
  - ⚠️ **不要用系统 Python**——核心依赖（`pypdf`、`edge-tts`、`rich` 等）装在 venv 里。
  - 🐛 **真实坑**：有 agent 尝试用系统 Python 跑脚本 → `ModuleNotFoundError` → 然后自己手写解析代码 → 编码/章节识别全崩。
- [ ] **ffmpeg 可用**：`.venv` 内的 `imageio-ffmpeg` 静态二进制已装（`setup_env.sh` 默认安装）。
  - ❌ 缺失 → 音频没有停顿、没有 ID3 标签、没有章节标记、响度不标准化。
  - ⚠️ **不要尝试装系统 ffmpeg 或编译 tesseract**——tesseract 在 macOS 上编译极慢（实测卡在 dependency-download 阶段超过 30 分钟），且对中文扫描 PDF 效果差。
  - 🐛 **真实坑**：某 agent 先尝试编译 tesseract → 卡死 → 被迫跳过；ffmpeg 显示❌没装好 → 后来才发现 `imageio-ffmpeg` 其实已经可用，只是检测逻辑有问题。
- [ ] **TTS 引擎确认**：
  - 默认 `edge-tts`（免费、无需 API Key、已随 venv 安装）→ **直接能用，不要换引擎**。
  - ⚠️ 若用户要求付费引擎（阿里云/火山/OpenAI）→ 必须先确认对应 `API_KEY`/`ACCESS_TOKEN` 环境变量存在，否则 401/403。
  - 🐛 **真实坑**：有 agent 默认去调 Azure/阿里云 TTS → 没 Key → 403 → 浪费大量时间排查。
- [ ] **PDF 类型判定**（仅 PDF 书籍需要）：
  - 先跑 `extract_book.py`，看 `book.txt` 是否有有效文字。
  - ✅ 有文字层 → 正常流程。
  - ❌ 只有水印/乱码（常见于 FreePic2Pdf 生成的 PDF、扫描版、图片型 PDF）→ **立即切到视觉提取分支**：
    1. `pdftoppm -r 200` 渲染全部页面为 PNG（529 页 ≈ 103MB，磁盘空间要够）
    2. 用**并行子代理**分批读图（每批 30~50 页），每页输出结构化笔记
    3. **绝对不要**尝试 tesseract OCR（效果差、编译慢）或手写正则提取（抽不到东西）
  - 🐛 **真实坑**：《世界上最简单的会计书》PDF 无文字层 → agent 花了大量时间在 tesseract 编译和重试上，最终还是要走视觉子代理；另一本书 529 页渲染出 103MB 图片 + 18 个 AI 智能体分波读取才完成。
- [ ] **ima 入库前提**（仅当用户要求存入 ima 时）：
  - ✅ `ima-mcp` 连接器已连接且 `can_add_knowledge==true`
  - ✅ 用户已在 ima 客户端/网页**手动创建好书名文件夹**（ima 无 API 建文件夹）
  - ⚠️ **上传不可逆**——不能移动/删除/重命名，确认文件名正确再传
  - ❌ 其他 agent 没有 ima-mcp → 这步**无法完成**，告知用户改用手动上传或回 WorkBuddy 做

### 其他 agent 最容易踩的 Top 7 坑

| # | 坪 | 症状 | 正确做法 |
|---|---|---|---|
| 1 | **不用 venv / 用系统 Python** | `ModuleNotFoundError`，然后手写代码重造轮子 | 始终用 `<技能目录>/.venv/bin/python` |
| 2 | **坏文字层 PDF 死磕 OCR** | tesseract 编译卡死 / 抽出乱码 / 反复重试 | 直接走视觉子代理读图分支 |
| 3 | **ffmpeg 装错位置** | `ffmpeg: command not found`，音频无停顿 | 用 venv 内的 `imageio-ffmpeg`，不装系统版 |
| 4 | **TTS 引擎选了付费但没 Key** | 401/403，反复查配置 | 默认 edge-tts，除非用户明确给 Key |
| 5 | **丢掉命名规范** | 产出 `ep01.mp3` 而非 `ep01_第1-2章_主题.mp3` | 严格套用 `rename_by_chapter.py` |
| 6 | **忘生成 RSS / shownotes** | 只有 mp3，没有 `podcast.xml` 和 `.md` 文稿 | `make_feed.py` + `shownotes_template.md` |
| 7 | **试图 API 建 ima 文件夹** | 接口不存在 / 404 | 让用户手动建，你只负责按 folder_id 上传 |

### 写脚本与跑流程时还会踩的隐性坑（基于代码实测）

**A. 脚本 JSON（阶段 5，render 失败的第一大元凶）**
- **`episode_id` 必须以 `epNN` 开头、且脚本文件必须叫 `ep01.script.json`**：`rename_by_chapter.py` 用正则 `ep\d+` 匹配文件名来重命名。若写 `"episode_id":"第1集"` 或文件叫 `ch1.script.json`，render 出的 `output/ep01.mp3` 不会被重命名，章节命名规范直接失效。
- **`voices` 的键必须和每行 `lines[].speaker` 完全一致**：写 `"speaker":"host"` 但 voices 里只定义了 `"narrator"` → 直接报 `speaker 未在 voices 中定义`。
- **edge 音色必须用真实 ShortName**（如 `zh-CN-XiaoxiaoNeural`）：瞎猜名字 edge_tts 会报错。开渲前先跑 `tts_render.py --list-voices --engine edge --lang zh` 取真实列表。
- **数字/符号写成朗读形态**：`5美元` 别写 `5`；`clean_for_tts` 会自动剥掉 Markdown 记号和 `(笑)(停顿)` 等舞台提示——脚本里别依赖它们被念出来。
- **每集先单独渲 ep01 试听**，确认音色/语速再批量跑（脚本自带断点续渲，重跑复用缓存）。

**B. 合成与拼接（阶段 6）**
- **混用非 MP3 引擎又没 ffmpeg 会直接崩**：`say` 产 AIFF、`aliyun` 可能产 WAV，纯 Python 兜底拼接只认 MP3。用这些引擎务必保证 ffmpeg 在（venv 内的 imageio-ffmpeg 即可）。
- **`merge_audio.py` 的停顿/响度/BGM/章节标记全部依赖 ffmpeg**：ffmpeg 缺失时只有"能出声"，没有任何精细控制。

**C. 流程顺序（阶段 4→5→6.5→7）**
- 顺序不可乱：**先写 `episodes.json`（含 id/chapter_range/topic）→ 写 `scripts/epNN.script.json` → render → `rename_by_chapter.py` → `make_feed.py`**。`rename_by_chapter.py` 必须能读到 `episodes.json`，否则跳过/保持原名。
- **`make_feed.py` 必传 `--title`、建议传 `--base-url`**：不传 base-url 时 RSS 的 enclosure 是相对路径，外部播客客户端无法订阅（脚本会打印提示）。要真订阅需挂 HTTP 服务。

**D. 扫描版 PDF 视觉提取（坏文字层时）**
- **必须装 poppler**（`pdftoppm`）：macOS `brew install poppler`、Linux `sudo apt install poppler-utils`。`setup_env.sh` 会检测并提醒，但**不会自动装**——这一步要你手动来。
- **磁盘要够**：529 页渲染成图约 100MB+；并行子代理建议每批 30~50 页。**没有并行子代理能力的 agent 做不了这步**——直接判定"本环境无法处理扫描版 PDF"。
- **绝不做 tesseract OCR**：编译极慢且中文效果差。抽不到文字时脚本会明确提示走视觉分支（不再误导去装 ocrmypdf）。

**E. 加密 PDF**
- 标准加密 PDF（含"无密码加密"）pypdf 可直接解密；**真密码保护的 PDF 需要你提供无密码版本**，本技能不存储密码。

**F. 网络与连接器**
- `edge` 引擎走微软在线端点，**离线/强沙箱环境会失败**；付费引擎同理需要出网。断网环境只能用 `say`（macOS 离线，但音质一般且产 AIFF，需 ffmpeg 合并）。
- ima 上传需要 Node + `ima-mcp` 连接器；非 WorkBuddy 的 agent 没有连接器，阶段 8 无法完成。

### 输出命名规范（硬性规则，不可省略）

```
ep{NN}_{章节范围}_{主题}.mp3          # 成品音频
ep{NN}_{章节范围}_{主题}.md            # 单集文稿（与音频同名）
```

示例：
- `ep01_学前测验+第1章_会计基本等式与资产负债表.mp3`
- `ep02_第2-3章_毛利与留存收益.mp3`
- `ep06_第9-10章_税金与最后分析.mp3`

- 章节范围 = 书的真实章节名（如 `第2-3章`、`第4章`、`学前测验+第1章`）
- 主题 = 该集核心内容短语（从 `episodes.json` 的 `topic` 字段取）
- **RSS `<title>` 和 ima 上传的 `file_name` 都用这个格式**

---

## 环境准备（首次使用执行一次）

```bash
bash <技能目录>/scripts/setup_env.sh          # 建 .venv + 装核心依赖（含静态 ffmpeg）
```

**只需执行一次**：ffmpeg（经 `imageio-ffmpeg` 装的静态二进制）会一并装进 `.venv`，
之后每次合成都复用，**无需重装**。`--with-ffmpeg` 参数现已保留为兼容占位，可省略。

**后续所有 Python 脚本都用 `<技能目录>/.venv/bin/python` 执行**（下文用 `$PY` 代指，
`$S` 代指 `<技能目录>/scripts`）。

可选增强：
- `ffmpeg` —— **默认已装**（`imageio-ffmpeg` 静态二进制，跨平台、不污染系统；
  `merge_audio.py` 自动采用）。缺失时仍能出音频，但会失去停顿控制、响度标准化、BGM、ID3 标签、章节标记。
- `cryptography` —— 已纳入核心依赖，用于解密 AES 加密 PDF。
- `calibre` —— 仅解析 `.mobi/.azw3/.fb2` 时需要（`ebook-convert` 先转 epub）。

---

## 开工默认值（无需打断用户）

若用户未说明，直接按默认值开工：

| 项 | 默认 |
|---|---|
| 输出语言 | 中文（不论原书语言） |
| 形式 | 双人对话（主持人 + 嘉宾） |
| 引擎 | `edge`（免费，无需 Key） |
| 命名 | `ep{NN}_{章节范围}_{主题}.mp3`（如 `ep01_学前测验+第1章_会计基本等式与资产负债表.mp3`） |
| 集数 | 按书的字数自动决定 |
| 单集时长 | 18–22 分钟 |

只有一种情况必须先问：**用户想用付费引擎但环境里没有对应 API Key**。

---

## 支持的文档格式

`extract_book.py` 原生支持：

| 类别 | 格式 |
|---|---|
| 直接支持 | `.pdf`（文本层正常）、`.epub`、`.txt`、`.md`、`.markdown`、`.rtf`、`.docx`、`.html`、`.htm`、`.xhtml` |
| 需 calibre | `.mobi`、`.azw`、`.azw3`、`.fb2`、`.lit`、`.pdb`、`.djvu`（先 `ebook-convert in out.epub` 再抽） |
| 例外 | **扫描版/图片型 PDF**（文字层损坏，pypdf 抽不到字）→ 需 OCR 或视觉提取；**PPT/PPTX 不支持**（仅 DOCX） |

判定方法：看扩展名即可。若 PDF 抽取后 `book.txt` 几乎无有效文字（只有水印/乱码），立即切到
「扫描版」分支：渲染页面图（`pdftoppm -r 200`）+ 视觉子代理读图 → 写 `notes/`。详见
`references/extraction_playbook.md` 与 `references/decisions.md`。

---

## 完整工作流（阶段 1–8）

建议用任务列表跟踪，长书全流程耗时较长。`pipeline.py` 负责①+②+③与⑥，④⑤（需要 LLM）由你做。

### 阶段 1 · 解析

```bash
$PY $S/extract_book.py <书籍路径> --out <工作目录>
```

产出 `book.txt` + `structure.json`（标题、作者、语言、字数、章节表）。
- 语言自动识别，可用 `--lang` 强制。
- 若报"几乎没抽到文字" → 扫描版 PDF，走视觉提取分支（见上）。
- 读完 `structure.json`，确认章节识别合理。章节数异常（=1 或过多）时，按字数均分即可。

### 阶段 2 · 切块

```bash
$PY $S/chunk_book.py --work <工作目录> --target-chars 12000
```

产出 `chunks/chunk_XXX.md` 与 `chunks/manifest.json`。

### 阶段 3 · 逐块精读 ⭐ 决定成片质量

先读 `references/extraction_playbook.md`。

**严格按 `manifest.json` 的 `reading_batches` 分批**：读一批 → 立刻写笔记 → 再读下一批。
绝不一次性把所有 chunk 读进上下文，否则后半本会被稀释。每块产出 `notes/chunk_XXX.md`，
全部读完后汇总成 `outline.json`（知识图谱，schema 见 playbook）。

书很长（>20 块）时可用 Agent 工具并行分派子代理各读一批，但**汇总 `outline.json` 必须由主代理完成**。

### 阶段 4 · 分集编排

基于 `outline.json` 的 `threads` 与 `depends_on` 产出 `episodes.json`。

核心原则：**按主题线分集，不按章节顺序分集**；一集一个核心问题；一集 3–5 个知识点。
详见 playbook 第三节。

`episodes.json` 每集**必须包含**（重命名阶段会用到）：

| 字段 | 说明 |
|---|---|
| `id` | `ep01` / `ep02` … |
| `title` | 该集创意标题（文稿标题与 RSS 兜底） |
| `chapter_range` | 真实章节范围，如 `第2-3章` / `第4章` / `学前测验+第1章` |
| `topic` | 该集核心内容短语，如 `毛利与留存收益` |

产出后向用户汇报分集方案，继续往下做，不必等确认（改脚本比改音频便宜）。

### 阶段 5 · 写脚本

先读 `references/script_writing.md`，再为每集写 `scripts/epNN.script.json`（schema 见
`assets/script_schema.json`）。音色搭配见 `references/tts_engines.md`。写完**逐条过一遍
script_writing.md 第八节自检清单**——能挡掉绝大多数事故。先只写第 1 集渲染试听，确认风格再批量写。

### 阶段 6 · 合成

```bash
# 语音合成（支持断点续渲，中断重跑复用已生成片段）
$PY $S/tts_render.py --script <工作目录>/scripts/ep01.script.json --out-dir <工作目录>/audio/ep01

# 拼接成一集
$PY $S/merge_audio.py --manifest <工作目录>/audio/ep01/render_manifest.json \
    --out <工作目录>/output/ep01.mp3 --album "《书名》拆书电台" --track 1

# 阶段 6.5 · 按章节重命名（默认规则，自动套用）
# 把 output/epNN.mp3 与同名 .md 重命名为 ep{NN}_{章节范围}_{主题}.mp3/.md
$PY $S/rename_by_chapter.py <工作目录>

# 重新生成 RSS 与索引，使文件名/标题一致
$PY $S/make_feed.py --dir <工作目录>/output \
    --title "《书名》拆书电台" --author "AI 拆书" \
    --description "..." --base-url https://your.host/podcast
```

渲染前建议先 `--dry-run` 看字符数与预估费用。同时按 `assets/shownotes_template.md`
为每集写 `output/epNN.md`（文件名与 mp3 同名，`make_feed.py` 自动关联）。

### 阶段 7 · 打包（RSS + 索引）

```bash
$PY $S/make_feed.py --dir <工作目录>/output \
    --title "《书名》拆书电台" --author "AI 拆书" \
    --description "..." --base-url https://your.host/podcast
```

产出 `podcast.xml`（可被播客客户端订阅）与 `index.md`。最后用 `present_files`
把 MP3、shownotes、`index.md` 交付给用户。

### 阶段 8 · 存入 ima 知识库（可选，默认询问）

生成的音频可存入 ima 知识库，按书名建文件夹、音频按章节顺序归档，便于在 ima 里对话式复习。

- **本机用户（zhy）**：按已存偏好**默认直接存入**（见用户级 MEMORY.md）。
- **其他用户**：默认**先询问**"是否要存入 ima 知识库"，确认后再传。

**执行流程（本技能内置，使用 ima-mcp 连接器）：**
1. 定位知识库：调用 `mcp__ima-mcp__get_knowledge_base_list`
   `{"params":[{"type":"KBT_MINE_KB","limit":50,"cursor":""}]}`，找到目标 KB（默认「书籍播客」，
   `can_add_knowledge==true`）。
2. **按书名建文件夹** ⚠️ **ima 连接器不暴露创建文件夹接口**，须用户在 ima 客户端 / 网页
   手动新建（如 `世界上最最简单的会计书`），再告诉我文件夹名 → 我用
   `mcp__ima-mcp__get_knowledge_list`（加 `filters` 只列 FOLDER）自动识别 `folder_id`。
3. 按 `ep01→epNN`（=章节顺序）逐文件入库，文件名保持 `ep{NN}_{章节范围}_{主题}.mp3` 原样
   （ima 以 `file_name` 作标题）。
4. 每文件三步：`create_media`（拿 COS 临时凭证）→ `cos-upload.cjs` 传字节 → `add_knowledge(folder_id)`。
5. 回查 `mcp__ima-mcp__get_knowledge_list(folder_id=...)` 校验落位。

详细字段 / 凭证映射 / MIME 对照 / 限制见 `references/ima_api.md`。**注意：ima 上传不可逆
（不能移动/删除/重命名），确认无误再传。**

---

## 用 pipeline.py 自动化确定性步骤

只做不依赖 LLM 的体力活，LLM 环节（④⑤）由你在中间完成。

```bash
PY=<技能目录>/.venv/bin/python
PL=<技能目录>/scripts/pipeline.py

# ①+②+③ 抽取与切块，并打印书的结构摘要
$PY $PL prep --book "/path/书.pdf" --work "/path/工作目录"

# （中间你自己做④⑤：精读 → episodes.json → epNN.script.json）

# ⑥ 逐集合成、拼接、按章节重命名、生成 RSS
$PY $PL render --work "/path/工作目录" --author "AI 拆书电台"
```

`render` 默认：引擎 edge-tts（免费）、专辑名《书名》拆书电台、自动按 `episodes.json`
的 `chapter_range`+`topic` 重命名为 `ep{NN}_{章节范围}_{主题}.mp3`。

---

## 常用命令速查

```bash
# 看某语言有哪些可用音色
$PY $S/tts_render.py --list-voices --engine edge --lang zh

# 只估算成本，不真渲
$PY $S/tts_render.py --script ep01.script.json --out-dir /tmp/x --dry-run

# 换引擎（脚本不用改，voices 里已按引擎分别配好）
$PY $S/tts_render.py --script ep01.script.json --out-dir out --engine aliyun

# 加 BGM 和片头
$PY $S/merge_audio.py --manifest ... --out ep01.mp3 --bgm bgm.mp3 --bgm-db -26 --intro intro.mp3

# 强制重渲某集（忽略缓存）
$PY $S/tts_render.py --script ep01.script.json --out-dir out --force
```

---

## 产物结构

```
<工作目录>/                        # 默认 <cwd>/book-podcast/<书名>/
├── book.txt                    全文
├── structure.json              元数据 + 章节表
├── chunks/                     切块 + manifest
├── notes/                      逐块精读笔记
├── outline.json                全书知识图谱  ← 阶段 3 核心产出
├── episodes.json               分集方案（含 chapter_range/topic）
├── scripts/epNN.script.json    对话脚本
├── audio/epNN/                 逐句音频片段 + render_manifest.json
└── output/
    ├── ep01_学前测验+第1章_会计基本等式与资产负债表.mp3   成品音频 ← 交付
    ├── ep01_学前测验+第1章_会计基本等式与资产负债表.md    单集文稿 ← 交付
    ├── podcast.xml             RSS 订阅源
    └── index.md                索引           ← 交付
```

---

## 排错

| 现象 | 原因与处理 |
|---|---|
| 抽不到文字 | 扫描版 PDF，走视觉提取分支（渲染页面图 + 子代理读图） |
| 章节全乱 / 只有 1 章 | 该书无标准章节标记，忽略即可，按字数切块不影响结果 |
| 中文书变成乱码 | 旧 GBK 编码，脚本已自动处理；仍失败用 `iconv` 预转 UTF-8 |
| `.mobi` 报错 | 装 calibre，或先手动转 epub |
| TTS 报 403 / 401 | API Key 未设或过期，见 `references/tts_engines.md` |
| 云端引擎频繁失败 | 降并发：`--concurrency 2` |
| 合成音频没有停顿 | 缺 ffmpeg，装上重跑 `merge_audio.py`（无需重渲语音） |
| 成片语速怪 / 念错字 | 回到脚本改文本，见 `script_writing.md` 第四节 TTS 友好规则 |
| 渲染中断 | 直接重跑同一条命令，已完成片段自动复用 |
| ima `create_media` 大小超限 | 确认 `file_size` 与磁盘字节数一致；单文件 ≤200MB、≤2 小时 |
| COS 上传 403 / 签名错误 | 检查 `start_time/expired_time` 是否原样透传，不要重新计算 |
| ima 找不到文件夹 | 回到阶段 8 步骤 2，提示用户在 ima 客户端新建 |

---

## 参考文档

- `references/extraction_playbook.md` —— 知识拆解方法论、笔记模板、`outline.json` schema、按书型调整拆法。**阶段 3 前必读**
- `references/script_writing.md` —— 角色设定、单集结构、口语化改写、TTS 友好规则、自检清单。**阶段 5 前必读**
- `references/tts_engines.md` —— 引擎对比、鉴权配置、各语言推荐音色搭配
- `references/ima_api.md` —— ima-mcp 4 个工具字段、凭证映射、MIME 对照、限制
- `references/decisions.md` —— 格式→抽取决策树、TTS 引擎、命名规则、ima 规则速查
- `assets/script_schema.json` —— 脚本 JSON 完整 schema
- `assets/shownotes_template.md` —— 单集文稿模板

---

## 版权提醒

生成物用于个人学习笔记与知识整理。**不要逐字朗读原书大段内容**——
拆书是提炼与再表达，不是有声书翻录。公开发布前提醒用户注意版权，
并在文稿末尾标注观点归属原作者。
