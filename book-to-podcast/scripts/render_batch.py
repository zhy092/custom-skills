"""
串行渲染多集，每集带超时保护，避免单句挂起拖垮整批。

背景：edge-tts 在并发较高时偶发请求无限挂起（不报错、不超时）。
批量 for 循环一旦卡在某句，后续所有集都不会执行。

设计：
  1. 逐集调用 tts_render.py，每集 subprocess timeout（默认 900s）
  2. 超时/异常都记录并继续下一集，不中断整批
  3. 全部跑完后，删除 0 字节片段并逐句重渲（复用 fix_segments_solo 的逻辑）

用法：
    python render_batch.py <工作目录> [集号...]
    python render_batch.py . 04 05 06
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys

# 基于脚本自身位置推导，避免硬编码
_HERE = os.path.dirname(os.path.abspath(__file__))
_SKILL = os.path.dirname(_HERE)
PY = os.path.join(_SKILL, '.venv', 'bin', 'python')
if not os.path.exists(PY):
    PY = sys.executable
RENDER = os.path.join(_HERE, 'tts_render.py')

TIMEOUT = int(os.environ.get('RENDER_TIMEOUT', '900'))
CONCURRENCY = os.environ.get('RENDER_CONCURRENCY', '2')


def zero_count(audio_root: str, ep: str) -> int:
    d = os.path.join(audio_root, ep)
    return sum(
        1 for f in glob.glob(os.path.join(d, 'seg_*.mp3'))
        if os.path.getsize(f) == 0
    )


def render_ep(work: str, ep: str) -> str:
    script = os.path.join(work, 'scripts', f'{ep}.script.json')
    outdir = os.path.join(work, 'audio', ep)
    if not os.path.exists(script):
        return '缺脚本，跳过'
    proc = subprocess.run(
        [PY, RENDER, '--script', script, '--out-dir', outdir,
         '--retries', '8', '--concurrency', CONCURRENCY],
        capture_output=True, text=True, timeout=TIMEOUT, cwd=work,
    )
    tail = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
    return (tail[-1] if tail else f'exit={proc.returncode}')[:110]


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit('用法: python render_batch.py <工作目录> <集号...>  例: 04 05 06')
    work = os.path.abspath(sys.argv[1])
    # 兼容 "04" 与 "ep04" 两种写法
    eps = [e if e.lower().startswith('ep') else 'ep' + e.zfill(2)
           for e in sys.argv[2:]]
    audio_root = os.path.join(work, 'audio')

    for ep in eps:
        print(f'\n=== 渲染 {ep} ===', flush=True)
        try:
            print(f'  {render_ep(work, ep)}', flush=True)
        except subprocess.TimeoutExpired:
            print(f'  [超时] {ep} 超过 {TIMEOUT}s，交由修复步骤逐句补齐', flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f'  [异常] {ep}: {exc}', flush=True)
        n = zero_count(audio_root, ep)
        print(f'  {ep} 剩余 0 字节片段: {n}', flush=True)

    print('\n=== 逐句补修 0 字节片段 ===', flush=True)
    fixer = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fix_segments_solo.py')
    subprocess.run([PY, fixer, work, '3'], cwd=work)


if __name__ == '__main__':
    main()
