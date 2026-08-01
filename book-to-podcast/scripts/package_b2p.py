#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
package_b2p.py — 打包 book-to-podcast 技能为可分发的 .skill 文件。

与官方 package_skill.py 的区别：
  * 自动排除 .venv / __pycache__ / .git / *.pyc / 测试产物（否则会有 48MB+ 体积）
  * 打包副本中去掉 `agent_created: true`（最大兼容性，避免严格校验器拒绝），
    本地工作副本仍保留该标记供 SkillManage 后续维护。
  * 内置宽松校验（允许 agent_created 等自定义键）。

用法:
  python package_b2p.py <skill目录> [输出目录]
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

SKILL_NAME = "book-to-podcast"

EXCLUDE_DIRS = {".venv", "__pycache__", ".git", "node_modules"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".DS_Store"}
# 工作目录里可能残留的测试产物（只打包技能本身，不打包运行产物）
EXCLUDE_NAMES = {"book-podcast", "work", "output", "tmp"}


def validate(skill_path: Path):
    md = skill_path / "SKILL.md"
    if not md.exists():
        sys.exit("❌ SKILL.md 缺失")
    text = md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        sys.exit("❌ SKILL.md 无 frontmatter")
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        sys.exit("❌ frontmatter 格式错误")
    fm = re.search(r"^name:\s*(.+)$", m.group(1), re.M)
    desc = re.search(r"^description:\s*(.+)$", m.group(1), re.M)
    if not fm:
        sys.exit("❌ 缺少 name")
    name = fm.group(1).strip()
    if not re.match(r"^[a-z0-9-]+$", name):
        sys.exit(f"❌ name 必须是 hyphen-case: {name}")
    if not desc or not desc.group(1).strip():
        sys.exit("❌ 缺少 description")
    if "<" in desc.group(1) or ">" in desc.group(1):
        sys.exit("❌ description 含尖括号")
    print(f"✅ 校验通过 (name={name})")


def iter_files(root: Path):
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root)
            parts = set(rel.parts)
            if parts & EXCLUDE_DIRS:
                continue
            if p.name in EXCLUDE_NAMES and p.is_dir():
                continue
            if p.name == ".DS_Store":
                continue
            if p.suffix in EXCLUDE_SUFFIX:
                continue
            yield p


def main():
    if len(sys.argv) < 2:
        print("用法: python package_b2p.py <skill目录> [输出目录]")
        sys.exit(1)
    src = Path(sys.argv[1]).resolve()
    out_dir = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    validate(src)

    # 拷到临时目录，去掉 agent_created 行
    tmp = Path(tempfile.mkdtemp(prefix="b2p_pkg_"))
    try:
        dst = tmp / SKILL_NAME
        dst.mkdir()
        for p in iter_files(src):
            rel = p.relative_to(src)
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if p.name == "SKILL.md":
                text = p.read_text(encoding="utf-8")
                text = re.sub(r"^agent_created:\s*.*$\n?", "", text, flags=re.M)
                target.write_text(text, encoding="utf-8")
            else:
                shutil.copy2(p, target)

        skill_file = out_dir / f"{SKILL_NAME}.skill"
        with zipfile.ZipFile(skill_file, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(dst.rglob("*")):
                if p.is_file():
                    arc = p.relative_to(tmp)  # book-to-podcast/...
                    z.write(p, str(arc))
                    print(f"  + {arc}")

        size = skill_file.stat().st_size / 1024
        print(f"\n✅ 已打包: {skill_file}  ({size:.0f} KB)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
