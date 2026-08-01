#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_book.py — 把任意格式、任意语言的书籍抽取为干净纯文本 + 章节结构。

支持格式:
  .pdf  .epub  .txt  .md  .markdown  .docx  .html/.htm  .rtf
  .mobi .azw .azw3 .fb2  (需系统安装 calibre 的 ebook-convert)

输出 (写入 --out 目录):
  book.txt        清洗后的全文
  structure.json  元数据 + 语言 + 章节表(标题/起止字符偏移/字数)

用法:
  python extract_book.py <书籍路径> --out <输出目录> [--lang zh] [--keep-running-heads]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter
from pathlib import Path

# --------------------------------------------------------------------------
# 语言识别（零依赖，基于 Unicode 字集 + 停用词）
# --------------------------------------------------------------------------

_SCRIPT_RANGES = {
    "han":      [(0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0xF900, 0xFAFF)],
    "kana":     [(0x3040, 0x309F), (0x30A0, 0x30FF)],
    "hangul":   [(0xAC00, 0xD7AF), (0x1100, 0x11FF), (0x3130, 0x318F)],
    "cyrillic": [(0x0400, 0x04FF)],
    "arabic":   [(0x0600, 0x06FF), (0x0750, 0x077F)],
    "hebrew":   [(0x0590, 0x05FF)],
    "devanagari": [(0x0900, 0x097F)],
    "thai":     [(0x0E00, 0x0E7F)],
    "greek":    [(0x0370, 0x03FF)],
    "latin":    [(0x0041, 0x005A), (0x0061, 0x007A), (0x00C0, 0x024F)],
}

# 拉丁语系用高频功能词区分
_LATIN_STOPWORDS = {
    "en": {"the", "and", "of", "to", "in", "that", "is", "it", "for", "with", "as", "was", "on", "are", "this"},
    "es": {"de", "la", "que", "el", "en", "y", "los", "se", "del", "las", "un", "por", "con", "para", "una"},
    "fr": {"de", "la", "le", "et", "les", "des", "en", "un", "du", "une", "que", "dans", "qui", "pour", "pas"},
    "de": {"der", "die", "und", "den", "das", "von", "mit", "ist", "des", "dem", "nicht", "ein", "eine", "auch", "sich"},
    "pt": {"de", "que", "os", "as", "do", "da", "em", "um", "para", "com", "não", "uma", "por", "dos", "das"},
    "it": {"di", "che", "il", "la", "e", "per", "un", "in", "non", "una", "con", "del", "da", "sono", "le"},
    "nl": {"de", "het", "een", "van", "en", "in", "is", "dat", "op", "te", "met", "voor", "niet", "zijn", "aan"},
    "id": {"yang", "dan", "di", "itu", "dengan", "untuk", "tidak", "ini", "dari", "dalam", "akan", "pada", "adalah"},
    "vi": {"của", "và", "là", "có", "được", "trong", "cho", "không", "một", "người", "những", "với", "để"},
    "tr": {"bir", "ve", "bu", "için", "ile", "de", "da", "çok", "olarak", "daha", "ama", "gibi", "kadar"},
}

_LANG_NAMES = {
    "zh": "中文", "ja": "日本語", "ko": "한국어", "ru": "Русский", "ar": "العربية",
    "he": "עברית", "hi": "हिन्दी", "th": "ไทย", "el": "Ελληνικά", "en": "English",
    "es": "Español", "fr": "Français", "de": "Deutsch", "pt": "Português",
    "it": "Italiano", "nl": "Nederlands", "id": "Bahasa Indonesia",
    "vi": "Tiếng Việt", "tr": "Türkçe",
}


