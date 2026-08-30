#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_feed.py — 扫描成品目录，生成播客 RSS 订阅源 + 索引页。

产出的 podcast.xml 可直接用小宇宙/Apple Podcasts/PocketCasts 等
「添加自定义 RSS」订阅（把目录挂到任意静态 HTTP 服务即可）。

用法:
  python make_feed.py --dir <成品目录> --title "《XXX》拆书电台" \
      --base-url https://example.com/podcast --author "AI 主播"
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import shutil
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
FFPROBE = shutil.which("ffprobe")


def duration_of(path: Path) -> str:
    if FFPROBE:
        try:
            r = subprocess.run(
                [FFPROBE, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nw=1:nk=1", str(path)],
                capture_output=True, text=True, check=True)
            total = int(float(r.stdout.strip()))
            h, rem = divmod(total, 3600)
            m, s = divmod(rem, 60)
            return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
        except Exception:
            pass
    # 兜底：用 mutagen 读取时长（无需 ffprobe）
    try:
        from mutagen.mp3 import MP3
        total = int(MP3(str(path)).info.length)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
    except Exception:
        return ""


def main() -> None:
    ap = argparse.ArgumentParser(description="成品目录 → 播客 RSS + 索引")
    ap.add_argument("--dir", required=True, help="含 ep*.mp3 的成品目录")
    ap.add_argument("--title", required=True, help="节目名")
    ap.add_argument("--base-url", default="", help="音频公网前缀，留空则用相对路径")
    ap.add_argument("--author", default="AI 拆书电台")
    ap.add_argument("--description", default="", help="节目简介")
    ap.add_argument("--language", default="zh-cn")
    ap.add_argument("--cover-url", default="", help="封面图 URL")
    args = ap.parse_args()

    root_dir = Path(args.dir).expanduser().resolve()
    mp3s = sorted(root_dir.glob("*.mp3"))
    if not mp3s:
        raise SystemExit(f"{root_dir} 下没有 mp3")

    ET.register_namespace("itunes", ITUNES)
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = args.title
    ET.SubElement(channel, "link").text = args.base_url or "."
    ET.SubElement(channel, "language").text = args.language
    ET.SubElement(channel, "description").text = args.description or args.title
    ET.SubElement(channel, f"{{{ITUNES}}}author").text = args.author
    ET.SubElement(channel, f"{{{ITUNES}}}summary").text = args.description or args.title
    ET.SubElement(channel, f"{{{ITUNES}}}explicit").text = "false"
    if args.cover_url:
        ET.SubElement(channel, f"{{{ITUNES}}}image", {"href": args.cover_url})

    now = datetime.now(timezone.utc)
    index = [f"# {args.title}\n", f"> {args.description}\n" if args.description else "",
             f"共 {len(mp3s)} 集\n"]

    for i, mp3 in enumerate(mp3s):
        # 同名 .md 视为该集 shownotes
        notes_file = mp3.with_suffix(".md")
        notes = notes_file.read_text(encoding="utf-8") if notes_file.exists() else ""
        title = mp3.stem
        for line in notes.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break

        url = f"{args.base_url.rstrip('/')}/{mp3.name}" if args.base_url else mp3.name
        dur = duration_of(mp3)

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "description").text = notes or title
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = f"{args.title}-{mp3.stem}"
        # 按集序递减发布时间，保证播客客户端排序正确
        ET.SubElement(item, "pubDate").text = format_datetime(
            now - timedelta(days=len(mp3s) - i - 1))
        ET.SubElement(item, "enclosure", {
            "url": url, "length": str(mp3.stat().st_size),
            "type": mimetypes.guess_type(mp3.name)[0] or "audio/mpeg"})
        if dur:
            ET.SubElement(item, f"{{{ITUNES}}}duration").text = dur
        ET.SubElement(item, f"{{{ITUNES}}}episode").text = str(i + 1)

        size_mb = mp3.stat().st_size / 1024 / 1024
        index.append(f"\n## {i + 1}. {title}\n")
        index.append(f"- 音频: [`{mp3.name}`](./{mp3.name})"
                     f"{f' · {dur}' if dur else ''} · {size_mb:.1f} MB")
        if notes_file.exists():
            index.append(f"- 文稿: [`{notes_file.name}`](./{notes_file.name})")

    ET.indent(rss, space="  ")
    feed = root_dir / "podcast.xml"
    ET.ElementTree(rss).write(feed, encoding="utf-8", xml_declaration=True)
    (root_dir / "index.md").write_text("\n".join(index) + "\n", encoding="utf-8")

    print(f"[完成] {len(mp3s)} 集")
    print(f"  RSS  : {feed}")
    print(f"  索引 : {root_dir / 'index.md'}")
    if not args.base_url:
        print("  提示 : 未设 --base-url，enclosure 用的是相对路径。"
              "要真正订阅需挂到 HTTP 服务并重新生成。")
        print(f"         本地预览: cd {root_dir} && python -m http.server 8800")


if __name__ == "__main__":
    main()
