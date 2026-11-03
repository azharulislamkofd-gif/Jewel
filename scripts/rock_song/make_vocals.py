#!/usr/bin/env python3
"""Turn the spoken demo clips (media/work/tts/<lyric_key>.wav) into a SUNG
female lead vocal track using ffmpeg's rubberband filter:

  * each vocal section is split into one segment per melody note
    (proportional to note duration), time-stretched to its musical slot,
  * pitch-shifted (formant-preserving rubberband) onto the composed melody,
  * segments are crossfaded, then the full take gets reverb + delay.

Output: media/work/vocals.wav (44.1 kHz stereo, same length as the song)
"""
import json, subprocess, sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import imageio_ffmpeg
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "media" / "work"
TTS = WORK / "tts"
SR = 44100

plan = json.load(open(WORK / "plan.json"))
DUR = plan["duration"]
N = int(DUR * SR)

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg failed: " + r.stderr[-500:])

def load_wav(path):
    x, sr = sf.read(str(path), dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != SR:
        # resample via ffmpeg
        tmp = WORK / "_tmp_res.wav"
        run([FFMPEG, "-y", "-i", str(path), "-ar", str(SR), "-ac", "1", str(tmp)])
        x, sr = sf.read(str(tmp), dtype="float32")
        if x.ndim > 1:
            x = x.mean(axis=1)
    return x

def estimate_f0(x):
    """Median f0 via autocorrelation over voiced 40 ms windows."""
    win = int(0.04 * SR); hop = int(0.01 * SR)
    f0s = []
    lo, hi = 90.0, 500.0
    for i in range(0, max(1, len(x) - win), hop):
        seg = x[i:i + win]
        if np.sqrt(np.mean(seg ** 2)) < 0.01:
            continue
        seg = seg - seg.mean()
        ac = np.correlate(seg, seg, mode="full")[win - 1:]
        if ac[0] <= 0:
            continue
        ac = ac / ac[0]
        lag_lo = int(SR / hi); lag_hi = int(SR / lo)
        if lag_hi >= len(ac):
            continue
        lag = lag_lo + np.argmax(ac[lag_lo:lag_hi])
        if ac[lag] > 0.35:
            f0s.append(SR / lag)
    if not f0s:
        return 220.0
    return float(np.median(f0s))

def rubberband_segment(x, target_f0, out_dur):
    """Time-stretch to out_dur and pitch-shift so median f0 == target_f0."""
    est = estimate_f0(x)
    ratio = target_f0 / est
    ratio = float(np.clip(ratio, 0.35, 2.8))
    tempo = len(x) / (out_dur * SR)
    tmp_in = WORK / "_seg_in.wav"
    tmp_out = WORK / "_seg_out.wav"
    sf.write(str(tmp_in), x, SR, subtype="FLOAT")
    run([FFMPEG, "-y", "-i", str(tmp_in),
         "-af", f"rubberband=tempo={tempo:.6f}:pitch={ratio:.6f}:formant=preserved:pitchq=quality:transients=crisp:window=long",
         "-ar", str(SR), "-ac", "1", str(tmp_out)])
    y, _ = sf.read(str(tmp_out), dtype="float32")
    if y.ndim > 1:
        y = y.mean(axis=1)
    # pad/trim to exact length
    if len(y) < int(out_dur * SR):
        y = np.concatenate([y, np.zeros(int(out_dur * SR) - len(y), dtype=np.float32)])
    return y[: int(out_dur * SR)]

def xfade_into(buf, sig, t0, xf=0.03):
    i0 = int(t0 * SR)
    n = len(sig)
    i1 = min(N, i0 + n)
    seg = sig[: i1 - i0]
    if i0 > 0 and i0 < N:
        nx = min(int(xf * SR), len(seg), i0)
        if nx > 0:
            ramp = np.linspace(0, 1, nx, dtype=np.float32)
            buf[i0:i0 + nx] = buf[i0:i0 + nx] * (1 - ramp) + seg[:nx] * ramp
            buf[i0 + nx:i1] += seg[nx:]
            return
    buf[i0:i1] += seg

def render_section(vp, audio, cache):
    key = vp["lyric_key"]
    if key not in cache:
        cache[key] = load_wav(TTS / f"{key}.wav")
    speech = cache[key]
    notes = vp["notes"]  # [start_s, dur_s, midi]
    total = vp["end"] - vp["start"]
    # merge consecutive identical midi notes to reduce segment count
    merged = []
    for st, du, m in notes:
        if merged and merged[-1][2] == m:
            merged[-1][1] += du
        else:
            merged.append([st, du, m])
    notes = merged
    sum_notes = sum(d for _, d, _ in notes)
    out = np.zeros(N, dtype=np.float32)
    for st, du, m in notes:
        # proportional slice of the speech audio
        frac0 = (st - vp["start"]) / total
        frac1 = (st + du - vp["start"]) / total
        i0 = int(frac0 * len(speech)); i1 = int(frac1 * len(speech))
        seg_in = speech[i0:i1]
        if len(seg_in) < int(0.05 * SR):
            continue
        target = 440.0 * 2 ** ((m - 69) / 12.0)
        seg = rubberband_segment(seg_in, target, du)
        xfade_into(out, seg, st)
    return out

def add_fx(voc):
    # highpass + gentle compression
    sos = signal.butter(2, 90, btype="high", fs=SR, output="sos")
    voc = signal.sosfilt(sos, voc).astype(np.float32)
    voc = np.tanh(1.6 * voc / (np.max(np.abs(voc)) + 1e-6) * 0.9)
    # dotted-8th delay
    beat = plan["beat"]
    d = int(1.5 * beat * SR)
    delayed = np.zeros(N, dtype=np.float32)
    delayed[d:] = voc[:-d] * 0.30
    delayed[2 * d:] += voc[:-2 * d] * 0.12
    voc = voc + delayed
    # stereo reverb: generated exponential-decay IR, fft convolution
    rng = np.random.default_rng(7)
    ir_len = int(1.9 * SR)
    t = np.arange(ir_len) / SR
    ir_l = rng.standard_normal(ir_len) * np.exp(-t / 0.45)
    ir_r = rng.standard_normal(ir_len) * np.exp(-t / 0.5)
    ir_l = signal.sosfilt(signal.butter(3, 4200, btype="low", fs=SR, output="sos"), ir_l)
    ir_r = signal.sosfilt(signal.butter(3, 4200, btype="low", fs=SR, output="sos"), ir_r)
    wet_l = signal.fftconvolve(voc, ir_l)[:N] * 0.35
    wet_r = signal.fftconvolve(voc, ir_r)[:N] * 0.35
    return np.stack([voc + wet_l, voc + wet_r], axis=1).astype(np.float32)

def main():
    TTS.mkdir(parents=True, exist_ok=True)
    cache = {}
    full = np.zeros(N, dtype=np.float32)
    for vp in plan["vocal_plan"]:
        f = TTS / f"{vp['lyric_key']}.wav"
        if not f.exists():
            print("MISSING tts clip:", f)
            continue
        print(f"singing section {vp['section']} ({vp['start']}-{vp['end']}) ...")
        seg = render_section(vp, None, cache)
        # per-section gain: verses soft, choruses strong
        g = {"verse1": 0.85, "verse2": 0.85, "pre1": 0.95, "chorus1": 1.0,
             "chorus2": 1.05, "bridge": 0.95, "chorus3": 1.15, "outro": 0.7}[vp["section"]]
        i0 = int(vp["start"] * SR); i1 = int(vp["end"] * SR)
        full[i0:i1] += seg[i0:i1] * g
    # fade outro vocal
    fo = int(288 * SR)
    full[fo:] *= np.linspace(1, 0, N - fo, dtype=np.float32)
    stereo = add_fx(full)
    peak = np.max(np.abs(stereo)) + 1e-9
    stereo *= 0.95 / peak
    sf.write(str(WORK / "vocals.wav"), stereo, SR, subtype="FLOAT")
    print("wrote", WORK / "vocals.wav", "peak", float(np.max(np.abs(stereo))))

if __name__ == "__main__":
    main()
