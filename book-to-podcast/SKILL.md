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
3. **ima 入库**：把成品音频**和书籍源文件**按章节顺序上传到 ima 知识库指定文件夹（自带零依赖 `ima_cos_upload.js` + MCP 工具流程）。

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
| 8 | **ima 上传 COS 签名错** | 403 `InvalidAccessKeyId`，误判"连接器坏了"反复换方式 | 直连 COS 域名 + 签 `host;content-length`（`ima_cos_upload.js` 已对，直接用） |
| 9 | **大文件超 STS 上限** | 191MB 被 `AccessDenied`；反复重试浪费时间 | 单文件 <100MB 才自动传；超限按兜底告知用户手动上传 |

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

**edge-tts 偶发 400 的抗造渲染（重要）**：免费端点偶发返回 `400 invalid parameter value`（非内容问题，约每 80 句 1 句）。
`pipeline.py render` 在任一集渲染失败时会整体 `sys.exit`，导致后续集不渲染、未完成的集不合并——一次崩全盘。
正确做法（救法与预防）：
1. 失败句对应的 `seg_XXXX.mp3` 是 0 字节，删掉它；
2. `tts_render.py` 自带断点续渲（以 `size>0` 判缓存，已正常的句自动跳过），只重渲失败句；
3. 用**外层重试循环**包住整条管线（每集最多 8 轮、每轮 `--retries 10 --concurrency 2`），跑完所有集再统一 `merge → rename → make_feed`。
这样单次抖动不会中断全流程，也不浪费已渲染的片段。

**补充：比 400 更隐蔽的「并发挂起」（2026-08 实测，比 400 更容易浪费大量时间）**

上面说的是「报错型」失败。**更要命的是「静默挂起型」**：`--concurrency` 调高（如 4）时，
edge-tts 偶发请求**无限挂起 —— 不报错、不超时、不退出**，进程原地卡死数小时。

🐛 真实事故：一次渲染中 ep03 卡在某句 15 分钟无任何新片段产出（对照 `ls -lt` 的文件
修改时间才发现）。更坑的是：**删掉 0 字节文件后整集重跑，往往再次卡在同一句**，
于是上面「删 0 字节 → 重渲」的常规救法在这里失灵，白白耗掉 20+ 分钟。

**症状自查**：某集 `seg_*.mp3` 数量长时间不增长，且 `ls -lt <ep 目录>` 最后修改时间
停在很久以前 → 基本可判定挂起，**不要继续干等**，立刻介入。

**正确的三层防御（按优先级）**：

| 层 | 做法 | 目的 |
|---|---|---|
| 预防 | 批量渲染用 `scripts/render_batch.py`（逐集 `subprocess` 超时，默认 900s），别用裸 for 循环 | 卡死只损失一集，不拖垮整批 |
| 降频 | 挂起后改用 `--concurrency 1~2` 而非 4 | 高并发是挂起诱因 |
| 救法 | `python scripts/fix_segments_solo.py <工作目录> [轮数]` | 把每个 0 字节句抽成最小脚本单句重渲，2–3 秒/句，稳定 |

`fix_segments_solo.py` 原理：单独构造只含**一句**的极小脚本，`--concurrency 1` 渲染，
再把产物按原 `seg_XXXX.mp3` 编号复制回去。它复用原脚本的 voices/engine 配置，
产物与批量渲染结果一致，可安全拼接。集号支持 `03` 与 `ep03` 两种写法。

**配套坑：进程被中断后 manifest 丢失**
渲染进程被 kill/超时后，片段已落盘但 `render_manifest.json` 没写成，此时 `merge_audio.py`
报 `FileNotFoundError: render_manifest.json`。**不要整集重渲**（可能再次挂起），改用：

```bash
python scripts/rebuild_manifest.py <工作目录> 03     # 从已存在的片段反向补 manifest
```

它复用 `tts_render.py` 的 `resolve_voice` 与文本清洗逻辑，保证 hash/voice 与原始渲染一致；
若仍有缺失或 0 字节片段会主动中止并提示，不会产出坏 manifest。

