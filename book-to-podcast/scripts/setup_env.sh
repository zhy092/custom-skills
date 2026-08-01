#!/usr/bin/env bash
# setup_env.sh — 为本技能创建独立 Python 环境并安装依赖。
# 不污染系统环境：所有包装进 <技能目录>/.venv
#
# 用法:
#   bash setup_env.sh                # 安装核心依赖 + 静态 ffmpeg（imageio-ffmpeg）
#   bash setup_env.sh --with-cloud   # 额外装云端 TTS SDK（可选，脚本本身用 HTTP 即可）
#   bash setup_env.sh --with-ffmpeg  # 兼容性保留：ffmpeg 现已默认安装，此参数仅为占位

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$SKILL_DIR/.venv"

echo "技能目录: $SKILL_DIR"

# ---- 1. 找一个可用的 Python 3.10+ ----------------------------------------
pick_python() {
  # 优先 WorkBuddy 托管的隔离运行时
  for c in "$HOME"/.workbuddy/binaries/python/versions/*/bin/python3; do
    [ -x "$c" ] && { echo "$c"; return; }
  done
  for c in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1; then
      if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
        command -v "$c"; return
      fi
    fi
  done
  echo ""
}

PY="$(pick_python)"
if [ -z "$PY" ]; then
  echo "错误: 找不到 Python 3.10+，请先安装。" >&2
  exit 1
fi
echo "使用 Python: $PY ($("$PY" --version 2>&1))"

# ---- 2. 建 venv ----------------------------------------------------------
if [ ! -d "$VENV" ]; then
  echo "创建虚拟环境: $VENV"
  "$PY" -m venv "$VENV"
fi
VPY="$VENV/bin/python"
[ -x "$VPY" ] || VPY="$VENV/Scripts/python.exe"   # Windows Git Bash

"$VPY" -m pip install --quiet --upgrade pip

# ---- 3. 依赖 -------------------------------------------------------------
echo "安装核心依赖…"
"$VPY" -m pip install --quiet \
  "edge-tts>=6.1.9" \
  "pypdf>=4.2.0" \
  "cryptography>=3.1" \
  "EbookLib>=0.18" \
  "beautifulsoup4>=4.12" \
  "python-docx>=1.1.0" \
  "charset-normalizer>=3.3" \
  "imageio-ffmpeg>=0.5.1"   # 静态 ffmpeg：停顿/响度/BGM/章节标记所必需，无需系统 ffmpeg

# lxml 只是 HTML 解析加速项，装不上不影响功能（脚本用内置 html.parser）
"$VPY" -m pip install --quiet "lxml>=5.0" 2>/dev/null \
  && echo "  + lxml（HTML 解析加速）" \
  || echo "  - lxml 不可用，改用内置 html.parser（不影响功能）"

# 校验
"$VPY" - <<'EOF'
import sys
missing = []
for mod, pkg in [("edge_tts","edge-tts"), ("pypdf","pypdf"), ("cryptography","cryptography"),
                 ("ebooklib","EbookLib"), ("bs4","beautifulsoup4"), ("docx","python-docx"),
                 ("charset_normalizer","charset-normalizer")]:
    try:
        __import__(mod)
    except ImportError:
        missing.append(pkg)
if missing:
    print("❌ 以下依赖缺失: " + ", ".join(missing)); sys.exit(1)
print("✅ 核心依赖校验通过")
EOF

if [ "${1:-}" = "--with-cloud" ]; then
  echo "安装云端 TTS SDK（可选）…"
  "$VPY" -m pip install --quiet "dashscope>=1.20.0" || echo "  dashscope 安装失败，可忽略（脚本走 HTTP）"
fi

# imageio-ffmpeg 现已在核心依赖中默认安装；此分支仅作兼容性占位。
if [ "${1:-}" = "--with-ffmpeg" ]; then
  "$VPY" -c "import imageio_ffmpeg; print('  + imageio-ffmpeg 已内置（默认安装），无需额外操作')" 2>/dev/null \
    || "$VPY" -m pip install --quiet "imageio-ffmpeg>=0.5.1"
fi

# ---- 4. ffmpeg 检查 ------------------------------------------------------
echo ""
ff_found=""
if command -v ffmpeg >/dev/null 2>&1; then
  ff_found="$(command -v ffmpeg)"
elif "$VPY" -c "import imageio_ffmpeg, os; os.path.exists(imageio_ffmpeg.get_ffmpeg_exe())" 2>/dev/null; then
  ff_found="$("$VPY" -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())" 2>/dev/null)"
fi
if [ -n "$ff_found" ]; then
  echo "✅ ffmpeg: $ff_found"
else
  echo "⚠️  未检测到 ffmpeg —— 没有它也能出音频，但会失去："
  echo "     精确停顿控制 / 响度标准化 / BGM 垫乐 / ID3 标签 / 章节标记"
  echo "   本应已随核心依赖安装 imageio-ffmpeg；若缺失可重跑: bash setup_env.sh"
  echo "   或系统安装:"
  case "$(uname -s)" in
    Darwin) echo "     brew install ffmpeg" ;;
    Linux)  echo "     sudo apt install ffmpeg   # 或 dnf/pacman" ;;
    *)      echo "     https://ffmpeg.org/download.html" ;;
  esac
fi

# ---- 5. calibre 检查（仅 mobi/azw3 需要）---------------------------------
if command -v ebook-convert >/dev/null 2>&1; then
  echo "✅ calibre ebook-convert: 可解析 mobi/azw3/fb2"
else
  echo "ℹ️  未装 calibre —— 只影响 .mobi/.azw3/.fb2 格式"
  echo "   需要时: brew install --cask calibre  /  sudo apt install calibre"
fi

echo ""
echo "✅ 环境就绪"
echo "   解释器: $VPY"
echo "   后续所有脚本都用它执行，例如："
echo "     $VPY $SKILL_DIR/scripts/extract_book.py <书> --out <工作目录>"