def detect_language(text: str) -> dict:
    """返回 {'code','name','confidence','scripts'}。纯启发式，无外部依赖。"""
    sample = text[:200_000]
    counts = Counter()
    for ch in sample:
        cp = ord(ch)
        for script, ranges in _SCRIPT_RANGES.items():
            if any(lo <= cp <= hi for lo, hi in ranges):
                counts[script] += 1
                break
    total = sum(counts.values()) or 1
    ratio = {k: v / total for k, v in counts.items()}

    # CJK 家族优先判定：假名存在即日语；谚文占优即韩语；否则中文
    if ratio.get("kana", 0) > 0.02:
        return {"code": "ja", "name": _LANG_NAMES["ja"], "confidence": round(min(0.99, ratio["kana"] * 6 + 0.4), 2), "scripts": ratio}
    if ratio.get("hangul", 0) > 0.15:
        return {"code": "ko", "name": _LANG_NAMES["ko"], "confidence": round(min(0.99, ratio["hangul"] + 0.3), 2), "scripts": ratio}
    if ratio.get("han", 0) > 0.15:
        return {"code": "zh", "name": _LANG_NAMES["zh"], "confidence": round(min(0.99, ratio["han"] + 0.3), 2), "scripts": ratio}

    for script, code in (("cyrillic", "ru"), ("arabic", "ar"), ("hebrew", "he"),
                         ("devanagari", "hi"), ("thai", "th"), ("greek", "el")):
        if ratio.get(script, 0) > 0.3:
            return {"code": code, "name": _LANG_NAMES[code], "confidence": round(min(0.99, ratio[script] + 0.2), 2), "scripts": ratio}

    # 拉丁字母：用停用词投票
    words = re.findall(r"[a-zà-öø-ÿ]+", sample.lower())
    if words:
        wc = Counter(words)
        scores = {code: sum(wc.get(w, 0) for w in sw) for code, sw in _LATIN_STOPWORDS.items()}
        best = max(scores, key=scores.get)
        top = scores[best]
        if top > 0:
            second = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0
            conf = 0.5 + 0.45 * (1 - second / top) if top else 0.5
            return {"code": best, "name": _LANG_NAMES.get(best, best), "confidence": round(conf, 2), "scripts": ratio}

    return {"code": "unknown", "name": "unknown", "confidence": 0.0, "scripts": ratio}


# --------------------------------------------------------------------------
# 各格式读取
# --------------------------------------------------------------------------

def _require(mod: str, pip_name: str | None = None):
    try:
        return __import__(mod)
    except ImportError:
        sys.exit(f"[缺少依赖] 需要 {pip_name or mod}。请先运行 scripts/setup_env.sh")


def read_pdf(path: Path) -> tuple[list[str], dict, list]:
    _require("pypdf")
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for p in reader.pages:
        try:
            pages.append(p.extract_text() or "")
        except Exception:
            pages.append("")

    meta = {}
    try:
        info = reader.metadata or {}
        meta = {"title": (info.get("/Title") or "").strip(),
                "author": (info.get("/Author") or "").strip()}
    except Exception:
        pass

    # 从 PDF 书签提取章节标题（比正则可靠得多）
    outline_titles = []
    try:
        def walk(items, depth=0):
            for it in items:
                if isinstance(it, list):
                    walk(it, depth + 1)
                else:
                    title = getattr(it, "title", None)
                    if title and depth <= 1:
                        outline_titles.append(str(title).strip())
        walk(reader.outline)
    except Exception:
        pass

    return pages, meta, outline_titles


def read_epub(path: Path) -> tuple[list[str], dict, list]:
    _require("ebooklib")
    _require("bs4", "beautifulsoup4")
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup

    book = epub.read_epub(str(path))
    meta = {}
    try:
        t = book.get_metadata("DC", "title")
        a = book.get_metadata("DC", "creator")
        meta = {"title": t[0][0] if t else "", "author": a[0][0] if a else ""}
    except Exception:
        pass

    sections, titles = [], []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        for bad in soup(["script", "style"]):
            bad.decompose()
        head = soup.find(["h1", "h2", "h3"])
        title = head.get_text(" ", strip=True) if head else ""
        text = soup.get_text("\n", strip=True)
        if len(text) < 30:          # 跳过封面/版权等碎片页
            continue
        if title:
            titles.append(title)
            # 保证章节标题独占一行，便于后续定位
            if not text.startswith(title):
                text = title + "\n" + text
        sections.append(text)
    return sections, meta, titles


def read_docx(path: Path) -> tuple[list[str], dict, list]:
    _require("docx", "python-docx")
    import docx

    d = docx.Document(str(path))
    blocks, titles = [], []
    for p in d.paragraphs:
        txt = p.text.strip()
        if not txt:
            continue
        style = (p.style.name or "").lower()
        if style.startswith("heading") or style in ("title", "subtitle"):
            titles.append(txt)
        blocks.append(txt)
    meta = {"title": (d.core_properties.title or ""), "author": (d.core_properties.author or "")}
    return ["\n".join(blocks)], meta, titles


