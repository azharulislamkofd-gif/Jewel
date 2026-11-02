#!/usr/bin/env python3
"""Animate a concert still into a cinematic MP4.

The repository's original ``make_video.py`` does a straight Ken Burns pan over a
cover-cropped still.  That works for landscape images, but a full-body portrait
would lose the singer's head and boots in a 16:9 crop.  This renderer instead
builds a widescreen stage from the *edges* of the supplied still (stretched,
de-focused and darkened), keeps the whole portrait sharp in the centre, then
layers the motion described in the brief:

    * slow cinematic camera orbit (parallax + tiny roll) with a subtle push-in
    * blue and golden spotlight beams panning across the stage
    * drifting floor smoke, flickering side sparks, pulsing crowd lights
    * a gentle "stage breeze" warp on hair / skirt-coat + a shifting stance
    * beat-synced light pulse, filmic grade, vignette, grain, fade in/out

Everything is procedural and reproducible from the single still -- no external
video model is required.  Output is a 1080p master plus an optional 4K upscale.

Usage:
    python3 tools/make_concert_video.py images/rock_singer_concert.jpg \
        media/rock_singer_live_concert.mp4 --seconds 20 --fourk media/rock_singer_live_concert_4k.mp4

Preview stills instead of encoding (handy for tuning the look):
    python3 tools/make_concert_video.py images/rock_singer_concert.jpg /tmp/x.mp4 \
        --preview-dir /tmp/concert_frames
"""
from __future__ import annotations

import argparse
import math
import subprocess
import sys
import time
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
TAU = 2.0 * math.pi


