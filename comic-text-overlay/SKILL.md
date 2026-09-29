---
name: comic-text-overlay
description: 给漫画图片添加中文字幕文字，合成图文并茂的绘本长图。当用户想要给漫画/绘本添加故事文字、给图片加字幕、或制作图文并茂的儿童故事漫画时使用此技能。
agent_created: true
tags:
  - image
  - text-overlay
  - comic
  - children's-book
  - PIL
  - python
---

# 图文漫画文字合成

将故事文字叠加到漫画/绘本图片上，生成每格含文字的图文并茂版本。

## 核心工具

使用 Python PIL（Pillow）库进行图片处理和文字合成。

**Python 环境**：
```
/Users/zyb/.workbuddy/binaries/python/envs/default/bin/python
```
（如 PIL 未安装：`pip install Pillow -q` 安装到该 venv）

## 工作流程

### Step 1：分析图片结构

确定图片尺寸和面板数量，计算每个面板的高度：
```
panel_height = image_height // num_panels
```

### Step 2：准备故事文字

为每个面板准备对应的文字内容（3-4行中文，简洁易懂）。

### Step 3：编写合成脚本

参考 `scripts/add_text_to_comic.py` 的结构，包含：

1. **字体加载**：按优先级尝试 PingFang → Hiragino Sans GB → Arial Unicode → load_default
2. **字体大小**：标题48px，格文字26px，金句24px（可根据图片宽度调整）
3. **文字区域高度**：每格下方预留 100-140px 文字区
4. **金句区域**：底部预留 80px，用浅色背景突出
5. **文字换行**：按自然语义分行，避免过长单行

### Step 4：执行脚本

```bash
/Users/zyb/.workbuddy/binaries/python/envs/default/bin/python <脚本路径>
```

### Step 5：上传到 IMA 知识库

按标准流程上传 PNG 文件：

1. preflight-check.cjs 检查
2. check_repeated_names 查重
3. create_media 创建媒体
4. cos-upload.cjs 上传
5. add_knowledge 添加到知识库

## 脚本参考模板

详见 `scripts/add_text_to_comic.py`

关键参数：
- 文字颜色：深紫色系 `(60, 50, 90)`，标题用深色
- 文字背景：半透明白/淡紫色，增加可读性
- 金句区域：淡紫色背景 + 居中显示
- 输出格式：PNG，quality=95

## 儿童绘本风格文字特点

- 语言温和轻柔，适合3-7岁儿童
- 每格文字不超过4行
- 使用可爱亲切的语气
- 结尾附"给小朋友的悄悄话"寓意金句
