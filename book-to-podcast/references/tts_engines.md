# TTS 引擎配置与音色搭配

## 一、选型速查

| 引擎 | `--engine` | 费用 | 中文自然度 | 语言覆盖 | 鉴权 |
|---|---|---|---|---|---|
| **Edge 大声朗读** | `edge` | **免费** | ★★★☆☆ | 40+ 语言、300+ 音色 | 无需 Key |
| **阿里云百炼 Qwen-TTS** | `aliyun` | ≈ ¥200/百万字符 | ★★★★★ | 单音色即支持 10 语言 + 10 种方言 | `DASHSCOPE_API_KEY` |
| **火山引擎（豆包）** | `volcano` | ≈ ¥250/百万字符 | ★★★★★ | 中英为主 | `VOLC_TTS_APPID` + `VOLC_TTS_TOKEN` |
| **MiniMax Speech** | `minimax` | ≈ ¥300/百万字符 | ★★★★★ | 多语言、情感强 | `MINIMAX_API_KEY` + `MINIMAX_GROUP_ID` |
| **OpenAI 兼容** | `openai` | ≈ ¥430/百万字符 | ★★★★☆ | 多语言、音色少 | `OPENAI_API_KEY` |
| **macOS say** | `say` | 免费离线 | ★★☆☆☆ | 跟随系统语音包 | 无 |

价格为 2026 年公开单价量级，仅用于 `--dry-run` 粗估，实际以各家账单为准。

### 怎么选

- **先跑通、零成本** → `edge`。20 分钟一集约 5000 字，完全免费
- **要发布、要中文听感** → `aliyun`。一集 5000 字 ≈ ¥1，性价比最高，
  且**同一个音色能读 10 种语言**，做多语种书特别省事
- **国内低延迟批量生产** → `volcano`
- **要情感张力（文学类）** → `minimax`
- **断网 / 兜底** → `say`

> 成本感受：一本 20 万字的书拆成 8 集、每集 5000 字 = 4 万字。
> `edge` ¥0；`aliyun` ≈ ¥8；`openai` ≈ ¥17。**成本不是瓶颈，脚本质量才是。**

---

## 二、鉴权配置

```bash
# 阿里云百炼（推荐国产方案）
# 控制台: https://bailian.console.aliyun.com  → API-KEY
export DASHSCOPE_API_KEY="sk-xxxx"
export DASHSCOPE_TTS_MODEL="qwen3-tts-flash"      # 可选，默认即此

# 火山引擎豆包
# 控制台: https://console.volcengine.com/speech/app
export VOLC_TTS_APPID="xxxx"
export VOLC_TTS_TOKEN="xxxx"
export VOLC_TTS_CLUSTER="volcano_tts"             # 可选

# MiniMax
export MINIMAX_API_KEY="xxxx"
export MINIMAX_GROUP_ID="xxxx"

# OpenAI 或任意兼容端点（如国内中转）
export OPENAI_API_KEY="sk-xxxx"
export OPENAI_BASE_URL="https://api.openai.com/v1"
```

写进 `~/.zshrc` 或 `~/.bashrc` 可持久生效。`edge` 与 `say` 无需任何配置。

---

## 三、推荐音色搭配

脚本里按引擎分别配好，切引擎时无需改脚本：

```json
"voices": {
  "host":  {"edge": "zh-CN-YunxiNeural",    "aliyun": "Ethan", "volcano": "BV700_streaming", "rate": "+6%"},
  "guest": {"edge": "zh-CN-XiaoxiaoNeural", "aliyun": "Elias", "volcano": "BV701_streaming"}
}
```

### 阿里云 Qwen-TTS（拆书场景优选）

| 角色 | voice | 中文名 | 为什么合适 |
|---|---|---|---|
| **嘉宾/领读** | `Elias` | 墨讲师 | 官方定位就是"把复杂知识转化为可消化模块"，拆书首选 |
| **主持人** | `Ethan` | 晨煦 | 阳光温暖有活力，提问不违和 |
| 主持人（女） | `Cherry` | 芊悦 | 亲切自然，最通用 |
| 严肃/学术书 | `Neil` | 阿闻 | 新闻主播腔，字正腔圆 |
| 历史/传记 | `Eldric Sage` | 沧明子 | 沉稳睿智老者感 |
| 文学/故事 | `Vincent` | 田叔 | 沙哑烟嗓，叙事张力强 |
| 知性女声 | `Maia` | 四月 | 知性温柔，适合社科 |
| 轻松/生活类 | `Serena` | 苏瑶 | 温柔不端着 |

**关键优势**：以上音色**每个都支持中/英/法/德/俄/意/西/葡/日/韩 10 种语言**，
做多语种书时不用换音色，音色人格保持一致。

另有 10 个方言音色（`Dylan` 北京、`Sunny`/`Eric` 四川、`Rocky`/`Kiki` 粤语、
`Jada` 上海、`Peter` 天津、`Marcus` 陕西、`Li` 南京、`Roy` 闽南），
做地域特色内容可用。

调用时可加 `language_type` 提示语种（如 `Chinese` / `English`），提升发音准确度。

### Edge（免费方案）

