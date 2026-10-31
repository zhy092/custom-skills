#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_and_name.py — 合并一集音频并直接按标题命名，一步到位。

为什么需要它：
  merge_audio.py 只产出 output/ep01.mp3，还要再跑 rename_by_chapter.py 才带上章节名。
  小说/播客类项目希望直接得到「《书名》ep01__创意标题.mp3」，中间忘跑重命名就交了裸名。
  本脚本把「合并 + 命名」合成一步，标题取自 scripts/epNN.script.json 的 title。

命名优先级：
  1. scripts/epNN.script.json 的 title        → 《书名》ep01__创意标题.mp3
  2. episodes.json 的 topic / title（兜底）
  3. 都没有                                    → 《书名》ep01.mp3

用法：
  python3 merge_and_name.py <工作目录> --album "《书名》拆书电台" --prefix "《书名》"
  python3 merge_and_name.py <工作目录> --prefix "《书名》" --only 03 05     # 只合指定集
  python3 merge_and_name.py <工作目录> --prefix "《书名》" --dry-run        # 只看规划不合并
  python3 merge_and_name.py <工作目录> --prefix "《书名》" --out-dir /tmp/t  # 换输出目录（测试用）

可选 --pattern 自定义文件名模板，字段：{prefix}{ep}{title}
  --pattern "{prefix}ep{ep}-{title}.mp3"
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def pick_python() -> str:
    venv = HERE.parent / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else sys.executable


def load_title(work: Path, ep: str) -> str:
    sp = work / "scripts" / f"{ep}.script.json"
    if sp.exists():
        try:
            t = json.loads(sp.read_text(encoding="utf-8")).get("title") or ""
            if t.strip():
                return t.strip()
        except json.JSONDecodeError:
            print(f"  ! {sp.name} JSON 不合法，跳过标题")
    epf = work / "episodes.json"
    if epf.exists():
        try:
            data = json.loads(epf.read_text(encoding="utf-8"))
            items = data.get("episodes", data) if isinstance(data, dict) else data
            for e in items:
                if str(e.get("id", "")).lower() == ep.lower():
                    return str(e.get("topic") or e.get("title") or "").strip()
        except json.JSONDecodeError:
            pass
    return ""


def safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", name).strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="合并 + 按标题命名")
    ap.add_argument("work", help="工作目录（内含 audio/epNN/render_manifest.json）")
    ap.add_argument("--album", default="", help="ID3 专辑名，默认取 --prefix 去掉书名号")
    ap.add_argument("--prefix", default="", help="文件名前缀，如 《书名》")
    ap.add_argument("--pattern", default="{prefix}{ep}__{title}.mp3",
                    help="文件名模板，支持 {prefix}{ep}{title}")
    ap.add_argument("--out-dir", default="output", help="输出子目录（相对工作目录或绝对路径）")
    ap.add_argument("--only", nargs="*", default=None, help="只处理这些集号，如 03 05")
    ap.add_argument("--dry-run", action="store_true", help="只打印规划，不合并")
    args = ap.parse_args()

    work = Path(args.work).expanduser().resolve()
    audio = work / "audio"
    if not audio.is_dir():
        raise SystemExit(f"找不到 {audio}")
    out_dir = Path(args.out_dir)
    out_dir = out_dir if out_dir.is_absolute() else work / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    album = args.album or (args.prefix.strip("《》") + " 拆书电台" if args.prefix else "拆书电台")

    only = {x.lower() for x in args.only} if args.only else None
    eps = [d.name for d in sorted(audio.glob("ep*")) if d.is_dir()]
    eps = [e for e in eps if only is None or e.lower() in only or e[2:] in only]
    if not eps:
        raise SystemExit("没有可处理的集目录")

    py = pick_python()
    merge = HERE / "merge_audio.py"
    if not merge.exists():
        raise SystemExit(f"找不到 {merge}")

    done, plan = [], []
    for ep in eps:
        manifest = audio / ep / "render_manifest.json"
        title = safe(load_title(work, ep))
        fname = args.pattern.format(prefix=args.prefix, ep=ep, title=title)
        fname = re.sub(r"__\.", ".", fname)          # 无标题时不留 "__"
        target = out_dir / safe(fname)
        plan.append((ep, title, target))

    if args.dry_run:
        for ep, title, target in plan:
            mark = "缺 manifest" if not (audio / ep / "render_manifest.json").exists() else "OK"
            print(f"  {ep}  [{mark}]  {target.name}")
        print(f"[dry-run] 共 {len(plan)} 集，未做任何合并")
        return

    for ep, title, target in plan:
        manifest = audio / ep / "render_manifest.json"
        if not manifest.exists():
            print(f"  [跳过] {ep}: 缺 render_manifest.json（可先跑 rebuild_manifest.py）")
            continue
        tmp = out_dir / f"{ep}.mp3"
        r = subprocess.run([py, str(merge), "--manifest", str(manifest), "--out", str(tmp),
                            "--album", album, "--track", ep[2:]],
                           capture_output=True, text=True, cwd=str(work))
        if r.returncode != 0 or not tmp.exists():
            tail = (r.stderr or "").strip().splitlines()[-1:]
            print(f"  [失败] {ep}: {tail}")
            continue
        if tmp != target:
            tmp.replace(target)
        done.append(target.name)
        print(f"  {target.name}  {target.stat().st_size // 1024 // 1024}MB")

    print(f"[完成] {len(done)}/{len(plan)} 集 → {out_dir}")
    if done:
        print("  下一步: make_feed.py --dir <output> --title ... 生成 podcast.xml / index.md")


if __name__ == "__main__":
    main()
