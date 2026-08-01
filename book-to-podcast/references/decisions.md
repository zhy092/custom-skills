# 决策树与默认值（总控技能速查）

## 1. 格式 → 抽取方式
| 输入格式 | 路径 | 备注 |
|---|---|---|
| PDF（文本层正常） | `extract_book.py` 直接读 | — |
| PDF（扫描版/图片型，文字层坏） | 渲染页面图 + 视觉子代理读图 → 写 notes | book-to-podcast 无原生 OCR；`ocrmypdf` 也可 |
| EPUB / TXT / MD / RTF / HTML | `extract_book.py` | 零额外依赖 |
| DOCX | `extract_book.py`（python-docx） | — |
| MOBI / AZW / AZW3 / FB2 / LIT / PDB / DJVU | 先 `ebook-convert in out.epub`（calibre）→ 再抽取 | 需系统装 calibre |
| PPT / PPTX | ❌ 不支持 | 仅 DOCX 在支持列表内 |

判定方法：看扩展名即可；若 PDF 抽取后 `book.txt` 几乎无有效文字（只有水印/乱码），
立即切换到「扫描版」分支。

## 2. TTS 引擎
| 引擎 | 费用 | 需要 |
|---|---|---|
| `edge-tts`（默认） | 免费 | 无 Key |
| 阿里云百炼 Qwen-TTS | 按量 | API Key |
| 火山引擎豆包 | 按量 | API Key |
| MiniMax / OpenAI | 按量 | API Key |

默认走 edge-tts，零成本出片；用户要更自然音色再切云端引擎。

## 3. 命名规则（固化）
`ep{NN}_{章节范围}_{主题}.mp3`
- `chapter_range` 例：`学前测验+第1章` / `第2-3章` / `第4章` / `第9-10章`
- `topic` 例：`毛利与留存收益` / `权责发生制与创意会计`
- 由 `rename_by_chapter.py` 依据 `episodes.json` 自动套用。

## 4. ima 入库规则
- 知识库：本机默认「书籍播客」；其他用户先问。
- 文件夹：按**书名**命名，须用户在 ima 客户端手动建（连接器无创建文件夹接口）。
- 顺序：`ep01 → epNN`（即章节顺序）。
- 重名策略：`DUPLICATE_NAME_STRATEGY_SAVE`。
- 可逆性：上传后不可移动/删除/重命名（不可逆），确认无误再传。
- 本机用户默认直接存；其他用户默认先询问。

## 5. 工作目录约定
默认 `<cwd>/book-podcast/<书名>/`，含：
`book.txt` `structure.json` `chunks/` `notes/` `episodes.json` `outline.json`
`scripts/epNN.script.json` `audio/epNN/` `output/epNN_*.mp3` + `epNN_*.md` `podcast.xml` `index.md`
