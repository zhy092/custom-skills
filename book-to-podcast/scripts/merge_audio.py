#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_audio.py — 把逐句片段合成为一集完整播客。

有 ffmpeg（推荐）: 精确停顿、响度标准化(-16 LUFS 播客标准)、BGM 垫乐、
                   片头片尾、ID3 标签、章节标记。
无 ffmpeg（兜底）: 纯 Python 直接拼接 MP3 帧，可用但没有停顿控制。

用法:
  python merge_audio.py --manifest segments/render_manifest.json --out ep01.mp3
  python merge_audio.py --manifest ... --out ep01.mp3 --bgm bgm.mp3 --bgm-db -26
  python merge_audio.py --manifest ... --out ep01.mp3 --no-normalize
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _find_ffmpeg() -> str | None:
    """优先系统 ffmpeg；没有就用 imageio-ffmpeg 附带的静态二进制（装在 venv 里，
    不污染系统）。两者都没有时返回 None，走纯 Python 兜底拼接。"""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return exe
    except Exception:
        pass
    return None


FFMPEG = _find_ffmpeg()
FFPROBE = shutil.which("ffprobe")


# --------------------------------------------------------------------------
# 无 ffmpeg 的兜底：直接拼 MP3 帧
# --------------------------------------------------------------------------

def strip_id3(data: bytes) -> bytes:
    """去掉 ID3v2 头与 ID3v1 尾，避免拼接后播放器解析错乱。"""
    if data[:3] == b"ID3" and len(data) > 10:
        size = ((data[6] & 0x7F) << 21) | ((data[7] & 0x7F) << 14) | \
               ((data[8] & 0x7F) << 7) | (data[9] & 0x7F)
        data = data[10 + size:]
    if data[-128:][:3] == b"TAG":
        data = data[:-128]
    return data


def naive_concat(files: list[Path], out: Path) -> None:
    bad = [f for f in files if f.suffix.lower() != ".mp3"]
    if bad:
        sys.exit(f"[无 ffmpeg] 只能拼接 MP3，但有 {len(bad)} 个非 MP3 片段"
                 f"（如 {bad[0].name}）。请安装 ffmpeg 后重试。")
    with out.open("wb") as w:
        for f in files:
            w.write(strip_id3(f.read_bytes()))


# --------------------------------------------------------------------------
# ffmpeg 路径
# --------------------------------------------------------------------------

_TIME_RE = re.compile(r"time=(\d+):(\d\d):(\d\d\.\d+)")


def probe_duration(path: Path) -> float:
    """取音频时长。优先 ffprobe；没有 ffprobe 时用 ffmpeg 解码到 null 读取。"""
    if FFPROBE:
        try:
            r = subprocess.run(
                [FFPROBE, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nw=1:nk=1", str(path)],
                capture_output=True, text=True, check=True)
            return float(r.stdout.strip())
        except Exception:
            pass
    if FFMPEG:
        try:
            r = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path),
                                "-f", "null", "-"],
                               capture_output=True, text=True)
            hits = _TIME_RE.findall(r.stderr)
            if hits:
                h, m, s = hits[-1]
                return int(h) * 3600 + int(m) * 60 + float(s)
        except Exception:
            pass
    return 0.0


def make_silence(seconds: float, tmp: Path, sr: int) -> Path:
    dest = tmp / f"sil_{int(round(seconds * 1000))}.mp3"
    if not dest.exists():
        subprocess.run(
            [FFMPEG, "-v", "error", "-y", "-f", "lavfi",
             "-i", f"anullsrc=r={sr}:cl=mono", "-t", f"{seconds:.3f}",
             "-c:a", "libmp3lame", "-b:a", "64k", str(dest)],
            check=True)
    return dest


