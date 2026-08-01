#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rename_by_chapter.py — 把 output/ 下的成品按 episodes.json 的章节信息，
自动重命名为「ep{NN}_{章节范围}_{主题}.mp3」格式（含同名 .md）。

用法:
  python rename_by_chapter.py <工作目录>

读取 <工作目录>/episodes.json，对每集取 id / chapter_range / topic：
  - ep01.mp3  -> ep01_第1章_会计基本等式与资产负债表.mp3
  - ep01.md   -> ep01_第1章_会计基本等式与资产负债表.md
若 episodes.json 缺字段，用 title 兜底；都没有则保持原名。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ILLEGAL = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def sanitize(s: str) -> str:
    return ILLEGAL.sub(" ", s).strip()


def main() -> None:
    if len(sys.argv) > 1:
        work = Path(sys.argv[1]).expanduser().resolve()
    else:
        work = Path.cwd()
    out = work / "output"
    epf = work / "episodes.json"
    if not out.is_dir():
        raise SystemExit(f"找不到输出目录：{out}")
    if not epf.exists():
        raise SystemExit("缺少 episodes.json，无法按章节重命名。")

    data = json.loads(epf.read_text(encoding="utf-8"))
    ep_list = data.get("episodes", data) if isinstance(data, dict) else data
    by_id = {str(e.get("id", "")).lower(): e for e in ep_list}

    count = 0
    for mp3 in sorted(out.glob("ep*.mp3")):
        m = re.match(r"(ep\d+)", mp3.stem, re.IGNORECASE)
        if not m:
            continue
        eid = m.group(1).lower()
        e = by_id.get(eid)
        if not e:
            print(f"  {mp3.name}: episodes.json 无对应条目，跳过")
            continue
        cr = sanitize(str(e.get("chapter_range") or e.get("chapter") or ""))
        tp = sanitize(str(e.get("topic") or e.get("title") or ""))
        if not (cr or tp):
            print(f"  {mp3.name}: 无 chapter_range/topic，保持原名")
            continue
        new_stem = f"{m.group(1)}_{cr}_{tp}"
        new_mp3 = out / f"{new_stem}{mp3.suffix}"
        md = mp3.with_suffix(".md")
        mp3.rename(new_mp3)
        if md.exists():
            md.rename(out / f"{new_stem}.md")
        print(f"  {mp3.name} -> {new_mp3.name}")
        count += 1

    print(f"\n重命名 {count} 个文件完成。")
    print("随后请重新运行 make_feed.py 生成 podcast.xml 与 index.md，使文件名/标题一致。")


if __name__ == "__main__":
    main()
