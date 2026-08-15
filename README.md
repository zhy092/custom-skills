# custom-skills

WorkBuddy 自定义技能仓库 —— 存放我自己创建 / 改造的技能。

每个子目录是一个独立的 WorkBuddy 技能，可直接复制到 `~/.workbuddy/skills/<name>/` 使用。

## 已收录技能

### [book-to-podcast](./book-to-podcast/)
一体化「拆书播客」技能：把任意格式的书籍（PDF / EPUB / MOBI / TXT / DOCX / HTML …）拆解成结构化知识要点，并自动生成多集**双人对话播客音频（MP3）**、逐集文稿与 RSS 订阅源，还能一键存入 ima 知识库「书籍播客」按书名归档。

- 语音引擎：默认 `edge-tts`（免费、无需 API Key），另支持阿里云百炼 Qwen-TTS、火山引擎豆包、MiniMax、OpenAI。
- 产物命名：`ep{序号}_{章节范围}_{主题}.mp3`（按真实章节拆分）。
- 安装：把 `book-to-podcast/` 放进 `~/.workbuddy/skills/`，然后运行 `bash book-to-podcast/scripts/setup_env.sh`（自动建 venv 并装依赖，含完整静态 ffmpeg）。

### [github-skill-store](./github-skill-store/)
技能分发与版本管理工具：把本地 WorkBuddy 技能**一键推送到 GitHub 仓库**（`zhy092/custom-skills`），支持新增 / 更新、自动排除 `.venv` 等缓存文件、维护 README 索引。

- 适用场景：用户说"把技能存到 GitHub""push 到 github""归档这个技能"时调用。
- 跨平台支持：macOS 钥匙串 / 环境变量 `GITHUB_TOKEN` / `gh auth token` / `~/.git-credentials` 四种取 Token 方式。
- 安全：Token 仅存在于 shell 变量，推送后清理临时目录，不残留凭据。

### [github-actions-cleanup](./github-actions-cleanup/)
排查并清理 GitHub 账户的 Actions 存储占用（artifacts 构建产物 + caches 依赖缓存），释放 0.5GB 免费配额。

- 适用场景：收到 GitHub "Actions storage 已用 X%" 告警、询问"哪个仓库占用 Actions 空间 / 存储满了 / 清理 Actions 缓存"时调用。
- 安全原则：仅删除 expired artifact 和 caches；active artifact 需用户确认；正在写入的 artifact 跳过。
- 延迟提醒：删除后 GitHub Billing 仪表盘可能有 5–30 分钟延迟，不代表删除失败。

## 目录约定
```
custom-skills/
├── README.md            # 本索引
├── .gitignore           # 忽略 venv / 缓存
└── <skill-name>/        # 每个技能一个目录
    └── SKILL.md         # 技能说明（必需）
```

## 提交新技能
1. 在仓库根目录新建 `<skill-name>/`，放入 `SKILL.md` 与脚本/资源；
2. 更新本 README 的「已收录技能」列表；
3. 提交并推送到 `main`。