def ffmpeg_merge(files: list[Path], out: Path, args, chapters: list[dict]) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="b2p_"))
    try:
        listing = tmp / "concat.txt"
        listing.write_text(
            "\n".join(f"file '{f.as_posix()}'" for f in files) + "\n",
            encoding="utf-8")

        joined = tmp / "joined.mp3"
        subprocess.run(
            [FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0",
             "-i", str(listing), "-c:a", "libmp3lame",
             "-b:a", args.bitrate, "-ar", str(args.sample_rate), "-ac", "1",
             str(joined)],
            check=True)

        stage = joined

        # 片头 / 片尾
        if args.intro or args.outro:
            parts = ([Path(args.intro)] if args.intro else []) + [stage] + \
                    ([Path(args.outro)] if args.outro else [])
            lst2 = tmp / "concat2.txt"
            norm = []
            for p in parts:                     # 统一编码参数再拼，避免参数不一致
                n = tmp / f"n_{len(norm)}_{p.stem}.mp3"
                subprocess.run(
                    [FFMPEG, "-v", "error", "-y", "-i", str(p), "-c:a", "libmp3lame",
                     "-b:a", args.bitrate, "-ar", str(args.sample_rate), "-ac", "1", str(n)],
                    check=True)
                norm.append(n)
            lst2.write_text("\n".join(f"file '{p.as_posix()}'" for p in norm) + "\n",
                            encoding="utf-8")
            stage2 = tmp / "with_bookends.mp3"
            subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0",
                            "-i", str(lst2), "-c", "copy", str(stage2)], check=True)
            stage = stage2

        # BGM 垫乐：循环铺满 + 压低音量 + 首尾淡入淡出
        if args.bgm:
            dur = probe_duration(stage)
            stage3 = tmp / "with_bgm.mp3"
            fade_out_start = max(0.0, dur - 3)
            subprocess.run(
                [FFMPEG, "-v", "error", "-y", "-i", str(stage),
                 "-stream_loop", "-1", "-i", str(Path(args.bgm)),
                 "-filter_complex",
                 f"[1:a]volume={args.bgm_db}dB,afade=t=in:st=0:d=2,"
                 f"afade=t=out:st={fade_out_start:.2f}:d=3[bg];"
                 f"[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0[a]",
                 "-map", "[a]", "-c:a", "libmp3lame", "-b:a", args.bitrate,
                 "-ar", str(args.sample_rate), "-ac", "1", str(stage3)],
                check=True)
            stage = stage3

        # 响度标准化到播客标准
        final_filters = []
        if not args.no_normalize:
            final_filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")

        cmd = [FFMPEG, "-v", "error", "-y", "-i", str(stage)]

        # 章节元数据（只需 ffmpeg 即可 mux，不依赖 ffprobe）
        meta_file = None
        if chapters:
            meta_file = tmp / "meta.txt"
            lines = [";FFMETADATA1"]
            for k, v in _id3(args).items():
                lines.append(f"{k}={v}")
            for ch in chapters:
                lines += ["[CHAPTER]", "TIMEBASE=1/1000",
                          f"START={int(ch['start'] * 1000)}",
                          f"END={int(ch['end'] * 1000)}",
                          f"title={ch['title']}"]
            meta_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
            cmd += ["-i", str(meta_file), "-map_metadata", "1", "-map", "0:a"]

        if final_filters:
            cmd += ["-af", ",".join(final_filters)]
        for k, v in _id3(args).items():
            cmd += ["-metadata", f"{k}={v}"]
        if args.cover and Path(args.cover).exists():
            cmd += ["-i", str(Path(args.cover)), "-map", "0:a", "-map",
                    str(2 if meta_file else 1) + ":v", "-c:v", "copy",
                    "-disposition:v", "attached_pic"]
        cmd += ["-c:a", "libmp3lame", "-b:a", args.bitrate,
                "-ar", str(args.sample_rate), "-ac", "1", str(out)]
        subprocess.run(cmd, check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _id3(args) -> dict:
    m = {}
    if args.title:  m["title"] = args.title
    if args.artist: m["artist"] = args.artist
    if args.album:  m["album"] = args.album
    if args.track:  m["track"] = str(args.track)
    m["genre"] = "Podcast"
    return m


# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="音频片段 → 一集完整播客")
    ap.add_argument("--manifest", required=True, help="tts_render.py 产出的 render_manifest.json")
    ap.add_argument("--out", required=True, help="输出 mp3 路径")
    ap.add_argument("--gap", type=float, default=None, help="默认句间停顿秒数")
    ap.add_argument("--speaker-gap", type=float, default=None,
                    help="换人说话时的额外停顿秒数（默认 gap 的 1.8 倍）")
    ap.add_argument("--bitrate", default="96k")
    ap.add_argument("--sample-rate", type=int, default=44100)
    ap.add_argument("--no-normalize", action="store_true", help="跳过响度标准化")
    ap.add_argument("--bgm", default=None, help="背景音乐文件")
    ap.add_argument("--bgm-db", default="-26", help="BGM 音量增益 dB，默认 -26")
    ap.add_argument("--intro", default=None, help="片头音频")
    ap.add_argument("--outro", default=None, help="片尾音频")
    ap.add_argument("--cover", default=None, help="封面图（jpg/png）")
    ap.add_argument("--title", default=None)
    ap.add_argument("--artist", default=None)
    ap.add_argument("--album", default=None)
    ap.add_argument("--track", default=None)
    args = ap.parse_args()

    mf = Path(args.manifest).expanduser().resolve()
    data = json.loads(mf.read_text(encoding="utf-8"))
    segments = data.get("segments") or []
    if not segments:
        sys.exit("清单里没有片段")

    args.title = args.title or data.get("title") or data.get("episode_id")
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    gap = args.gap if args.gap is not None else float(data.get("default_gap", 0.35))
    spk_gap = args.speaker_gap if args.speaker_gap is not None else round(gap * 1.8, 3)

    if not FFMPEG:
        print("[警告] 未检测到 ffmpeg → 走兜底拼接：无停顿控制、无响度标准化、"
              "无 BGM/标签。\n"
              "        建议安装: macOS `brew install ffmpeg` / "
              "Ubuntu `sudo apt install ffmpeg`", file=sys.stderr)
        naive_concat([Path(s["file"]) for s in segments], out)
        size = out.stat().st_size / 1024 / 1024
        print(f"[完成] {out}  ({size:.1f} MB, {len(segments)} 段)")
        return

    # 交织片段与静音
    tmp_sil = Path(tempfile.mkdtemp(prefix="b2p_sil_"))
    try:
        files: list[Path] = []
        chapters: list[dict] = []
        clock = 0.0
        prev_speaker = None

        for i, s in enumerate(segments):
            f = Path(s["file"])
            if not f.exists():
                sys.exit(f"片段缺失: {f}")

            if i > 0:
                pause = float(s.get("pause_before", 0)) or 0.0
                explicit = float(segments[i - 1].get("pause_after", 0)) or 0.0
                base = explicit or (spk_gap if s.get("speaker") != prev_speaker else gap)
                base = max(base, pause)
                if base > 0.01:
                    files.append(make_silence(base, tmp_sil, args.sample_rate))
                    clock += base

            if s.get("chapter"):
                chapters.append({"title": s["chapter"], "start": clock, "end": clock})
            dur = probe_duration(f)
            clock += dur
            if chapters:
                chapters[-1]["end"] = clock
            files.append(f)
            prev_speaker = s.get("speaker")

        # 章节区间收尾：每章结束于下一章开始
        for j in range(len(chapters) - 1):
            chapters[j]["end"] = chapters[j + 1]["start"]
        if chapters:
            chapters[-1]["end"] = clock

        ffmpeg_merge(files, out, args, chapters)
    finally:
        shutil.rmtree(tmp_sil, ignore_errors=True)

    dur = probe_duration(out)
    size = out.stat().st_size / 1024 / 1024
    mm, ss = divmod(int(dur), 60)
    print(f"[完成] {out}")
    print(f"  时长 {mm}:{ss:02d} | {size:.1f} MB | {len(segments)} 段 | "
          f"停顿 {gap}s/换人 {spk_gap}s" + (f" | {len(chapters)} 个章节标记" if chapters else ""))


if __name__ == "__main__":
    main()