**macOS 无 `timeout` 命令**：想给命令加超时别写 `timeout 180 ...`（会 `command not found`）。
要么 `brew install coreutils` 后用 `gtimeout`，要么直接用上述 Python 脚本
（内部已用 `subprocess.run(..., timeout=)`）。

**另一个隐蔽坑：同时跑多个渲染进程会被系统 kill（exit 137）**
后台批量渲染 + 前台补渲同时进行时，进程可能被 OOM/资源管控直接杀掉（退出码 137）。
**渲染阶段尽量串行**，不要一边后台批量渲一边前台补渲同一批集。

### 写脚本 JSON 的高频手误：`speaker` 后误写冒号

写 `epNN.script.json` 时极易写成
`{"speaker": "host": "text": "..."}`（第二个分隔符写成 `:` 而非 `,`），
`tts_render.py` 只会抛一长串 `JSONDecodeError` 栈，不直接指到问题行。
**低成本防护**：写完所有脚本后先跑一次校验，别等渲染时才炸：

```bash
python - <<'EOF'
import glob, json, re
pat = re.compile(r'("speaker"\s*:\s*"[^"]+")\s*:\s*("text"\s*:)')
for p in sorted(glob.glob('scripts/ep*.script.json')):
    s = open(p, encoding='utf-8').read()
    new = pat.sub(r'\1, \2', s)
    if new != s:
        open(p, 'w', encoding='utf-8').write(new); print('fixed', p)
    d = json.load(open(p, encoding='utf-8'))
    print(f"valid {p} | {len(d['lines'])} 句 | {sum(len(l['text']) for l in d['lines'])} 字符")
EOF
```

**顺带卡字数**：中文 250–280 字/分，目标 18–22 分钟 ⇒ **每集需 4500–5500 字符**。
初稿常只写到 1500–1800 字符（约 7–8 分钟），明显偏短，渲染前务必先核对上面这行输出。

### 章节识别失效不等于报废（PDF 目录页码错位时）

部分 PDF（尤其华章/机械工业出版社电子书）的目录文本会被抽成 `第章`（数字被拆散），
导致 `structure.json` 只识别出「前言 / 后记」两章，正文全被塞进「后记」。
**不要因此重做抽取**——`chunk_book.py` 的切块仍然可用，正文内容完整。

正确做法：**从 `book.txt` 开头的目录文本人工还原真实章节表**，再在 `episodes.json`
的 `chapter_range` 字段里写回真实章节（如 `第3章`、`第6-9章`），命名规范照样成立。
可用 `grep -n "^第[0-9]*章\|^前言\|^引子\|^后记\|^附录" book.txt` 定位章节起始行辅助还原。

**G. ima 上传（COS 直传）专属坑 —— 必须按正确方式签，且注意文件大小上限**

ima 连接器**没有"直接上传文件"的工具**。上传 = `create_media`（拿 COS 临时凭证）→ 客户端自签 PUT 到 COS → `add_knowledge`（归库）。自签 PUT 有两条致命细节，错一个就 403：

> **当前上传器：`scripts/ima_cos_upload.js`（Node + 官方 `cos-nodejs-sdk-v5`，已替代旧的 `ima_cos_upload.js`）**。首次使用前安装 SDK：`mkdir -p /Users/zhy/.workbuddy/binaries/node/workspace && <托管node>/npm install cos-nodejs-sdk-v5`。脚本已内置路径解析，自动用官方 SDK 签名（`host`+`content-length` 由 SDK 处理），无需手签；直接 `node ima_cos_upload.js <creds.json>` 即可，不要自己实现上传。

1. **必须用直连 COS 域名，且签名要包含 `content-length`**：
   - ✅ 正确：上传主机 = `https://{bucket}.cos.{region}.myqcloud.com`，签名 header 列表 = `host` **+ `content-length`**（`ima_cos_upload.js` 用官方 SDK 就是这么签的，直接用它，不要自己实现）。
   - ❌ 错误：`custom_domain`（CDN 域名）、或只签 `host` → COS 回 `403 InvalidAccessKeyId`（**不是密钥失效，是签名不匹配**）。
   - 🐛 真实坑：曾用 `custom_domain` + 只签 `host` 上传，连续 6 轮都 403，一度误判"连接器坏了"；改成直连域名 + 签 `content-length` 后立刻 200。
