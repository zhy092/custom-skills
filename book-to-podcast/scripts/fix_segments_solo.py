"""
逐句重渲 0 字节片段（规避 edge-tts 并发挂起）。

背景：批量渲染时 concurrency 调高（如 4）偶发请求无限挂起 —— 不报错、不超时，
整个进程卡死数小时。删掉 0 字节文件后整集重跑往往再次卡住同一句。

解法：把每个失败句单独抽成"最小脚本"，用 concurrency=1 逐句重渲，
再按原 seg 编号复制回原位。单句渲染 2-3 秒完成，稳定可靠。

用法：
    python fix_segments_solo.py [工作目录] [最大轮数]

默认处理 <工作目录>/audio/ep*/ 下所有 0 字节 seg_*.mp3。
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

# 基于脚本自身位置推导，避免硬编码
_HERE = os.path.dirname(os.path.abspath(__file__))
_SKILL = os.path.dirname(_HERE)
PY = os.path.join(_SKILL, '.venv', 'bin', 'python')
if not os.path.exists(PY):
    PY = sys.executable
RENDER = os.path.join(_HERE, 'tts_render.py')


def zero_segments(audio_root: str) -> list[str]:
    out = []
    for f in sorted(glob.glob(os.path.join(audio_root, 'ep*', 'seg_*.mp3'))):
        if os.path.getsize(f) == 0:
            out.append(f)
    return out


def render_solo(script_path: str, ep: str, line_idx: int, dest: str) -> bool:
    """把单句抽成最小脚本渲染，再复制到 dest。返回是否成功。"""
    with open(script_path, encoding='utf-8') as fh:
        data = json.load(fh)
    mini = {
        'episode_id': f'{ep}solo',
        'title': 'solo',
        'language': data.get('language', 'zh'),
        'engine': data.get('engine', 'edge'),
        'default_gap': data.get('default_gap', 0.35),
        'voices': data['voices'],
        'lines': [data['lines'][line_idx]],
    }
    tmpdir = tempfile.mkdtemp(prefix='solo_')
    mini_path = os.path.join(tmpdir, 'mini.json')
    with open(mini_path, 'w', encoding='utf-8') as fh:
        json.dump(mini, fh, ensure_ascii=False)

    out_dir = os.path.join(tmpdir, 'out')
    proc = subprocess.run(
        [PY, RENDER, '--script', mini_path, '--out-dir', out_dir,
         '--retries', '6', '--concurrency', '1'],
        capture_output=True, text=True, timeout=180,
    )
    produced = os.path.join(out_dir, 'seg_0001.mp3')
    ok = os.path.exists(produced) and os.path.getsize(produced) > 0
    if ok:
        shutil.copy(produced, dest)
    shutil.rmtree(tmpdir, ignore_errors=True)
    return ok


def main() -> None:
    work = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    max_rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    work = os.path.abspath(work)
    audio_root = os.path.join(work, 'audio')
    scripts_dir = os.path.join(work, 'scripts')

    for r in range(1, max_rounds + 1):
        zeros = zero_segments(audio_root)
        print(f'\n=== 第 {r} 轮：{len(zeros)} 个 0 字节片段 ===')
        if not zeros:
            print('全部片段正常。')
            return

        fixed, failed = 0, []
        for zf in zeros:
            ep = os.path.basename(os.path.dirname(zf))          # ep03
            seg = os.path.basename(zf)                          # seg_0053.mp3
            idx = int(re.search(r'seg_(\d+)', seg).group(1)) - 1  # 0-based 行号
            script_path = os.path.join(scripts_dir, f'{ep}.script.json')
            if not os.path.exists(script_path):
                failed.append((zf, '缺脚本'))
                continue
            try:
                os.remove(zf)
                if render_solo(script_path, ep, idx, zf):
                    print(f'  [修复] {ep}/{seg} (line {idx})')
                    fixed += 1
                else:
                    failed.append((zf, '渲染失败'))
            except subprocess.TimeoutExpired:
                failed.append((zf, '单句渲染超时'))
            except Exception as exc:  # noqa: BLE001
                failed.append((zf, str(exc)))

        print(f'本轮修复 {fixed} 个，失败 {len(failed)} 个')
        for f, reason in failed:
            print(f'  [失败] {f} — {reason}')

    remain = zero_segments(audio_root)
    print(f'\n最终剩余 {len(remain)} 个 0 字节片段' if remain else '\n全部片段渲染完成。')
    sys.exit(1 if remain else 0)


if __name__ == '__main__':
    main()
