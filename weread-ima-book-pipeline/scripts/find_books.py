#!/usr/bin/env python3
"""按关键词找书 + 查重（ima 文件夹 / 本地成品 / 书架），输出候选清单。

用法:
  python3 find_books.py "行为经济学" [--limit 15] [--json out.json]
  python3 find_books.py --shelf                # 只列书架现状

查重口径（README 第 5 节）：书名归一化（去《》、标点、空格、全半角）后做包含比对。
"""
import glob
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ima_openapi as ima  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIES = "/tmp/wr_cookies3.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def norm(s):
    return ima.norm(s)


def wr_get(path):
    if not os.path.exists(COOKIES):
        raise SystemExit("缺登录态：先跑 python3 scripts/wr_session.py")
    ck = {c["name"]: c["value"] for c in json.load(open(COOKIES))}
    hdr = "; ".join(f"{k}={v}" for k, v in ck.items())
    req = urllib.request.Request("https://weread.qq.com" + path,
                                 headers={"Cookie": hdr, "User-Agent": UA,
                                          "Accept": "application/json",
                                          "Referer": "https://weread.qq.com/"})
    return json.loads(urllib.request.build_opener(
        urllib.request.ProxyHandler({})).open(req, timeout=25).read())


def kb_folders():
    return {norm(f["name"]): f for f in ima.folders()}


def local_done():
    done = {}
    for d in glob.glob(os.path.join(ROOT, "podcast", "*")):
        mp3 = glob.glob(os.path.join(d, "output", "*.mp3"))
        if mp3:
            done[norm(os.path.basename(d))] = len(mp3)
    return done


def shelf_ids():
    try:
        d = wr_get("/web/shelf/sync")
        return {b["bookId"] for b in d.get("books", [])}, d.get("bookCount")
    except Exception:
        return set(), 0


def search(kw, limit=15):
    d = wr_get("/web/search/global?keyword=" + urllib.parse.quote(kw))
    out = []
    for item in (d.get("books") or [])[:limit]:
        b = item.get("bookInfo") or {}
        raw = b.get("newRating") or 0
        score = round(raw / 10, 1) if raw and raw > 100 else (raw or None)
        out.append({
            "bookId": b.get("bookId"),
            "title": b.get("title"),
            "author": b.get("author"),
            "publisher": b.get("publisher"),
            "price": b.get("price"),
            "score": score,
            "label": (b.get("newRatingDetail") or {}).get("title"),
            "readerLink": b.get("readerLink"),
            "intro": (b.get("intro") or "")[:70],
        })
    return out


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    if args[0] == "--shelf":
        ids, n = shelf_ids()
        print(f"书架共 {n} 本")
        return
    kw = args[0]
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else 15

    kbs, done, (ids, _) = kb_folders(), local_done(), shelf_ids()
    print(f"基准：ima 文件夹 {len(kbs)} 个 / 本地成品 {len(done)} 本 / 书架已读\n")

    rows = search(kw, limit)
    print(f"「{kw}」候选 {len(rows)} 本\n")
    for i, b in enumerate(rows, 1):
        t = norm(b["title"])
        flags = []
        if any(t and (t in k or k in t) for k in done):
            flags.append("已做完")
        if any(t and (t in k or k in t) for k in kbs):
            flags.append("已有文件夹")
        if b["bookId"] in ids:
            flags.append("在书架")
        b["status"] = " / ".join(flags) if flags else "新"
        meta = " · ".join(x for x in [
            b["author"],
            b["label"],
            f'{b["score"]}分' if b["score"] else None,
            f'¥{b["price"]}' if b["price"] else None,
            b["publisher"][:12] if b["publisher"] else None,
        ] if x)
        print(f'{i}. {b["title"]}')
        print(f'   {meta}')
        print(f'   状态：{b["status"]}   id={b["bookId"]}')
    if "--json" in args:
        p = args[args.index("--json") + 1]
        json.dump(rows, open(p, "w"), ensure_ascii=False, indent=1)
        print(f"\n已写入 {p}")


if __name__ == "__main__":
    main()
