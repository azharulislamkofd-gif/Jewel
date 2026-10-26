#!/usr/bin/env python3
"""Turn a still image into a cinematic MP4 with smooth Ken Burns camera moves.

Usage:
    python3 tools/make_video.py <source.png> <output.mp4> [--w 1920] [--h 1080] [--fps 30]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from PIL import Image

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def ease_in_out(t: float) -> float:
    """Smoothstep-ish easing so camera moves feel weighty, not linear."""
    return t * t * (3.0 - 2.0 * t)


# Each shot: (duration_seconds, (x0, y0, x1, y1) start, (x0, y0, x1, y1) end)
# Coordinates are normalised 0..1 against the source canvas.
SHOTS = [
    # 1. Establishing: slow push in from wide
    (6.5, (0.000, 0.000, 1.000, 1.000), (0.130, 0.075, 0.870, 0.925)),
    # 2. Detail: drift across the pedestal / product hero area
    (5.5, (0.235, 0.170, 0.765, 0.830), (0.355, 0.135, 0.885, 0.795)),
    # 3. Close-up: tight crop, gentle rise
    (5.5, (0.300, 0.400, 0.700, 0.900), (0.325, 0.190, 0.725, 0.690)),
    # 4. Slide across the gadget row
    (5.0, (0.060, 0.330, 0.560, 0.955), (0.440, 0.330, 0.940, 0.955)),
    # 5. Final pull back to wide
    (5.5, (0.250, 0.145, 0.750, 0.770), (0.000, 0.000, 1.000, 1.000)),
]

FADE_IN_FRAMES = 21
FADE_OUT_FRAMES = 33


def build_canvas(src: Path, target_ratio: float, work_w: int) -> Image.Image:
    """Cover-crop the source to the target aspect ratio at high resolution."""
    img = Image.open(src).convert("RGB")
    sw, sh = img.size
    src_ratio = sw / sh
    if src_ratio > target_ratio:
        new_w = int(round(sh * target_ratio))
        left = (sw - new_w) // 2
        img = img.crop((left, 0, left + new_w, sh))
    else:
        new_h = int(round(sw / target_ratio))
        top = (sh - new_h) // 2
        img = img.crop((0, top, sw, top + new_h))
    cw, ch = img.size
    if cw < work_w:
        scale = work_w / cw
        img = img.resize((work_w, int(round(ch * scale))), Image.LANCZOS)
    return img


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--w", type=int, default=1920)
    ap.add_argument("--h", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--crf", type=int, default=19)
    args = ap.parse_args()

    out_w, out_h, fps = args.w, args.h, args.fps
    if out_w % 2 or out_h % 2:
        print("width/height must be even for yuv420p", file=sys.stderr)
        return 2

    # Oversample the working canvas so zooms stay crisp (avoid upscale blur).
    work_w = max(out_w * 2, 3000)
    canvas = build_canvas(args.source, out_w / out_h, work_w)
    CW, CH = canvas.size
    print(f"[info] canvas {CW}x{CH} -> output {out_w}x{out_h} @ {fps}fps", file=sys.stderr)

    total_seconds = sum(s[0] for s in SHOTS)
    total_frames = int(round(total_seconds * fps))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG, "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{out_w}x{out_h}", "-r", str(fps),
        "-i", "-",
        "-an",
        "-c:v", "libx264", "-preset", "slow", "-crf", str(args.crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(args.output),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    frame_idx = 0
    for dur, rect_a, rect_b in SHOTS:
        n = int(round(dur * fps))
        for i in range(n):
            t = ease_in_out(i / max(n - 1, 1))
            x0 = (rect_a[0] + (rect_b[0] - rect_a[0]) * t) * CW
            y0 = (rect_a[1] + (rect_b[1] - rect_a[1]) * t) * CH
            x1 = (rect_a[2] + (rect_b[2] - rect_a[2]) * t) * CW
            y1 = (rect_a[3] + (rect_b[3] - rect_a[3]) * t) * CH
            crop = canvas.crop((int(x0), int(y0), int(x1), int(y1)))
            frame = crop.resize((out_w, out_h), Image.LANCZOS)

            # Fade in / out
            if frame_idx < FADE_IN_FRAMES:
                k = frame_idx / FADE_IN_FRAMES
                frame = Image.eval(frame, lambda v, k=k: int(v * k))
            elif frame_idx >= total_frames - FADE_OUT_FRAMES:
                k = max(0.0, (total_frames - frame_idx) / FADE_OUT_FRAMES)
                frame = Image.eval(frame, lambda v, k=k: int(v * k))

            proc.stdin.write(frame.tobytes())
            frame_idx += 1

    proc.stdin.close()
    proc.wait()
    size_mb = args.output.stat().st_size / (1024 * 1024)
    print(f"[ok] {args.output}  frames={frame_idx}  ~{frame_idx / fps:.1f}s  {size_mb:.2f} MB")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
