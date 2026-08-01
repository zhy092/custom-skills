#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chunk_book.py — 把 book.txt 按「章节优先、大小兜底」切成可逐块精读的片段。

为什么需要它: 一本 30 万字的书塞不进上下文。切块后 agent 逐块精读并产出
局部笔记，最后再汇总成全书知识图谱 —— 这是唯一可靠的长书处理路径。

输出:
  chunks/chunk_001.md ...   每块带头部元信息(章节/序号/字数)
  chunks/manifest.json      切块清单 + 建议阅读批次

用法:
  python chunk_book.py --work <extract输出目录> [--target-chars 12000] [--overlap 400]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# 句子边界：兼顾中日韩全角标点与拉丁语系标点
_SENT_END = re.compile(r"(?<=[。！？!?；;…])\s*|(?<=[.!?])\s+(?=[A-Z\"'\u201c])")


def split_sentences(text: str) -> list[str]:
    parts = [p for p in _SENT_END.split(text) if p and p.strip()]
    return parts or [text]


def pack(text: str, target: int, overlap: int) -> list[str]:
    """按句子边界打包到接近 target 字符，块间保留 overlap 字符上下文。"""
    if len(text) <= target:
        return [text]

    out: list[str] = []
    for para in re.split(r"\n{2,}", text):
        para = para.strip()
        if not para:
            continue
        if out and len(out[-1]) + len(para) + 2 <= target:
            out[-1] += "\n\n" + para
        elif len(para) <= target:
            out.append(para)
        else:
            # 超长段落 → 退到句子级切分
            buf = ""
            for s in split_sentences(para):
                if buf and len(buf) + len(s) > target:
                    out.append(buf)
                    buf = s
                else:
                    buf += s
            if buf:
                out.append(buf)

    if overlap > 0:
        out = [out[0]] + [
            ("…" + out[i - 1][-overlap:] + "\n\n" + out[i]) for i in range(1, len(out))
        ]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="书籍全文 → 可逐块精读的片段")
    ap.add_argument("--work", required=True, help="extract_book.py 的输出目录")
    ap.add_argument("--target-chars", type=int, default=12000, help="每块目标字符数")
    ap.add_argument("--overlap", type=int, default=400, help="块间重叠字符数")
    ap.add_argument("--batch-size", type=int, default=4, help="建议每批精读几块")
    args = ap.parse_args()

    work = Path(args.work).expanduser().resolve()
    structure = json.loads((work / "structure.json").read_text(encoding="utf-8"))
    text = (work / "book.txt").read_text(encoding="utf-8")

    chunks_dir = work / "chunks"
    chunks_dir.mkdir(exist_ok=True)
    for old in chunks_dir.glob("chunk_*.md"):
        old.unlink()

    records = []
    for ch in structure["chapters"]:
        body = text[ch["start"]:ch["end"]].strip()
        if not body:
            continue
        for i, piece in enumerate(pack(body, args.target_chars, args.overlap), 1):
            idx = len(records) + 1
            name = f"chunk_{idx:03d}.md"
            total_in_ch = "?"
            header = (
                f"<!-- chunk {idx} | 章节 {ch['index']}: {ch['title']} "
                f"| 分片 {i} | {len(piece)} 字 -->\n\n"
            )
            (chunks_dir / name).write_text(header + piece, encoding="utf-8")
            records.append({
                "id": idx,
                "file": f"chunks/{name}",
                "chapter_index": ch["index"],
                "chapter_title": ch["title"],
                "part": i,
                "chars": len(piece),
                "preview": re.sub(r"\s+", " ", piece[:100]),
            })
        # 回填该章总分片数
        for r in records:
            if r["chapter_index"] == ch["index"]:
                r["parts_in_chapter"] = sum(
                    1 for x in records if x["chapter_index"] == ch["index"])

    batches = [
        {"batch": b // args.batch_size + 1,
         "chunks": [r["id"] for r in records[b:b + args.batch_size]]}
        for b in range(0, len(records), args.batch_size)
    ]

    manifest = {
        "book_title": structure["title"],
        "language": structure["language"]["code"],
        "total_chars": structure["total_chars"],
        "chunk_count": len(records),
        "target_chars": args.target_chars,
        "batch_count": len(batches),
        "reading_batches": batches,
        "chunks": records,
    }
    (chunks_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[完成] 切出 {len(records)} 块，分 {len(batches)} 批精读")
    print(f"  目录: {chunks_dir}")
    print(f"  清单: {chunks_dir / 'manifest.json'}")
    print("  提示: 逐批读 chunk 并写局部笔记，切勿一次性全读进上下文")


if __name__ == "__main__":
    main()
