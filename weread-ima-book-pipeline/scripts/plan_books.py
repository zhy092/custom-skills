#!/usr/bin/env python3
"""批量评估候选书单：搜索 → 取 bookId/评分 → 查重（文件夹/本地/书架）→ 出表。

输入：txt（每行书名）或直接命令行多个书名
用法:
  python3 plan_books.py candidates.txt --json state/candidates.json
  python3 plan_books.py "活着" "长安的荔枝"
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import find_books as fb  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    argv = sys.argv[1:]
    json_out = None
    pos = []
    i = 0
    while i < len(argv):
        if argv[i] == "--json":
            json_out = argv[i + 1] if i + 1 < len(argv) else None
            i += 2
            continue
        pos.append(argv[i])
        i += 1
    if not pos:
        print(__doc__)
        return
    if len(pos) == 1 and pos[0].endswith(".txt"):
        titles = [l.strip() for l in open(pos[0], encoding="utf-8") if l.strip()]
    else:
        titles = pos

    kbs, done, (shelf, _) = fb.kb_folders(), fb.local_done(), fb.shelf_ids()
    rows = []
    for t in titles:
        try:
            hits = fb.search(t, 3)
        except Exception as e:
            print(f"!! {t} 搜索失败 {str(e)[:40]}")
            continue
        b = hits[0] if hits else None
        if not b:
            print(f"-  {t}：搜索无结果")
            continue
        n = fb.norm(b["title"])
        flags = []
        if any(n and (n in k or k in n) for k in done):
            flags.append("已做完")
        if any(n and (n in k or k in n) for k in kbs):
            flags.append("已有文件夹")
        if b["bookId"] in shelf:
            flags.append("在书架")
        b["want"] = t
        b["status"] = " / ".join(flags) if flags else "新"
        rows.append(b)
        mark = "✓" if b["status"] == "新" else "·"
        print(f'{mark} {t:<18} → {b["title"][:26]:<28} {b["score"] or "-":>5}分  {b["status"]}')

    if json_out:
        p = json_out
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        json.dump(rows, open(p, "w"), ensure_ascii=False, indent=1)
        print(f"\n已写入 {p}（{len(rows)} 本，其中新书 {sum(1 for r in rows if r['status']=='新')} 本）")


if __name__ == "__main__":
    main()