def smoothstep(x: np.ndarray | float) -> np.ndarray | float:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def fractal_noise(rng: np.random.Generator, h: int, w: int, octaves: int = 4) -> np.ndarray:
    """Tileable-ish smooth value noise, returned in 0..1 at (h, w)."""
    out = np.zeros((h, w), np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        gh, gw = max(3, h // (2 ** (octaves - o))), max(3, w // (2 ** (octaves - o)))
        small = rng.random((gh, gw)).astype(np.float32)
        layer = cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)
        out += layer * amp
        total += amp
        amp *= 0.55
    out /= total
    return (out - out.min()) / max(out.max() - out.min(), 1e-6)


class ConcertRenderer:
    """Stateful renderer: build the static layers once, then animate per frame."""

    def __init__(self, source: Path, w: int = 1920, h: int = 1080,
                 fps: int = 30, seconds: float = 20.0, seed: int = 2026):
        self.W, self.H, self.fps, self.seconds = w, h, fps, seconds
        self.total = int(round(seconds * fps))
        self.CW, self.CH = int(round(w * 1.12)), int(round(h * 1.12))
        self.lw, self.lh = w // 4, h // 4  # low-res grid for light/smoke/spark FX

        bgr = cv2.imread(str(source), cv2.IMREAD_COLOR)
        if bgr is None:
            raise SystemExit(f"cannot read image: {source}")
        src = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        self._build_stage(src)
        self._build_maps()

        rng = np.random.default_rng(seed)
        self.noise_a = fractal_noise(rng, self.lh, self.lw)
        self.noise_b = fractal_noise(rng, self.lh, self.lw)
        self.grain_rng = np.random.default_rng(seed + 1)
        self._build_beams()
        self._build_particles(rng)

    # ------------------------------------------------------------------ stage
    def _build_stage(self, src: np.ndarray) -> None:
        """Widescreen backdrop from the still's side strips + sharp centre portrait."""
        sh, sw = src.shape[:2]
        # The upper part of the still is all blue/gold beams and smoke: stretched
        # + de-focused it becomes a natural widescreen bokeh backdrop, with no
        # second, ghosted copy of the singer behind the sharp portrait.
        cut, top = int(sw * 0.30), int(sh * 0.62)
        left, right = src[:top, :cut], src[:top, sw - cut:]
        half = self.CW // 2
        bl = cv2.resize(left, (half, self.CH), interpolation=cv2.INTER_CUBIC)
        br = cv2.resize(right, (self.CW - half, self.CH), interpolation=cv2.INTER_CUBIC)
        bg = np.concatenate((bl, br), axis=1).astype(np.float32)
        bg = cv2.GaussianBlur(bg, (0, 0), 30)
        bg = np.clip(bg * 0.58 + np.array([0.016, 0.024, 0.046], np.float32), 0, 1)
        self.bg = np.ascontiguousarray(bg)

        fh = int(round(self.CH * 0.95))
        fw = int(round(fh * sw / sh))
        fg = cv2.resize(src, (fw, fh), interpolation=cv2.INTER_LANCZOS4).astype(np.float32)
        self.fw, self.fh = fw, fh

        # Wide feathered alpha + progressive defocus at the portrait's edges, so
        # the sharp subject dissolves into the blurred stage instead of ending
        # on a visible rectangle.
        ax = smoothstep(np.arange(fw, dtype=np.float32) / max(1, fw * 0.135))
        ax = np.minimum(ax, ax[::-1])
        ay = smoothstep(np.arange(fh, dtype=np.float32) / max(1, fh * 0.025))
        ay = np.minimum(ay, ay[::-1])
        self.alpha = np.ascontiguousarray((ay[:, None] * ax[None, :])[..., None])
        sharp = np.float32(smoothstep((ax[None, :] * ay[:, None] - 0.22) / 0.78))[..., None]
        soft = cv2.GaussianBlur(fg, (0, 0), 7)
        self.fg = np.ascontiguousarray(fg * sharp + soft * (1 - sharp))
        self.fx0, self.fy0 = (self.CW - fw) // 2, (self.CH - fh) // 2

    def _build_maps(self) -> None:
        """Coordinate grids for the low-res FX and the full-res breeze remap."""
        self.Xn, self.Yn = np.meshgrid(
            np.linspace(0, 1, self.lw, dtype=np.float32),
            np.linspace(0, 1, self.lh, dtype=np.float32),
        )
        xx, yy = np.meshgrid(np.arange(self.W, dtype=np.float32),
                             np.arange(self.H, dtype=np.float32))
        self.base_x = np.ascontiguousarray(xx)
        self.base_y = np.ascontiguousarray(yy)
        self.map_x = np.empty_like(self.base_x)
        self.map_y = np.empty_like(self.base_y)
        # Subject protection: keep added light off the singer's face / leather.
        self.protect = 1.0 - 0.62 * np.exp(-((self.Xn - 0.5) / 0.20) ** 2)
        self.vignette = self._vignette()

    def _vignette(self) -> np.ndarray:
        x = (np.arange(self.W, dtype=np.float32) / self.W - 0.5) * 2.0
        y = (np.arange(self.H, dtype=np.float32) / self.H - 0.5) * 2.0
        xx, yy = np.meshgrid(x, y)
        r2 = xx * xx * 0.85 + yy * yy
        return np.ascontiguousarray(
            (1.0 - 0.34 * np.clip(r2, 0, 1.6) ** 1.35)[..., None].astype(np.float32)
        )

    def _build_beams(self) -> None:
        cyan = np.array([0.10, 0.72, 1.00], np.float32)
        gold = np.array([1.00, 0.66, 0.20], np.float32)
        # (origin x, base angle, sweep amplitude, sweep period, phase, colour, gain)
        self.beams = [
            (0.06, -0.34, 0.16, 13.0, 0.2, cyan, 0.44),
            (0.27, -0.10, 0.20, 17.0, 1.7, cyan, 0.34),
            (0.47, 0.16, 0.18, 15.0, 3.1, gold, 0.31),
            (0.71, 0.30, 0.22, 19.0, 4.4, gold, 0.39),
            (0.94, 0.42, 0.17, 12.0, 5.6, cyan, 0.42),
        ]

    def _build_particles(self, rng: np.random.Generator) -> None:
        n = 90
        self.spark_x = np.concatenate((rng.uniform(0.01, 0.20, n // 2),
                                       rng.uniform(0.80, 0.99, n // 2)))
        rng.shuffle(self.spark_x)
        self.spark_y0 = rng.uniform(0.30, 0.88, n)
        self.spark_v = rng.uniform(0.035, 0.10, n)
        self.spark_phase = rng.uniform(0, TAU, n)
        self.spark_gain = rng.uniform(0.45, 1.0, n)

        m = 110
        self.crowd_x = np.concatenate((rng.uniform(0.0, 0.31, m // 2),
                                       rng.uniform(0.69, 1.0, m // 2)))
        self.crowd_y = rng.uniform(0.44, 0.76, m)
        self.crowd_phase = rng.uniform(0, TAU, m)
        self.crowd_gain = rng.uniform(0.25, 0.75, m)
        self.crowd_warm = rng.random(m) > 0.35

    # ------------------------------------------------------------------- frame
    def _compose(self, t: float, p: float) -> np.ndarray:
        """Backdrop + portrait with an orbital parallax, then camera push-in/roll."""
        orbit = math.sin(TAU * t / (self.seconds * 0.92) - math.pi / 2)
        frame = self.bg.copy()
        fx = self.fx0 + int(round(7.0 * orbit))
        fy = self.fy0 + int(round(2.0 * math.sin(TAU * t / 9.0)))
        roi = frame[fy:fy + self.fh, fx:fx + self.fw]
        frame[fy:fy + self.fh, fx:fx + self.fw] = roi * (1 - self.alpha) + self.fg * self.alpha

        zoom = 1.0 + 0.05 * p                       # subtle, continuous push-in
        angle = 0.30 * math.sin(TAU * t / (self.seconds * 1.1))  # hint of orbit roll
        M = cv2.getRotationMatrix2D((self.CW / 2, self.CH / 2), angle, zoom)
        M[0, 2] += self.W / 2 - self.CW / 2 - 9.0 * orbit
        M[1, 2] += self.H / 2 - self.CH / 2 + 3.0 * math.sin(TAU * t / 11.0)
        return cv2.warpAffine(frame, M, (self.W, self.H), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REFLECT)

    def _breeze(self, frame: np.ndarray, t: float) -> np.ndarray:
        """Localised, sub-pixel-to-few-pixel warp: hair sway + skirt-coat flow."""
        X, Y = self.Xn, self.Yn
        cx = np.exp(-((X - 0.5) / 0.115) ** 2)
        hair = cx * np.exp(-((Y - 0.24) / 0.14) ** 2) * smoothstep((Y - 0.08) / 0.22)
        skirt = cx * np.exp(-((Y - 0.74) / 0.30) ** 2) * smoothstep((Y - 0.42) / 0.22)
        body = np.exp(-((X - 0.5) / 0.19) ** 2) * np.exp(-((Y - 0.52) / 0.42) ** 2)
        phase = 7.0 * Y + 4.0 * X
        dx = (2.4 * hair * np.sin(TAU * 0.36 * t + phase)
              + 3.6 * skirt * np.sin(TAU * 0.27 * t + 2.0 * Y + 3.0 * X)
              + 0.7 * body * np.sin(TAU * 0.22 * t))
        dy = 0.8 * hair * np.sin(TAU * 0.31 * t + phase) + 0.5 * skirt * np.sin(TAU * 0.24 * t)
        np.add(self.base_x, cv2.resize(dx.astype(np.float32), (self.W, self.H)), out=self.map_x)
        np.add(self.base_y, cv2.resize(dy.astype(np.float32), (self.W, self.H)), out=self.map_y)
        return cv2.remap(frame, self.map_x, self.map_y, cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_REPLICATE)

    def _lights(self, t: float) -> np.ndarray:
        """Low-res additive light field: beams, smoke, sparks, crowd, lamps."""
        X, Y = self.Xn, self.Yn
        ov = np.zeros((self.lh, self.lw, 3), np.float32)
        beat = 0.82 + 0.18 * math.sin(TAU * 2.0 * t)  # 120 bpm feel

        for ox0, base_ang, amp, period, phase, colour, gain in self.beams:
            ox = 0.06 + 0.88 * ox0 + 0.035 * math.sin(TAU * t / (self.seconds * 0.8) + phase)
            ang = base_ang + amp * math.sin(TAU * t / period + phase)
            sx, sy = math.sin(ang), math.cos(ang)
            px, py = X - ox, Y + 0.08
            along = px * sx + py * sy
            perp = np.abs(px * sy - py * sx)
            width = 0.010 + 0.115 * np.maximum(along, 0)
            beam = np.exp(-((perp / width) ** 2)) * np.exp(-np.maximum(along, 0) * 1.25)
            beam *= (along > 0) * self.protect
            flick = 0.78 + 0.22 * math.sin(TAU * 2.0 * t + phase * 2.0)
            ov += beam[..., None] * colour * (gain * beat * flick)
            lamp = np.exp(-((X - ox) ** 2 + (Y - 0.005) ** 2) / (2 * 0.045 ** 2))
            ov += lamp[..., None] * colour * (0.24 * gain * beat)

        # Floor smoke: two smooth noise fields drifting in opposite directions.
        sa = int((t * 13) % self.lw)
        sb = int((t * 7) % self.lw)
        cloud = 0.62 * np.roll(self.noise_a, sa, axis=1) + 0.38 * np.roll(self.noise_b, -sb, axis=1)
        cloud = np.clip(cloud - 0.42, 0, 1) * 1.7
        smoke_mask = (0.95 * np.exp(-((Y - 0.90) / 0.26) ** 2)
                      + 0.22 * np.exp(-((Y - 0.48) / 0.20) ** 2))
        cool = np.array([0.52, 0.72, 0.92], np.float32)
        ov += (cloud * smoke_mask * self.protect)[..., None] * cool * 0.21

        # Lightweight additive dots, blurred once so they read as glows / sparks.
        dots = np.zeros((self.lh, self.lw), np.float32)
        sy = (self.spark_y0 + self.spark_v * t) % 0.62 + 0.30
        sx = self.spark_x + 0.012 * np.sin(TAU * 0.4 * t + self.spark_phase)
        flick = np.clip(np.sin(TAU * 3.3 * t + self.spark_phase), 0, 1) ** 3
        for x, y, g, f in zip(sx, sy, self.spark_gain, flick):
            cv2.circle(dots, (int(x * self.lw), int(y * self.lh)), 0,
                       float(g * f * 0.75), -1, cv2.LINE_AA)
        pulse = 0.45 + 0.55 * np.clip(np.sin(TAU * 2.0 * t + self.crowd_phase), 0, 1)
        cy = self.crowd_y + 0.006 * np.sin(TAU * 1.7 * t + self.crowd_phase)
        for x, y, g, pl, warm in zip(self.crowd_x, cy, self.crowd_gain, pulse, self.crowd_warm):
            cv2.circle(dots, (int(x * self.lw), int(y * self.lh)), 1,
                       float(g * pl * (0.36 if warm else 0.30)), -1, cv2.LINE_AA)
        dots = cv2.GaussianBlur(dots, (0, 0), 1.1)
        ov += dots[..., None] * np.array([0.72, 0.90, 1.00], np.float32) * 0.85
        return ov

    def render_frame(self, i: int) -> np.ndarray:
        t = i / self.fps
        p = smoothstep(t / self.seconds)
        frame = self._compose(t, p)
        frame = self._breeze(frame, t)

        ov = cv2.resize(self._lights(t), (self.W, self.H), interpolation=cv2.INTER_LINEAR)
        frame = 1.0 - (1.0 - frame) * (1.0 - np.clip(ov, 0, 0.9))  # screen blend

        frame *= self.vignette
        frame *= 1.0 + 0.012 * math.sin(TAU * 2.0 * t)               # beat pulse
        # gentle filmic S-curve + cool shadows / warm highlights
        lum = frame.mean(axis=2, keepdims=True)
        frame = np.clip(frame * 1.045 - 0.012, 0, 1)
        frame = frame + (1 - lum) * np.array([0.012, 0.006, 0.000], np.float32)
        frame = frame + lum * np.array([0.000, 0.005, 0.014], np.float32)
        grain = self.grain_rng.standard_normal((self.lh, self.lw)).astype(np.float32)
        frame += cv2.resize(grain, (self.W, self.H))[..., None] * 0.006
        fade = min(1.0, smoothstep(t / 0.8), smoothstep((self.seconds - t) / 1.1))
        frame = np.clip(frame * fade, 0, 1)
        return np.ascontiguousarray((frame * 255.0).astype(np.uint8))


def encode(renderer: ConcertRenderer, output: Path, crf: int, preset: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG, "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{renderer.W}x{renderer.H}", "-r", str(renderer.fps), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    started = time.time()
    for i in range(renderer.total):
        proc.stdin.write(renderer.render_frame(i).tobytes())
        if (i + 1) % 60 == 0:
            print(f"[info] {i + 1}/{renderer.total} frames  {time.time() - started:.0f}s",
                  file=sys.stderr, flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg encode failed")
    print(f"[ok] {output}  {renderer.total} frames  ~{renderer.seconds:.1f}s  "
          f"{output.stat().st_size / 1048576:.2f} MB  ({time.time() - started:.0f}s)")


def make_4k(master: Path, fourk: Path, crf: int) -> None:
    """Lanczos upscale of the 1080p master (the source still is only 843 px wide)."""
    fourk.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG, "-y", "-loglevel", "error", "-i", str(master),
        "-vf", "scale=3840:2160:flags=lanczos,unsharp=5:5:0.45:5:5:0.0",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(fourk),
    ]
    subprocess.run(cmd, check=True)
    print(f"[ok] {fourk}  3840x2160  {fourk.stat().st_size / 1048576:.2f} MB")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--w", type=int, default=1920)
    ap.add_argument("--h", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--crf", type=int, default=18)
    ap.add_argument("--preset", default="medium")
    ap.add_argument("--fourk", type=Path, help="also write a 3840x2160 upscale here")
    ap.add_argument("--fourk-crf", type=int, default=22)
    ap.add_argument("--poster", type=Path, help="save a representative 16:9 frame as JPG")
    ap.add_argument("--preview-dir", type=Path,
                    help="write 4 sample frames here and exit without encoding")
    args = ap.parse_args()

    if args.w % 2 or args.h % 2:
        print("width/height must be even for yuv420p", file=sys.stderr)
        return 2

    r = ConcertRenderer(args.source, args.w, args.h, args.fps, args.seconds)
    print(f"[info] {args.source} -> {args.w}x{args.h} @ {args.fps}fps, "
          f"{r.total} frames, stage canvas {r.CW}x{r.CH}", file=sys.stderr)

    if args.preview_dir:
        args.preview_dir.mkdir(parents=True, exist_ok=True)
        for frac in (0.02, 0.30, 0.65, 0.95):
            i = int(r.total * frac)
            frame = r.render_frame(i)
            p = args.preview_dir / f"frame_{i:04d}.jpg"
            cv2.imwrite(str(p), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR),
                        [cv2.IMWRITE_JPEG_QUALITY, 92])
            print(f"[preview] {p}")
        return 0

    if args.poster:
        args.poster.parent.mkdir(parents=True, exist_ok=True)
        frame = r.render_frame(int(r.total * 0.32))
        cv2.imwrite(str(args.poster), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR),
                    [cv2.IMWRITE_JPEG_QUALITY, 90])
        print(f"[ok] poster {args.poster}")

    encode(r, args.output, args.crf, args.preset)
    if args.fourk:
        make_4k(args.output, args.fourk, args.fourk_crf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
