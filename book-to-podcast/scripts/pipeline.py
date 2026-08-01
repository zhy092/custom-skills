#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
book-to-podcast（一体化技能）—— 拆书播客总控：把「确定性本地步骤」串起来。

子命令：
  prep    抽取 + 切块（阶段 1-2），并打印书的结构摘要
  render  逐集 语音合成 + 拼接（阶段 5-6），再按章节重命名 + 生成 RSS（阶段 6.5/7）

说明：
- 中间需要 LLM 的环节（精读笔记 / 分集编排 / 写对话脚本）由 agent 在 prep 与 render
  之间完成，pipeline 不替你写稿，只把能自动化的体力活一键跑完。
- ima 入库不在此脚本内，由 SKILL.md「阶段 8」描述的 MCP 流程负责（本技能自带零依赖
  cos-upload.cjs 上传器）。
- 路径全部相对本文件所在技能目录解析，技能装在任意路径均可运行。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent   # .../book-to-podcast（技能根）
S = SKILL_DIR / "scripts"
PY = (SKILL_DIR / ".venv" / "bin" / "python").as_posix()  # 技能自带 venv


def run(cmd, cwd=None):
    print("\n$ " + " ".join(str(c) for c in cmd), flush=True)
    r = subprocess.run(cmd, cwd=cwd)
    if r.returncode != 0:
        sys.exit(f"[pipeline] 步骤失败，退出码 {r.returncode}")


def find_scripts(work: Path):
    return sorted(work.glob("scripts/ep[0-9]*.script.json"))


def book_title(work: Path) -> str:
    sj = work / "structure.json"
    if sj.exists():
        try:
            d = json.loads(sj.read_text(encoding="utf-8"))
            return (d.get("title") or "").strip()
        except Exception:
            pass
    return work.name


def cmd_prep(a):
    book = Path(a.book).expanduser().resolve()
    work = Path(a.work).expanduser().resolve() if a.work else \
        (Path.cwd() / "book-podcast" / book.stem)
    work.mkdir(parents=True, exist_ok=True)

    # 阶段 1：抽取
    cmd = [PY, str(S / "extract_book.py"), str(book), "--out", str(work)]
    if a.lang:
        cmd += ["--lang", a.lang]
    run(cmd)

    # 阶段 2：切块
    cmd = [PY, str(S / "chunk_book.py"), "--work", str(work)]
    if a.target_chars:
        cmd += ["--target-chars", str(a.target_chars)]
    if a.overlap:
        cmd += ["--overlap", str(a.overlap)]
    run(cmd)

    # 摘要
    sj = work / "structure.json"
    if sj.exists():
        d = json.loads(sj.read_text(encoding="utf-8"))
        chaps = d.get("chapters") or []
        print("\n=== 抽取完成 ===")
        print("书名   :", d.get("title"))
        print("作者   :", d.get("author"))
        print("语言   :", (d.get("language") or d.get("lang_info") or {}).get("code") if isinstance(d.get("language"), dict) else d.get("language"))
        print("字数   :", d.get("word_count"))
        print("章节数 :", len(chaps))
        print("工作目录:", work)
    print("\n>>> 下一步：agent 基于 chunks/ 精读 → 编排 episodes.json → 写 scripts/epNN.script.json")
    print(">>> 然后运行：python pipeline.py render --work", work)


def cmd_render(a):
    work = Path(a.work).expanduser().resolve()
    scripts = find_scripts(work)
    if not scripts:
        sys.exit(f"[pipeline] 在 {work}/scripts 找不到任何 epNN.script.json，请先写脚本")
    print(f"发现 {len(scripts)} 个脚本，开始合成…")

    title = a.title or book_title(work)
    album = a.album or f"《{title}》拆书电台"

    for i, sc in enumerate(scripts, 1):
        ep = sc.stem  # ep01
        out_dir = work / "audio" / ep
        manifest = out_dir / "render_manifest.json"
        mp3 = work / "output" / f"{ep}.mp3"
        mp3.parent.mkdir(parents=True, exist_ok=True)

        # 阶段 5：语音合成（断点续渲，重跑复用缓存）
        cmd = [PY, str(S / "tts_render.py"), "--script", str(sc), "--out-dir", str(out_dir)]
        if a.engine:
            cmd += ["--engine", a.engine]
        if a.concurrency:
            cmd += ["--concurrency", str(a.concurrency)]
        if a.force:
            cmd += ["--force"]
        run(cmd)

        # 阶段 6：拼接
        cmd = [PY, str(S / "merge_audio.py"), "--manifest", str(manifest),
               "--out", str(mp3), "--album", album, "--track", str(i)]
        run(cmd)

    # 阶段 6.5：按章节重命名（自动套用 ep{NN}_{章节范围}_{主题} 规则）
    run([PY, str(S / "rename_by_chapter.py"), str(work)])

    # 阶段 7：RSS + 索引
    feed = [PY, str(S / "make_feed.py"), "--dir", str(work / "output"),
            "--title", album, "--author", a.author]
    if a.description:
        feed += ["--description", a.description]
    if a.base_url:
        feed += ["--base-url", a.base_url]
    run(feed)

    print("\n=== 渲染完成 ===")
    for mp3 in sorted(work.glob("output/ep*.mp3")):
        print("  ", mp3.name)


def main():
    ap = argparse.ArgumentParser(description="book-to-podcast 总控：prep / render")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("prep", help="抽取+切块，并打印结构摘要")
    p.add_argument("--book", required=True, help="书籍文件路径")
    p.add_argument("--work", help="工作目录（默认 book-podcast/<书名>/）")
    p.add_argument("--lang", help="强制语言码 zh/en/ja…，默认自动识别")
    p.add_argument("--target-chars", type=int, default=12000, help="每块目标字符数")
    p.add_argument("--overlap", type=int, default=400, help="块间重叠字符数")
    p.set_defaults(func=cmd_prep)

    r = sub.add_parser("render", help="逐集合成+拼接+重命名+生成RSS")
    r.add_argument("--work", required=True, help="工作目录")
    r.add_argument("--title", help="书名（默认读 structure.json）")
    r.add_argument("--album", help="专辑名（默认 《书名》拆书电台）")
    r.add_argument("--author", default="AI 拆书电台")
    r.add_argument("--description", help="节目简介")
    r.add_argument("--base-url", help="音频公网前缀，留空用相对路径")
    r.add_argument("--engine", help="TTS 引擎（默认 edge-tts 免费）")
    r.add_argument("--concurrency", type=int, help="并发合成数")
    r.add_argument("--force", action="store_true", help="忽略缓存全部重渲")
    r.set_defaults(func=cmd_render)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
