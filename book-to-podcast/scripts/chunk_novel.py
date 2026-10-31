#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chunk_novel.py — 长篇小说/三部曲按「册」切块，每块≈1 集播客素材。

与 chunk_book.py 的区别（别混用）：
  chunk_book.py   按结构章节切 1.2 万字小块，供 agent 逐块精读、汇总知识图谱（非虚构书用）
  chunk_novel.py  按「册」边界把整本书切成 N 份 7–9 万字的素材块，一块直接写一集成稿
                  不做摘要素材，也不带 overlap —— 因为小说要连续读，重复会污染情节记忆

典型场景：一本 80 万字的四部曲，你想做 10 集播客 → --episodes 3,4,3
产出：chunks/chunk_001.md … + chunks/map.json（含每块起止偏移、字数、所属册）

用法：
  # 三部曲，按册分配集数（章节号归 1 处自动识别为新一册）
  python3 chunk_novel.py --input books/某书/book.txt --out podcast/某书/chunks \\
      --episodes 4,3,3 --vol-detect chapter-reset

  # 册名靠标题页标记切（如三部曲各有「三体2」「三体3」标题页）
  python3 chunk_novel.py --input book.txt --out chunks --episodes 3,4,4 \\
      --vol-detect "markers:三体2,三体3" --labels "三体1,三体2,三体3"

  # 不分册，整本均分 6 集
  python3 chunk_novel.py --input book.txt --out chunks --episodes 6 --vol-detect none

  # 开头有双栏乱序前言（阅读器抓取常见），从正文标记处起算
  python3 chunk_novel.py ... --skip-to-re $'\\n1\\n科学边界'
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CN_DIGITS = "零一二三四五六七八九"
CHAPTER_RE = re.compile(r"第([一二三四五六七八九十百零]+)([章回])")
SENT_END = "。！？\n”」"


def cn2int(s: str) -> int:
    """中文数字转整数（支持到百位，够章节号用）。"""
    total = section = num = 0
    for ch in s:
        if ch in CN_DIGITS:
            num = CN_DIGITS.index(ch)
        elif ch == "十":
            section += (num or 1) * 10
            num = 0
        elif ch == "百":
            section += (num or 1) * 100
            num = 0
    return section + num


def vol_bounds_chapter_reset(text: str, min_prev: int = 20) -> list[int]:
    """章节号从 N 回到 1 → 判定进入新一册。

    两道过滤，专治阅读器抓取里的假章节号（实测踩过）：
      1. 「第X回」必须独占行尾（否则「第一回出远门」这类正文会被当成章号）；
      2. 认作新册之前，后面 5 个章号里必须出现「第2章」——真正的册首后面一定跟着第2章，
         而正文里偶然冒出的「第一章」不会。
    """
    marks: list[tuple[int, int]] = []
    for m in CHAPTER_RE.finditer(text):
        num = cn2int(m.group(1))
        if not 1 <= num <= 999:
            continue
        if m.group(2) == "回" and (m.end() >= len(text) or text[m.end()] not in "\n\r 　\t"):
            continue          # 「第一回出远门」→ 丢弃
        marks.append((m.start(), num))

    bounds = [0]
    prev = 0
    for i, (pos, num) in enumerate(marks):
        if num == prev + 1:
            prev = num
            continue
        if num == 1 and prev >= min_prev:
            ahead = [n for _, n in marks[i + 1:i + 6]]
            if 2 in ahead:    # 册首后面得有第2章，否则是假章号
                bounds.append(pos)
                prev = 1
    return bounds if len(bounds) > 1 else [0]


def vol_bounds_markers(text: str, markers: list[str]) -> list[int]:
    """按标题页标记字符串切册（标记自身归入新一册）。"""
    bounds = [0]
    for mk in markers:
        pos = text.find(mk)
        if pos > 0:
            bounds.append(pos)
    return sorted(set(bounds))


def snap(text: str, pos: int, lo: int, hi: int, window: int = 500) -> int:
    """把切点挪到最近的句末/换行之后，避免把一句话劈开。"""
    for d in range(window):
        for p in (pos + d, pos - d):
            if lo < p < hi and text[p - 1] in SENT_END:
                return p
    return pos