| 语言 | 主持人 | 嘉宾 | 备选 |
|---|---|---|---|
| 中文 普通话 | `zh-CN-YunxiNeural` 男·活泼 | `zh-CN-XiaoxiaoNeural` 女·亲和 | `zh-CN-YunjianNeural` 男·浑厚<br>`zh-CN-XiaoyiNeural` 女·活力 |
| 中文 严肃 | `zh-CN-YunyangNeural` 男·播音 | `zh-CN-XiaoxiaoNeural` | — |
| 粤语 | `zh-HK-WanLungNeural` 男 | `zh-HK-HiuMaanNeural` 女 | — |
| 中文 台湾 | `zh-TW-YunJheNeural` 男 | `zh-TW-HsiaoChenNeural` 女 | — |
| 英语 美 | `en-US-AndrewNeural` 男 | `en-US-AvaNeural` 女 | `en-US-BrianNeural`<br>`en-US-EmmaNeural` |
| 英语 英 | `en-GB-RyanNeural` 男 | `en-GB-SoniaNeural` 女 | — |
| 日语 | `ja-JP-KeitaNeural` 男 | `ja-JP-NanamiNeural` 女 | — |
| 韩语 | `ko-KR-InJoonNeural` 男 | `ko-KR-SunHiNeural` 女 | — |
| 法语 | `fr-FR-HenriNeural` 男 | `fr-FR-DeniseNeural` 女 | — |
| 德语 | `de-DE-ConradNeural` 男 | `de-DE-KatjaNeural` 女 | — |
| 西语 | `es-ES-AlvaroNeural` 男 | `es-ES-ElviraNeural` 女 | — |
| 葡语 巴西 | `pt-BR-AntonioNeural` 男 | `pt-BR-FranciscaNeural` 女 | — |
| 意语 | `it-IT-DiegoNeural` 男 | `it-IT-ElsaNeural` 女 | — |
| 俄语 | `ru-RU-DmitryNeural` 男 | `ru-RU-SvetlanaNeural` 女 | — |
| 阿拉伯语 | `ar-SA-HamedNeural` 男 | `ar-SA-ZariyahNeural` 女 | — |
| 印地语 | `hi-IN-MadhurNeural` 男 | `hi-IN-SwaraNeural` 女 | — |

完整列表随时查：

```bash
$PY scripts/tts_render.py --list-voices --engine edge --lang zh
$PY scripts/tts_render.py --list-voices --engine edge          # 全部
```

**edge 参数**：`rate` `"+6%"`、`pitch` `"-2Hz"`、`volume` `"+0%"`。
双人对话时给主持人 `rate: "+6%"` 制造语速差，对话感更真。

### 火山引擎常用 voice_type

`BV700_streaming` 灿灿（女·通用）· `BV701_streaming` 擎苍（男·浑厚）·
`BV001_streaming` 通用女声 · `BV002_streaming` 通用男声 ·
`BV705_streaming` 炀炀 · `BV406_streaming` 梓梓

完整列表见火山控制台「音色管理」，不同账号开通的音色不同，
**用之前先在控制台确认已开通**，否则报错。

### OpenAI

`alloy` `echo` `fable` `onyx` `nova` `shimmer` `ash` `ballad` `coral` `sage` `verse`

搭配建议：主持人 `ash`（男·干练）／嘉宾 `sage`（中性·沉稳）；
或 `onyx`（男·低沉）+ `nova`（女·明亮）。
支持 `instructions` 字段用自然语言控制风格，如
`"speak like a curious podcast host, warm and slightly fast"`。

### MiniMax

`male-qn-qingse` 青涩男 · `female-shaonv` 少女 · `presenter_male` 男主持 ·
`presenter_female` 女主持 · `audiobook_male_1` 有声书男 · `audiobook_female_1` 有声书女

拆书推荐 `presenter_male` + `audiobook_female_1`。

### macOS say

```bash
say -v '?'          # 列出已装语音；中文需在 系统设置→辅助功能→朗读内容→系统声音 里下载
```

常见：`Tingting`（中）、`Samantha`/`Alex`（英）、`Kyoko`（日）、`Yuna`（韩）。
参数用 `wpm`（每分钟词数，中文建议 180–220）。
**输出 AIFF，合并必须有 ffmpeg。**

---

## 四、排错

| 报错 | 原因 | 处理 |
|---|---|---|
| `403` / `401` | Key 未设 / 过期 / 没开通该服务 | 检查环境变量；到控制台确认服务已开通 |
| 阿里云 `InvalidParameter: voice` | 音色 ID 拼错，或该模型不支持此音色 | 对照上表；注意 `Eldric Sage` 含空格 |
| 火山 `code != 3000` | 音色未开通 / cluster 不对 | 控制台确认音色权限；试 `VOLC_TTS_CLUSTER=volcano_tts` |
| 频繁超时、部分片段失败 | 并发过高被限流 | `--concurrency 2`，脚本自带 3 次退避重试 |
| edge 卡住不返回 | 网络到微软端点不通 | 换网络或改用国产引擎 |
| 生成了空文件 | 文本被清洗后为空（整行都是符号） | 检查该行 `text` 是否只有 Markdown 记号 |
| 合成音频忽大忽小 | 不同引擎/音色响度不一 | `merge_audio.py` 默认已做 `loudnorm`，别加 `--no-normalize` |

**通用建议**：正式批量渲染前先 `--dry-run` 看字符数与费用，
再单独渲染第 1 集试听，确认音色与语速合适后再跑全量。
渲染中断直接重跑同一条命令即可，已完成片段会自动复用。