2. **STS 临时凭证有单次上传大小上限（约 100MB）**：
   - ✅ 经验值：39MB PDF 成功；**191MB PDF 被 `AccessDenied` 拒绝**（凭证有效、签名正确，仅因文件超上限）。
   - ⚠️ 安全阈值：单文件 **<100MB** 再走自动上传。ima 文档写的"≤200MB"是 `create_media` 入参上限，但 COS STS 凭证实际卡在 ~100MB，**以 ~100MB 为准**。
   - 🐛 **超限处理（硬性）**：若大文件（如高清扫描 PDF 常 150–200MB）上传被 `AccessDenied` 拒绝，**立即停止自动重试**，按下面"阶段 8 失败兜底"告知用户原因并请其手动上传——不要无限重试、不要自己猜原因。

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
   手动新建（如 `世界上最简单的会计书`），再告诉我文件夹名 → 我用
   `mcp__ima-mcp__get_knowledge_list`（加 `filters` 只列 FOLDER）自动识别 `folder_id`。
3. 按 `ep01→epNN`（=章节顺序）逐文件入库音频，文件名保持 `ep{NN}_{章节范围}_{主题}.mp3` 原样
   （ima 以 `file_name` 作标题）。
   - ⚠️ **`folder_id` 必须精确无误**：它是长串字符（如 `folder_7494237180399974`），**务必从配置/变量读取或粘贴后逐位核对**，绝不在多个 `add_knowledge` 调用里逐条手写——手误一位就会报「文件夹不存在」，且只影响那一个文件，极难排查。建议把 `folder_id` 存进一个变量，6 个调用共用。
4. **把书籍源文件（原 PDF / EPUB / DOCX …）也上传到同一文件夹**（强烈推荐，便于在 ima 里对照原文与音频）：
   - `create_media`：`file_name` 用**原文件名**（如 `世界上最简单的会计书(高清).pdf`）、
     `content_type` 按扩展名查 `references/ima_api.md` 的 MIME 表（pdf→`application/pdf`）、
     `file_size` **必须与磁盘字节数完全一致**，否则服务端拒收。
   - `ima_cos_upload.js` 传字节（⚠️ **必须传 `--start-time`/`--expired-time`**，取自 `create_media` 返回的 `start_time`/`expired_time`；否则本机时钟若慢于真实时间，签名会落在 STS 生效窗口外，报 `InvalidAccessKeyId`）→ `add_knowledge(folder_id)`。
   - 🐛 **真实坑**：扫描版 / 高清 PDF 源文件常达 100–200MB，`ima_cos_upload.js` 默认 socket 超时 5 分钟，
     大文件务必加 `--timeout 540000`；调用它的 Bash 命令也要设较长超时（如 600000ms），否则传到一半被切断。
   - ⚠️ 上传不可逆，源文件名确认无误再传（建议保持原文件名，ima 以 file_name 作标题）。
5. 每文件（音频 + 源文件）三步：
   `create_media`（拿 COS 临时凭证）→ `ima_cos_upload.js` 传字节 → `add_knowledge(folder_id)`。
6. 回查 `mcp__ima-mcp__get_knowledge_list(folder_id=...)` 校验落位（音频 + 源文件都应出现）。

**⚠️ 上传失败兜底（硬性规则）**
- 若 `create_media` + `ima_cos_upload.js` 上传报错，典型错误码与含义：
  - `AccessDenied` → **文件超过 STS 凭证单次上传上限（约 100MB）**；
  - `InvalidAccessKeyId` → STS **时间窗口错**（最常见）：本机时钟慢于真实时间时 `ima_cos_upload.js` 默认 `Date.now()` 签名落在凭证 `start_time` 生效窗口外，腾讯云判定临时 AKID 无效；**必须用 `create_media` 返回的 `start_time`/`expired_time` 作 `--start-time`/`--expired-time` 签名**；另临时 `secret_id` 漏字符也会触发，须整段完整复制。
  - `403` 超时 → Bash 调用超时太短（大文件须 `--timeout 540000` + Bash ≥600000ms）。