def main() -> None:
    ap = argparse.ArgumentParser(description="长篇小说按册切成集级素材块")
    ap.add_argument("--input", required=True, help="book.txt 路径")
    ap.add_argument("--out", required=True, help="输出 chunks 目录")
    ap.add_argument("--episodes", required=True,
                    help="集数：单个数=整本均分（如 6）；逗号列表=按册分配（如 4,3,3）")
    ap.add_argument("--vol-detect", default="chapter-reset",
                    help="chapter-reset | markers:标记1,标记2 | none（默认 chapter-reset）")
    ap.add_argument("--labels", default="", help="册名，逗号分隔（如 第一部,第二部,第三部）")
    ap.add_argument("--skip-to-re", default="", help="从该正则首次匹配处起算（丢掉乱序前言）")
    ap.add_argument("--min-prev", type=int, default=20,
                    help="chapter-reset 判定阈值：章节号回 1 时前一号至少多大（默认 20）")
    args = ap.parse_args()

    text = Path(args.input).expanduser().read_text(encoding="utf-8")
    offset_base = 0
    if args.skip_to_re:
        m = re.search(args.skip_to_re, text)
        if m:
            offset_base = m.start()
            print(f"[前言跳过] 从第 {offset_base} 字起算：{text[offset_base:offset_base + 30]!r}")
            text = text[offset_base:]

    # 册边界
    if args.vol_detect == "none":
        bounds = [0]
    elif args.vol_detect.startswith("markers:"):
        bounds = vol_bounds_markers(text, [x.strip() for x in args.vol_detect[8:].split(",") if x.strip()])
    else:
        bounds = vol_bounds_chapter_reset(text, args.min_prev)
    bounds = bounds + [len(text)]
    n_vol = len(bounds) - 1

    # 集数分配
    ep_spec = [int(x) for x in re.split(r"[,，\s]+", args.episodes.strip()) if x]
    if len(ep_spec) == 1:
        per_vol = [ep_spec[0] // n_vol + (1 if i < ep_spec[0] % n_vol else 0) for i in range(n_vol)]
    elif len(ep_spec) == n_vol:
        per_vol = ep_spec
    else:
        raise SystemExit(
            f"集数({len(ep_spec)} 项) 与识别出的册数({n_vol}) 不匹配：{bounds}\n"
            f"请改用单个总数，或检查 --vol-detect / --min-prev")
    labels = [x.strip() for x in args.labels.split(",") if x.strip()]
    if len(labels) < n_vol:
        labels = labels + [f"第{i + 1}册" for i in range(len(labels), n_vol)]

    print(f"[识别] {n_vol} 册，边界 {bounds}，总字数 {len(text)}，分集 {per_vol}")

    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    for old in list(out.glob("chunk_*.md")) + [out / "map.json"]:
        if old.exists():
            old.unlink()

    cmap, k = [], 0
    for v in range(n_vol):
        lo, hi = bounds[v], bounds[v + 1]
        n = per_vol[v]
        span = hi - lo
        for j in range(n):
            a = lo + span * j // n
            b = lo + span * (j + 1) // n
            if j:
                a = snap(text, a, lo, hi)
            if j < n - 1:
                b = snap(text, b, lo, hi)
            k += 1
            body = text[a:b]
            (out / f"chunk_{k:03d}.md").write_text(body, encoding="utf-8")
            label = f"{labels[v]} 第{j + 1}/{n}段"
            cmap.append({"k": k, "label": label, "vol": v + 1,
                         "start": a + offset_base, "end": b + offset_base, "chars": len(body)})
            print(f"  chunk_{k:03d} {len(body):7d} 字  {label}  首句: {body[:26]}")

    (out / "map.json").write_text(
        json.dumps(cmap, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[完成] {len(cmap)} 块 → {out}/chunk_001.md … + map.json")
    print("  提示：每块直接写一集成稿（4800-5400 字符），不要再把块切成更小的摘要单位")


if __name__ == "__main__":
    main()