def read_html(path: Path) -> tuple[list[str], dict, list]:
    _require("bs4", "beautifulsoup4")
    from bs4 import BeautifulSoup

    raw = _read_bytes_as_text(path)
    soup = BeautifulSoup(raw, "html.parser")
    for bad in soup(["script", "style", "nav", "footer"]):
        bad.decompose()
    titles = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2"])]
    title = soup.title.get_text(strip=True) if soup.title else ""
    return [soup.get_text("\n", strip=True)], {"title": title, "author": ""}, titles


def _read_bytes_as_text(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8", "utf-8-sig"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    try:  # 非 UTF-8（常见于中文 GBK / 日文 Shift-JIS 旧书）
        from charset_normalizer import from_bytes
        best = from_bytes(data).best()
        if best:
            return str(best)
    except ImportError:
        pass
    for enc in ("gb18030", "big5", "shift_jis", "euc-kr", "cp1251", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def read_txt(path: Path) -> tuple[list[str], dict, list]:
    return [_read_bytes_as_text(path)], {"title": path.stem, "author": ""}, []


def convert_with_calibre(path: Path) -> Path:
    """mobi/azw3/fb2 等交给 calibre 转 epub。"""
    exe = shutil.which("ebook-convert")
    if not exe:
        sys.exit(
            f"[无法解析 {path.suffix}] 需要 calibre 的 ebook-convert。\n"
            "  macOS : brew install --cask calibre\n"
            "  Linux : sudo apt install calibre\n"
            "或先手动把书转成 epub / pdf / txt 再重试。"
        )
    tmp = Path(tempfile.mkdtemp()) / (path.stem + ".epub")
    subprocess.run([exe, str(path), str(tmp)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return tmp


# --------------------------------------------------------------------------
# 清洗
# --------------------------------------------------------------------------

def strip_running_heads(pages: list[str], min_pages: int = 6) -> list[str]:
    """删除 PDF 每页重复出现的页眉/页脚（书名、章名、页码）。"""
    if len(pages) < min_pages:
        return pages
    head_c, foot_c = Counter(), Counter()
    for pg in pages:
        lines = [l.strip() for l in pg.splitlines() if l.strip()]
        if not lines:
            continue
        head_c[lines[0]] += 1
        foot_c[lines[-1]] += 1
    threshold = max(3, len(pages) * 0.35)
    bad_heads = {k for k, v in head_c.items() if v >= threshold and len(k) < 80}
    bad_foots = {k for k, v in foot_c.items() if v >= threshold and len(k) < 80}

    out = []
    for pg in pages:
        lines = pg.splitlines()
        while lines and not lines[0].strip():
            lines.pop(0)
        if lines and lines[0].strip() in bad_heads:
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        if lines and lines[-1].strip() in bad_foots:
            lines.pop()
        out.append("\n".join(lines))
    return out


_PAGE_NUM_RE = re.compile(r"^\s*[-—–\[(]?\s*\d{1,4}\s*[-—–\])]?\s*$")


def clean_text(text: str, lang: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00ad", "")                       # 软连字符
    text = re.sub(r"[ \t\u00a0]+", " ", text)

    lines = [l for l in text.split("\n") if not _PAGE_NUM_RE.match(l)]
    text = "\n".join(lines)

    # 英文类：修复跨行断词 "exam-\nple" -> "example"
    if lang not in ("zh", "ja", "ko", "th"):
        text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
        # 段内换行合并为空格（保留空行作为段落分隔）
        text = re.sub(r"(?<![.!?:;\"'\)\]])\n(?!\n)(?=[a-zà-öø-ÿ])", " ", text)
    else:
        # CJK：段内换行直接去掉（中日韩不用空格分词）
        text = re.sub(r"(?<=[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af，、；：）」』】])\n(?!\n)"
                      r"(?=[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af（「『【])", "", text)

    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --------------------------------------------------------------------------
# 章节切分
# --------------------------------------------------------------------------

# 强信号：明确的章节标记，误命中率极低
_CHAPTER_PATTERNS_STRONG = [
    r"^#{1,3}\s+\S.*$",                                                  # Markdown 标题
    r"^第\s*[0-9０-９一二三四五六七八九十百千零〇两]+\s*[章回节節篇部讲講课課](?:\s|$|[:：、.．\-—　]).*$",  # 中文
    r"^第\s*[0-9０-９一二三四五六七八九十百]+\s*[話话](?:\s|$|[:：、.．\-—　]).*$",       # 日文
    r"^제\s*[0-9]+\s*[장부편](?:\s|$|[:：.\-—]).*$",                        # 韩文
    r"^(?:CHAPTER|Chapter)\s+(?:\d+|[IVXLCDM]+|[A-Z][a-z]+)\b.*$",
    r"^(?:PART|Part|BOOK|Book)\s+(?:\d+|[IVXLCDM]+|[A-Z][a-z]+)\b.*$",
    r"^(?:Capítulo|CAPÍTULO|Chapitre|CHAPITRE|Kapitel|KAPITEL|Capitolo|Hoofdstuk|Глава|ГЛАВА|Bab|Bölüm)\s+[\dIVXLC]+.*$",
    r"^(?:前言|序言|序章|引言|导论|導論|绪论|緒論|后记|後記|结语|結語|结论|結論|附录|附錄|致谢|致謝|尾声|尾聲|译者序|自序|推荐序)\s*$",
    r"^(?:Introduction|INTRODUCTION|Preface|PREFACE|Foreword|FOREWORD|Prologue|PROLOGUE|Conclusion|CONCLUSION|Epilogue|EPILOGUE|Afterword|AFTERWORD|Appendix|APPENDIX)\s*$",
]
# 弱信号："1. 标题"。在带编号列表的书里会大量误命中，仅当强信号不足时启用
_CHAPTER_PATTERNS_WEAK = [
    r"^\s*\d{1,2}\s*[.、．]\s+\S.{2,60}$",
]

_RE_STRONG = re.compile("|".join(f"(?:{p})" for p in _CHAPTER_PATTERNS_STRONG), re.MULTILINE)
_RE_ALL = re.compile(
    "|".join(f"(?:{p})" for p in _CHAPTER_PATTERNS_STRONG + _CHAPTER_PATTERNS_WEAK),
    re.MULTILINE)


def _scan(regex, text: str) -> list[tuple[int, str]]:
    out = []
    for m in regex.finditer(text):
        title = m.group(0).strip().lstrip("#").strip()
        if title:
            out.append((m.start(), title))
    return out


def detect_chapters(text: str, known_titles: list[str] | None = None) -> list[dict]:
    """返回 [{index,title,start,end,chars}]。优先用书签/TOC 标题定位。"""
    marks: list[tuple[int, str]] = []

    if known_titles:
        seen = set()
        cursor = 0
        for t in known_titles:
            t = t.strip()
            if not t or len(t) > 120 or t in seen:
                continue
            seen.add(t)
            pos = text.find(t, cursor)
            if pos == -1:
                pos = text.find(t)          # 顺序对不上时全局兜底
            if pos != -1:
                marks.append((pos, t))
                cursor = pos + len(t)

    # 书签命中太少 → 回退到正则：先用强信号，不够再加弱信号
    if len(marks) < 3:
        marks = _scan(_RE_STRONG, text)
        if len(marks) < 3:
            marks = _scan(_RE_ALL, text)
        else:
            # 强信号够用时，若加上弱信号不会导致章节碎片化，则一并采纳
            with_weak = _scan(_RE_ALL, text)
            if len(with_weak) <= max(len(marks) * 1.5, len(text) / 3000):
                marks = with_weak

    marks.sort(key=lambda x: x[0])
    # 仅去除同位置/相邻行的重复命中；不能按大间距过滤，
    # 否则「很短的前言」后面紧跟的第一章会被误吃掉
    deduped: list[tuple[int, str]] = []
    for pos, title in marks:
        if deduped and pos - deduped[-1][0] < 40:
            continue
        deduped.append((pos, title))

    if not deduped:
        return [{"index": 1, "title": "全文", "start": 0, "end": len(text), "chars": len(text)}]

    chapters = []
    if deduped[0][0] > 500:      # 首个标题之前还有正文
        chapters.append({"index": 1, "title": "开篇", "start": 0,
                         "end": deduped[0][0], "chars": deduped[0][0]})
    for i, (pos, title) in enumerate(deduped):
        end = deduped[i + 1][0] if i + 1 < len(deduped) else len(text)
        chapters.append({"index": len(chapters) + 1, "title": title,
                         "start": pos, "end": end, "chars": end - pos})
    return chapters


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------

READERS = {
    ".pdf": read_pdf, ".epub": read_epub, ".docx": read_docx,
    ".html": read_html, ".htm": read_html, ".xhtml": read_html,
    ".txt": read_txt, ".md": read_txt, ".markdown": read_txt, ".rtf": read_txt,
}
CALIBRE_EXTS = {".mobi", ".azw", ".azw3", ".fb2", ".lit", ".pdb", ".djvu"}


def main() -> None:
    ap = argparse.ArgumentParser(description="书籍 → 纯文本 + 章节结构")
    ap.add_argument("book", help="书籍文件路径")
    ap.add_argument("--out", required=True, help="输出目录")
    ap.add_argument("--lang", default=None, help="强制指定语言码(zh/en/ja...)，默认自动识别")
    ap.add_argument("--keep-running-heads", action="store_true", help="保留 PDF 页眉页脚")
    args = ap.parse_args()

    src = Path(args.book).expanduser().resolve()
    if not src.exists():
        sys.exit(f"文件不存在: {src}")

    ext = src.suffix.lower()
    if ext in CALIBRE_EXTS:
        print(f"[转换] {ext} → epub (calibre)…", file=sys.stderr)
        src = convert_with_calibre(src)
        ext = ".epub"

    reader = READERS.get(ext)
    if not reader:
        sys.exit(f"不支持的格式: {ext}。支持 {sorted(READERS) + sorted(CALIBRE_EXTS)}")

    print(f"[解析] {src.name}", file=sys.stderr)
    parts, meta, titles = reader(src)

    if ext == ".pdf" and not args.keep_running_heads:
        parts = strip_running_heads(parts)

    raw = "\n\n".join(p for p in parts if p and p.strip())
    if len(raw.strip()) < 200:
        sys.exit("[失败] 几乎没抽到文字。若是扫描版 PDF，请先做 OCR"
                 "（如 ocrmypdf in.pdf out.pdf）后重试。")

    lang_info = detect_language(raw)
    if args.lang:
        lang_info = {"code": args.lang, "name": _LANG_NAMES.get(args.lang, args.lang),
                     "confidence": 1.0, "scripts": lang_info["scripts"], "forced": True}

    text = clean_text(raw, lang_info["code"])
    chapters = detect_chapters(text, titles)

    out = Path(args.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / "book.txt").write_text(text, encoding="utf-8")

    cjk = lang_info["code"] in ("zh", "ja", "ko")
    structure = {
        "source_file": str(Path(args.book).expanduser().resolve()),
        "format": ext,
        "title": (meta.get("title") or Path(args.book).stem).strip(),
        "author": (meta.get("author") or "").strip(),
        "language": lang_info,
        "total_chars": len(text),
        # 估算朗读时长: 中日韩约 260 字/分钟, 拉丁语系约 160 词/分钟
        "est_read_minutes": round(len(text) / 260 if cjk else len(text.split()) / 160),
        "chapter_count": len(chapters),
        "chapters": chapters,
        "text_file": str(out / "book.txt"),
    }
    (out / "structure.json").write_text(
        json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[完成] {structure['title']}", file=sys.stderr)
    print(f"  语言   : {lang_info['name']} ({lang_info['code']}, 置信 {lang_info['confidence']})", file=sys.stderr)
    print(f"  字数   : {len(text):,}  ≈ 朗读 {structure['est_read_minutes']} 分钟", file=sys.stderr)
    print(f"  章节   : {len(chapters)}", file=sys.stderr)
    print(f"  输出   : {out}", file=sys.stderr)
    for c in chapters[:12]:
        print(f"    {c['index']:>3}. {c['title'][:56]}  ({c['chars']:,} 字)", file=sys.stderr)
    if len(chapters) > 12:
        print(f"    … 还有 {len(chapters) - 12} 章", file=sys.stderr)


if __name__ == "__main__":
    main()
