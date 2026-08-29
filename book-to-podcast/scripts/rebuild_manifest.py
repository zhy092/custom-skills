"""
从已存在的 seg_*.mp3 片段反向生成 render_manifest.json。

场景：渲染进程被中断（超时/OOM/kill），片段都已落盘但 manifest 没写成。
此时重跑 tts_render 会再次发起请求（还可能再挂），不如直接补 manifest。

复用 tts_render.py 的 resolve_voice / clean_for_tts，保证 hash、voice 与
原渲染完全一致，merge_audio 可直接使用。

用法：
    python rebuild_manifest.py <工作目录> <集号>   例: python rebuild_manifest.py . 03
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

# 基于脚本自身位置推导技能目录，拷贝/换机后依然可用
SKILL_SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def load_tts_render():
    spec = importlib.util.spec_from_file_location(
        'b2p_tts_render', os.path.join(SKILL_SCRIPTS, 'tts_render.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find_clean(mod):
    """tts_render 里的文本清洗函数（版本差异兜底）"""
    for name in ('clean_for_tts', 'clean_text', 'sanitize_text'):
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn
    return lambda t: t


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit('用法: python rebuild_manifest.py <工作目录> <集号>')
    work = Path(sys.argv[1]).expanduser().resolve()
    ep = sys.argv[2].lower()
    # 兼容 "03" 与 "ep03" 两种写法
    if not ep.startswith('ep'):
        ep = 'ep' + ep.zfill(2)

    script_path = work / 'scripts' / f'{ep}.script.json'
    out_dir = work / 'audio' / ep
    if not script_path.exists():
        raise SystemExit(f'找不到脚本: {script_path}')
    if not out_dir.is_dir():
        raise SystemExit(f'找不到片段目录: {out_dir}')

    mod = load_tts_render()
    clean = find_clean(mod)
    resolve_voice = mod.resolve_voice

    data = json.loads(script_path.read_text(encoding='utf-8'))
    engine = data.get('engine', 'edge')
    voices_cfg = data['voices']
    default_gap = float(data.get('default_gap', 0.35))

    segments, missing = [], []
    for i, line in enumerate(data['lines'], start=1):
        text = clean(line.get('text', ''))
        spk = line.get('speaker', 'host')
        voice, opts = resolve_voice(voices_cfg[spk], engine)
        if line.get('voice'):
            voice = line['voice']
        opts = {**opts, **(line.get('tts_opts') or {})}
        sig = hashlib.sha1(
            f"{engine}|{voice}|{json.dumps(opts, sort_keys=True)}|{text}".encode()
        ).hexdigest()[:12]
        f = out_dir / f'seg_{i:04d}.mp3'
        if not f.exists() or f.stat().st_size == 0:
            missing.append(f.name)
        segments.append({
            'index': i,
            'speaker': spk,
            'voice': voice,
            'text': text,
            'chars': len(text),
            'hash': sig,
            'file': str(f),
            'pause_after': float(line.get('pause_after', 0.0)),
            'chapter': line.get('chapter'),
            'cached': True,
        })

    if missing:
        print(f'[中止] 以下片段缺失或为 0 字节，请先修复: {missing}')
        sys.exit(1)

    manifest = {
        'episode_id': data.get('episode_id', ep),
        'title': data.get('title', ep),
        'language': data.get('language', 'zh'),
        'engine': engine,
        'segment_count': len(segments),
        'total_chars': sum(s['chars'] for s in segments),
        'default_gap': default_gap,
        'segments': segments,
    }
    dest = out_dir / 'render_manifest.json'
    dest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'[完成] {dest}')
    print(f'  {len(segments)} 段 | {manifest["total_chars"]} 字符')


if __name__ == '__main__':
    main()
