#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tts_render.py — 把对话脚本 JSON 渲染成逐句音频片段。多引擎可切换。

引擎与鉴权环境变量:
  edge     免费、无需 Key、40+ 语言 300+ 音色            (默认)
  aliyun   阿里云百炼 Qwen-TTS      DASHSCOPE_API_KEY
  volcano  火山引擎豆包 TTS         VOLC_TTS_APPID / VOLC_TTS_TOKEN [/ VOLC_TTS_CLUSTER]
  minimax  MiniMax Speech          MINIMAX_API_KEY / MINIMAX_GROUP_ID
  openai   OpenAI 兼容 TTS          OPENAI_API_KEY [/ OPENAI_BASE_URL]
  say      macOS 系统离线合成        无需 Key（音质一般，仅兜底）

用法:
  python tts_render.py --script ep01.script.json --out-dir ep01/segments
  python tts_render.py --script ep01.script.json --out-dir out --engine aliyun
  python tts_render.py --list-voices --engine edge --lang zh
  python tts_render.py --script ep01.script.json --out-dir out --dry-run
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------

def _http_json(url: str, payload: dict, headers: dict, timeout: int = 120) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download(url: str, dest: Path, timeout: int = 120) -> None:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        dest.write_bytes(resp.read())


def _env(name: str, engine: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        sys.exit(f"[{engine}] 缺少环境变量 {name}。请先 export {name}=...")
    return v


# --------------------------------------------------------------------------
# 引擎实现: synth(text, voice, opts, dest) -> 实际写出的文件后缀
# --------------------------------------------------------------------------

def synth_edge(text: str, voice: str, opts: dict, dest: Path) -> str:
    """微软 Edge 大声朗读（免费）。"""
    try:
        import asyncio
        import edge_tts
    except ImportError:
        sys.exit("[edge] 缺少 edge-tts。请运行 scripts/setup_env.sh")

    kw = {}
    if opts.get("rate"):   kw["rate"] = opts["rate"]      # 例 "+8%"
    if opts.get("pitch"):  kw["pitch"] = opts["pitch"]    # 例 "-2Hz"
    if opts.get("volume"): kw["volume"] = opts["volume"]  # 例 "+0%"

    async def run():
        comm = edge_tts.Communicate(text, voice, **kw)
        await comm.save(str(dest.with_suffix(".mp3")))

    asyncio.run(run())
    return ".mp3"


def synth_aliyun(text: str, voice: str, opts: dict, dest: Path) -> str:
    """阿里云百炼 Qwen-TTS。中文自然度第一梯队，性价比高。"""
    key = _env("DASHSCOPE_API_KEY", "aliyun")
    model = opts.get("model") or os.environ.get("DASHSCOPE_TTS_MODEL", "qwen3-tts-flash")
    payload = {"model": model, "input": {"text": text, "voice": voice}}
    if opts.get("language_type"):
        payload["input"]["language_type"] = opts["language_type"]
    if opts.get("instructions"):        # qwen3-tts-instruct-* 支持自然语言控场
        payload["input"]["instructions"] = opts["instructions"]

    data = _http_json(
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
        payload,
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    url = (data.get("output") or {}).get("audio", {}).get("url")
    if not url:
        raise RuntimeError(f"阿里云未返回音频: {json.dumps(data, ensure_ascii=False)[:400]}")
    ext = ".wav" if ".wav" in url.split("?")[0].lower() else ".mp3"
    _download(url, dest.with_suffix(ext))
    return ext


def synth_volcano(text: str, voice: str, opts: dict, dest: Path) -> str:
    """火山引擎（豆包）TTS。国内延迟最低。"""
    appid = _env("VOLC_TTS_APPID", "volcano")
    token = _env("VOLC_TTS_TOKEN", "volcano")
    cluster = os.environ.get("VOLC_TTS_CLUSTER", "volcano_tts")
    payload = {
        "app": {"appid": appid, "token": token, "cluster": cluster},
        "user": {"uid": "book-to-podcast"},
        "audio": {
            "voice_type": voice,
            "encoding": "mp3",
            "speed_ratio": float(opts.get("speed_ratio", 1.0)),
            "volume_ratio": float(opts.get("volume_ratio", 1.0)),
            "pitch_ratio": float(opts.get("pitch_ratio", 1.0)),
        },
        "request": {"reqid": str(uuid.uuid4()), "text": text, "operation": "query"},
    }
    data = _http_json(
        "https://openspeech.bytedance.com/api/v1/tts", payload,
        {"Authorization": f"Bearer;{token}", "Content-Type": "application/json"},
    )
    if not data.get("data"):
        raise RuntimeError(f"火山引擎未返回音频: {json.dumps(data, ensure_ascii=False)[:400]}")
    dest.with_suffix(".mp3").write_bytes(base64.b64decode(data["data"]))
    return ".mp3"


def synth_minimax(text: str, voice: str, opts: dict, dest: Path) -> str:
    """MiniMax Speech。情感表现力强。"""
    key = _env("MINIMAX_API_KEY", "minimax")
    gid = _env("MINIMAX_GROUP_ID", "minimax")
    model = opts.get("model") or os.environ.get("MINIMAX_TTS_MODEL", "speech-02-hd")
    payload = {
        "model": model, "text": text, "stream": False,
        "voice_setting": {
            "voice_id": voice,
            "speed": float(opts.get("speed", 1.0)),
            "vol": float(opts.get("vol", 1.0)),
            "pitch": int(opts.get("pitch_step", 0)),
        },
        "audio_setting": {"sample_rate": 32000, "bitrate": 128000,
                          "format": "mp3", "channel": 1},
    }
    data = _http_json(
        f"https://api.minimax.chat/v1/t2a_v2?GroupId={gid}", payload,
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    hexed = (data.get("data") or {}).get("audio")
    if not hexed:
        raise RuntimeError(f"MiniMax 未返回音频: {json.dumps(data, ensure_ascii=False)[:400]}")
    dest.with_suffix(".mp3").write_bytes(bytes.fromhex(hexed))
    return ".mp3"


def synth_openai(text: str, voice: str, opts: dict, dest: Path) -> str:
    """OpenAI / 任意 OpenAI 兼容端点。"""
    key = _env("OPENAI_API_KEY", "openai")
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    payload = {
        "model": opts.get("model", "gpt-4o-mini-tts"),
        "voice": voice, "input": text, "response_format": "mp3",
    }
    if opts.get("instructions"):
        payload["instructions"] = opts["instructions"]
    if opts.get("speed"):
        payload["speed"] = float(opts["speed"])
    req = urllib.request.Request(
        f"{base}/audio/speech",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        dest.with_suffix(".mp3").write_bytes(resp.read())
    return ".mp3"


def synth_say(text: str, voice: str, opts: dict, dest: Path) -> str:
    """macOS 内置 say，离线兜底。"""
    if not shutil.which("say"):
        sys.exit("[say] 仅 macOS 可用")
    out = dest.with_suffix(".aiff")
    cmd = ["say", "-o", str(out), "--data-format=LEI16@22050"]
    if voice:
        cmd += ["-v", voice]
    if opts.get("wpm"):
        cmd += ["-r", str(opts["wpm"])]
    subprocess.run(cmd + [text], check=True)
    return ".aiff"


ENGINES = {
    "edge": synth_edge, "aliyun": synth_aliyun, "volcano": synth_volcano,
    "minimax": synth_minimax, "openai": synth_openai, "say": synth_say,
}

# 各引擎并发上限：云端引擎压太狠会被限流
DEFAULT_CONCURRENCY = {"edge": 4, "aliyun": 4, "volcano": 4,
                       "minimax": 3, "openai": 6, "say": 2}


# --------------------------------------------------------------------------
# 文本预处理
# --------------------------------------------------------------------------

_MD = [
    (re.compile(r"\*\*(.+?)\*\*"), r"\1"), (re.compile(r"\*(.+?)\*"), r"\1"),
    (re.compile(r"`(.+?)`"), r"\1"), (re.compile(r"~~(.+?)~~"), r"\1"),
    (re.compile(r"\[(.+?)\]\(.+?\)"), r"\1"), (re.compile(r"^#{1,6}\s*", re.M), ""),
    (re.compile(r"^>\s*", re.M), ""),
]


def clean_for_tts(text: str) -> str:
    """去掉朗读时会被念出来的 Markdown 记号和舞台提示。"""
    text = re.sub(r"[（(]\s*(?:笑|停顿|轻笑|叹气|sigh|laughs?|pause)\s*[)）]", "…", text)
    text = re.sub(r"[\[【]\s*(?:BGM|音效|SFX|sfx)[^\]】]*[\]】]", "", text)
    for pat, rep in _MD:
        text = pat.sub(rep, text)
    return re.sub(r"\s+", " ", text).strip()


def resolve_voice(spk_cfg, engine: str) -> tuple[str, dict]:
    """speaker 配置支持三种写法: 字符串 / {voice,...} / {edge:...,aliyun:...}"""
    if isinstance(spk_cfg, str):
        return spk_cfg, {}
    if not isinstance(spk_cfg, dict):
        raise ValueError(f"无法解析的音色配置: {spk_cfg!r}")
    opts = {k: v for k, v in spk_cfg.items()
            if k not in ("voice", *ENGINES.keys())}
    voice = spk_cfg.get(engine) or spk_cfg.get("voice")
    if isinstance(voice, dict):
        opts.update({k: v for k, v in voice.items() if k != "voice"})
        voice = voice.get("voice")
    if not voice:
        raise ValueError(f"speaker 缺少 {engine} 引擎的音色: {spk_cfg!r}")
    return voice, opts


# --------------------------------------------------------------------------
# 音色清单
# --------------------------------------------------------------------------

def list_voices(engine: str, lang: str | None) -> None:
    if engine != "edge":
        print(f"[提示] {engine} 的音色列表请查阅 references/tts_engines.md")
        return
    try:
        import asyncio
        import edge_tts
    except ImportError:
        sys.exit("[edge] 缺少 edge-tts。请运行 scripts/setup_env.sh")

    voices = asyncio.run(edge_tts.list_voices())
    rows = [v for v in voices
            if not lang or v["Locale"].lower().startswith(lang.lower())]
    rows.sort(key=lambda v: (v["Locale"], v["ShortName"]))
    print(f"共 {len(rows)} 个音色" + (f"（筛选 {lang}）" if lang else ""))
    for v in rows:
        tags = ", ".join((v.get("VoiceTag") or {}).get("ContentCategories", []) or [])
        pers = ", ".join((v.get("VoiceTag") or {}).get("VoicePersonalities", []) or [])
        print(f"  {v['ShortName']:<34} {v['Gender']:<7} {tags:<24} {pers}")


# --------------------------------------------------------------------------
# 主渲染
# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="对话脚本 → 逐句音频片段")
    ap.add_argument("--script", help="脚本 JSON 路径")
    ap.add_argument("--out-dir", help="片段输出目录")
    ap.add_argument("--engine", default=None, help=f"引擎: {'/'.join(ENGINES)}")
    ap.add_argument("--concurrency", type=int, default=None)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--force", action="store_true", help="忽略缓存，全部重渲")
    ap.add_argument("--dry-run", action="store_true", help="只统计字数与预估费用")
    ap.add_argument("--list-voices", action="store_true")
    ap.add_argument("--lang", default=None, help="配合 --list-voices 过滤语言")
    args = ap.parse_args()

    if args.list_voices:
        list_voices(args.engine or "edge", args.lang)
        return
    if not args.script or not args.out_dir:
        ap.error("需要 --script 和 --out-dir")

    script = json.loads(Path(args.script).expanduser().read_text(encoding="utf-8"))
    engine = args.engine or script.get("engine") or "edge"
    if engine not in ENGINES:
        sys.exit(f"未知引擎 {engine}，可选: {'/'.join(ENGINES)}")

    voices_cfg = script.get("voices") or {}
    lines = script.get("lines") or []
    if not lines:
        sys.exit("脚本里没有 lines")

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # 组装任务
    tasks = []
    for i, line in enumerate(lines, 1):
        text = clean_for_tts(line.get("text", ""))
        if not text:
            continue
        spk = line.get("speaker", "host")
        if spk not in voices_cfg:
            sys.exit(f"第 {i} 行 speaker='{spk}' 未在 voices 中定义（已定义: {list(voices_cfg)}）")
        voice, opts = resolve_voice(voices_cfg[spk], engine)
        opts = {**opts, **(line.get("tts_opts") or {})}
        if line.get("voice"):
            voice = line["voice"]
        sig = hashlib.sha1(
            f"{engine}|{voice}|{json.dumps(opts, sort_keys=True)}|{text}".encode()
        ).hexdigest()[:12]
        tasks.append({
            "index": i, "speaker": spk, "voice": voice, "opts": opts,
            "text": text, "chars": len(text), "hash": sig,
            "stem": out_dir / f"seg_{i:04d}",
            "pause_after": float(line.get("pause_after", 0.0)),
            "chapter": line.get("chapter"),
        })

    total_chars = sum(t["chars"] for t in tasks)
    print(f"[脚本] {script.get('title', Path(args.script).stem)}")
    print(f"  引擎 {engine} | {len(tasks)} 句 | {total_chars:,} 字符 | 角色 {list(voices_cfg)}")

    if args.dry_run:
        price = {"edge": 0.0, "say": 0.0, "aliyun": 200.0,
                 "volcano": 250.0, "minimax": 300.0, "openai": 430.0}
        cost = total_chars / 1_000_000 * price.get(engine, 0.0)
        print(f"  预估费用 ≈ ¥{cost:.2f}（按公开单价粗算，仅供参考）")
        for t in tasks[:6]:
            print(f"    {t['index']:>3} [{t['speaker']}/{t['voice']}] {t['text'][:56]}")
        return

    # 断点续渲：命中缓存直接跳过
    cache = {}
    manifest_path = out_dir / "render_manifest.json"
    if manifest_path.exists() and not args.force:
        try:
            for s in json.loads(manifest_path.read_text(encoding="utf-8")).get("segments", []):
                cache[s["index"]] = s
        except Exception:
            pass

    conc = args.concurrency or DEFAULT_CONCURRENCY.get(engine, 4)
    synth = ENGINES[engine]
    results: dict[int, dict] = {}
    done_n = [0]

    def work(t: dict) -> dict:
        prev = cache.get(t["index"])
        if prev and prev.get("hash") == t["hash"]:
            f = Path(prev["file"])
            if f.exists() and f.stat().st_size > 0:
                done_n[0] += 1
                return {**prev, "cached": True, "chapter": t.get("chapter")}

        last_err = None
        for attempt in range(1, args.retries + 1):
            try:
                ext = synth(t["text"], t["voice"], t["opts"], t["stem"])
                path = t["stem"].with_suffix(ext)
                if not path.exists() or path.stat().st_size == 0:
                    raise RuntimeError("生成了空文件")
                done_n[0] += 1
                print(f"  [{done_n[0]}/{len(tasks)}] seg_{t['index']:04d} "
                      f"{t['speaker']:<8} {t['chars']:>4}字 → {path.name}")
                return {"index": t["index"], "speaker": t["speaker"], "voice": t["voice"],
                        "text": t["text"], "chars": t["chars"], "hash": t["hash"],
                        "file": str(path), "pause_after": t["pause_after"],
                        "chapter": t.get("chapter"), "cached": False}
            except Exception as e:                     # noqa: BLE001
                last_err = e
                if attempt < args.retries:
                    time.sleep(1.5 * attempt)
        raise RuntimeError(f"seg_{t['index']:04d} 渲染失败（{args.retries} 次重试）: {last_err}")

    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=conc) as pool:
        futs = {pool.submit(work, t): t for t in tasks}
        for fut in cf.as_completed(futs):
            r = fut.result()
            results[r["index"]] = r

    segments = [results[k] for k in sorted(results)]
    cached_n = sum(1 for s in segments if s.get("cached"))
    manifest = {
        "episode_id": script.get("episode_id", Path(args.script).stem),
        "title": script.get("title", ""),
        "language": script.get("language", ""),
        "engine": engine,
        "segment_count": len(segments),
        "total_chars": total_chars,
        "default_gap": script.get("default_gap", 0.35),
        "segments": segments,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    print(f"[完成] {len(segments)} 段（复用缓存 {cached_n}）耗时 {time.time() - t0:.1f}s")
    print(f"  清单: {manifest_path}")
    print(f"  下一步: python merge_audio.py --manifest {manifest_path} --out <输出.mp3>")


if __name__ == "__main__":
    main()