- **处理流程（硬性）**：① 先读 COS 返回的错误码判定原因，**不要盲目重试**；② 超限或签名域错 → **停止自动重试**；③ **明确告知用户**：哪本书、哪个文件、失败原因（如"源 PDF 191MB 超过 ima 单次上传上限约 100MB"）、建议操作（"请在 ima 客户端手动把该文件拖入『书籍播客 / 书名』文件夹"）；④ 已成功入库的文件照常保留，不回滚，其余小文件继续传。
- ❌ **禁止**：超限文件反复重试、自己改写签名算法"碰运气"、不告知用户就跳过。

**⚠️ 前置判定：连接器是否已连接（开工阶段 8 前必查）**

本会话的 `<connector-status>` 会列出每个连接器的状态。若看到
`ima-mcp ima知识库: disconnected`，说明**阶段 8 此刻无法自动完成**，不要硬闯。

确认方法：`ToolSearch` 用 `tool_names: ["mcp__ima-mcp__get_knowledge_list", ...]` 精确查找。
⚠️ **判定陷阱**：ToolSearch 在找不到目标时会返回**一批不相关的工具**（如 github 的工具），
看起来像"找到了 2 个"，其实**一个 ima 工具都没有**。所以必须**逐个核对返回工具名是否以
`mcp__ima-mcp__` 开头**，不能以"Found N tool(s)"的数量判断。

确认未连接后的处理（硬性）：
1. **先把阶段 1–7 完整交付**（本地 mp3 + shownotes + podcast.xml + index.md），不要卡在上传上。
2. 顺手生成 `upload_manifest.json`（记录每个待传文件的 `file_name` / `file_size` /
   `content_type` / `file_ext`，并核对总计是否超过 100MB 阈值），为后续上传做准备。
3. **明确告知用户**：ima 连接器当前未连接 → 请在连接器管理页连接后让我继续上传；
   或给出手动上传路径（ima 客户端 → 「书籍播客」→ 书名文件夹 → 拖入文件）。
4. ❌ 不要假装上传成功；❌ 不要因为上传失败就不交付本地产物。

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
| edge-tts 偶发 `400 invalid parameter` | 免费端点网络抖动（约每 80 句 1 句，非内容问题），`pipeline.py render` 默认 3 次重试后整体 `sys.exit`，会中断后续集渲染、未完成集不合并；救法：删掉 0 字节段 → 断点续渲（`tts_render` 以 `size>0` 判缓存，已正常的句跳过）→ 外层重试循环包住整条管线（如每集最多 8 轮、每轮 `--retries 10`），跑完所有集再统一合并+重命名+RSS |
| ima `add_knowledge` 报「文件夹不存在」 | `folder_id` 手误/写错（如 `999974`↔`0399974`）→ 该集未入库；核对 `folder_id` 后用正确值重提 `add_knowledge` 即可，无需重传字节 |
| COS 上传 403 `InvalidAccessKeyId` | **STS 临时凭证签名时间窗口错（最常见根因）**：`ima_cos_upload.js` 默认用本机 `Date.now()` 做签名窗口，若**本机系统时钟慢于真实时间**（哪怕慢几分钟），签名时间会落在 `create_media` 返回的 `start_time` 生效窗口之外，腾讯云直接判定该临时 AKID 无效。救法：把 `create_media` 返回的 `start_time`/`expired_time` 作为 `--start-time`/`--expired-time` 传给 `ima_cos_upload.js` 再签名（绝不用默认 Date.now）；若仍偶发 403，sleep 15s 重试（ima↔腾讯云 凭证传播有秒级延迟）。另：`create_media` 返回的 `secret_id` 是临时 AKID，**必须整段完整复制**，漏一位字符同样报 InvalidAccessKeyId |
| COS 上传 `AccessDenied` | **文件超 STS 凭证单次上限（约 100MB）**：39MB 成功、191MB 被拒；超限请告知用户手动上传，不要重试 |
| COS 上传 403 超时 | Bash 调用超时太短；大文件加 `--timeout 540000` 且 Bash 设 ≥600000ms |
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
