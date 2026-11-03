#!/usr/bin/env python3
"""Render the instrumental rock arrangement of 'Rise From The Ashes' to WAV.

Pure numpy/scipy synthesis: live-style drums, distorted rhythm guitars, bass,
atmospheric pads and a melodic lead guitar, arranged by scripts/rock_song/song_data.py.

Outputs:
  media/work/instrumental.wav   (44.1 kHz stereo float32 -> 16-bit PCM)
  media/work/plan.json          (vocal melody plan + video scene schedule + beats)
"""
import json, math, sys
from pathlib import Path

import numpy as np
from scipy import signal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from song_data import (SECTIONS, VOCAL_SECTIONS, LYRICS, VOCAL_MELODY, SCENES,
                       INTRO_LEAD, SOLO_LEAD, OUTRO_LEAD, BPM, BEAT, BAR, SR,
                       DURATION, chord_at, section_of, bars_to_notes, parse_phrase,
                       note_midi, midi_freq)

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "media" / "work"
WORK.mkdir(parents=True, exist_ok=True)

N = int(DURATION * SR)
L = np.zeros(N, dtype=np.float32)
R = np.zeros(N, dtype=np.float32)

def place(buf, sig, t0):
    i = int(t0 * SR)
    if i >= N:
        return
    j = min(N, i + len(sig))
    buf[i:j] += sig[: j - i]

def env_ar(n, a, r):
    e = np.ones(n, dtype=np.float32)
    na = max(1, int(a * SR)); nr = max(1, int(r * SR))
    if na < n: e[:na] = np.linspace(0, 1, na, dtype=np.float32)
    if nr < n: e[-nr:] *= np.linspace(1, 0, nr, dtype=np.float32)
    return e

def saw(freq, dur, detune_cents=0.0, vib=0.0, vib_rate=5.5, phase0=0.0):
    n = max(1, int(dur * SR))
    t = np.arange(n, dtype=np.float32) / SR
    f = freq * 2 ** (detune_cents / 1200.0)
    if vib > 0:
        f = f * (1 + vib * np.sin(2 * np.pi * vib_rate * t))
    ph = 2 * np.pi * np.cumsum(f) / SR + phase0
    return (2 * (np.cumsum(f) / SR % 1.0) - 1.0).astype(np.float32), ph

def osc_saw(freq, dur, detune_cents=0.0, vib=0.0, vib_rate=5.5):
    n = max(1, int(dur * SR))
    t = np.arange(n, dtype=np.float32) / SR
    f = freq * 2 ** (detune_cents / 1200.0)
    if vib > 0:
        f = f * (1.0 + vib * np.sin(2 * np.pi * vib_rate * t))
    return (2.0 * ((np.cumsum(f) / SR) % 1.0) - 1.0).astype(np.float32)

def osc_sin(freq, dur):
    n = max(1, int(dur * SR))
    t = np.arange(n, dtype=np.float32) / SR
    return np.sin(2 * np.pi * freq * t).astype(np.float32)

def lowpass(x, cutoff, order=4):
    if cutoff >= SR / 2 - 100:
        return x
    sos = signal.butter(order, cutoff, btype="low", fs=SR, output="sos")
    return signal.sosfilt(sos, x).astype(np.float32)

def highpass(x, cutoff, order=4):
    sos = signal.butter(order, cutoff, btype="high", fs=SR, output="sos")
    return signal.sosfilt(sos, x).astype(np.float32)

def bandpass(x, lo, hi, order=4):
    sos = signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    return signal.sosfilt(sos, x).astype(np.float32)

def noise(n):
    return np.random.default_rng(12345).standard_normal(n).astype(np.float32)

# ------------------------------------------------------------------ drums
def kick(t0, gain=1.0):
    dur = 0.28
    n = int(dur * SR); t = np.arange(n) / SR
    f = 46 + 130 * np.exp(-t / 0.028)
    ph = 2 * np.pi * np.cumsum(f) / SR
    sig = np.sin(ph) * np.exp(-t / 0.105) + noise(n) * np.exp(-t / 0.004) * 0.25
    place(L, sig * gain * 0.9, t0); place(R, sig * gain * 0.9, t0)
    return sig * gain  # for sidechain duck

def snare(t0, gain=1.0, dur=0.22):
    n = int(dur * SR)
    sig = bandpass(noise(n), 1200, 5500, 3) * np.exp(-np.arange(n) / SR / 0.075)
    sig += osc_sin(185, dur) * np.exp(-np.arange(n) / SR / 0.05) * 0.6
    place(L, sig * gain * 0.55, t0); place(R, sig * gain * 0.55, t0)

def hat(t0, open_=False, gain=1.0):
    dur = 0.35 if open_ else 0.08
    n = int(dur * SR)
    sig = highpass(noise(n), 7800, 3) * np.exp(-np.arange(n) / SR / (0.28 if open_ else 0.028))
    g = 0.16 * gain * (1.6 if open_ else 1.0)
    place(L, sig * g, t0); place(R, sig * g, t0)

def crash(t0, gain=1.0):
    dur = 1.6; n = int(dur * SR)
    sig = highpass(noise(n), 4200, 3) * np.exp(-np.arange(n) / SR / 0.55)
    place(L, sig * 0.30 * gain, t0); place(R, sig * 0.30 * gain, t0)

KICK_STEPS = {"verse": [0, 4], "pre": [0, 4, 6], "chorus": [0, 4, 6],
              "solo": [0, 4, 6], "bridge": [0], "intro": [0, 4], "outro": [0, 4]}
SNARE_STEPS = {"verse": [2, 6], "pre": [2, 6], "chorus": [2, 6],
               "solo": [2, 6], "bridge": [4], "intro": [2, 6], "outro": [2, 6]}

def sec_key(name):
    return {"verse1": "verse", "verse2": "verse", "pre1": "pre",
            "chorus1": "chorus", "chorus2": "chorus", "chorus3": "chorus",
            "solo": "solo", "bridge": "bridge", "intro": "intro", "outro": "outro"}[name]

def render_drums():
    bar = 0
    t = 0.0
    duck = np.zeros(N, dtype=np.float32)
    while t < DURATION - 1e-3:
        name, s, e, en, voc = section_of(t)
        key = sec_key(name)
        bar_len = min(BAR, DURATION - t)
        # intro: silent for first ~6 bars, outro: stop after 300s, final hit at 320
        if name == "intro" and bar < 6:
            pass
        elif name == "outro" and t > 300.0:
            pass
        else:
            ks = KICK_STEPS[key]; ss = SNARE_STEPS[key]
            for st in range(8):
                tt = t + st * BEAT / 2
                if tt >= min(e, DURATION):
                    break
                accent = 1.25 if st % 2 == 0 else 1.0
                g = 0.5 + 0.5 * en
                if st in ks:
                    k = kick(tt, 0.9 * g * accent)
                    i0 = int(tt * SR); i1 = min(N, i0 + len(k))
                    duck[i0:i1] = np.maximum(duck[i0:i1], np.abs(k[: i1 - i0]))
                if st in ss:
                    snare(tt, 0.8 * g * accent)
                hat(tt, open_=(st == 6 and key in ("chorus", "solo")), gain=g * accent)
            if key in ("chorus", "solo") and (t - s) < BAR * 0.5 or (key == "bridge"):
                crash(t, 0.7 + 0.3 * en)
            # snare roll on last bar of pre / intro
            if (key in ("pre", "intro")) and (e - t) <= BAR + 0.01:
                for i in range(16):
                    snare(t + i * BEAT / 4, 0.25 + 0.75 * i / 16.0)
        t += bar_len
        bar += 1
    # final hit at 320s
    kick(320.0, 1.2); crash(320.0, 1.1); snare(320.0, 0.9)
    return duck

# ------------------------------------------------------------------- bass
def render_bass(duck):
    t = 0.0
    while t < DURATION - 1e-3:
        name, s, e, en, voc = section_of(t)
        if name == "intro" and t < 6 * BAR:
            t += BEAT / 2; continue
        if name == "outro" and t > 305:
            t += BEAT / 2; continue
        bass_midi, _ = chord_at(t)
        f = midi_freq(bass_midi)
        for st in range(8):
            tt = t + st * BEAT / 2
            if tt >= e:
                break
            dur = BEAT / 2 * 0.95
            n = int(dur * SR)
            sig = osc_sin(f, dur) + 0.35 * np.sign(osc_sin(f * 1.003, dur))
            sig = lowpass(sig, 320, 3) * env_ar(n, 0.008, dur * 0.7)
            g = (0.55 + 0.45 * en) * (1.15 if st % 2 == 0 else 0.9)
            i0 = int(tt * SR); i1 = min(N, i0 + n)
            d = 1.0 - 0.45 * duck[i0:i1]
            seg = sig[: i1 - i0] * g * d
            L[i0:i1] += seg; R[i0:i1] += seg
        t += BAR

# ---------------------------------------------------------- rhythm guitar
def strum(t0, chord_midis, dur, gain, cutoff, palm=False, pan=0.0):
    tones = []
    for m in chord_midis:
        f = midi_freq(m)
        tones.append(osc_saw(f, dur, -7) + osc_saw(f, dur, 7))
    sig = sum(tones) / len(tones)
    sig = np.tanh(2.6 * sig)                      # distortion
    sig = lowpass(sig, cutoff, 4)
    if palm:
        sig = sig * env_ar(len(sig), 0.004, dur * 0.45)
    else:
        sig = sig * env_ar(len(sig), 0.006, dur * 0.9)
    sig *= gain
    # strum feel: tiny stagger by re-adding delayed copy
    d = int(0.009 * SR)
    sig2 = np.concatenate([np.zeros(d, dtype=np.float32), sig[:-d]]) * 0.5
    sig = sig + sig2
    gl = 1.0 - abs(pan) * 0.35; gr = 1.0 + abs(pan) * 0.0
    if pan <= 0:
        place(L, sig * 1.0, t0); place(R, sig * gl, t0)
    else:
        place(L, sig * gl, t0); place(R, sig * 1.0, t0)

def render_rhythm():
    t = 0.0
    while t < DURATION - 1e-3:
        name, s, e, en, voc = section_of(t)
        key = sec_key(name)
        _, gtr = chord_at(t)
        if name == "intro":
            t += BAR; continue
        if name == "outro" and t > 318:
            # final ringing chord
            strum(320.0, gtr, 8.0, 0.5, 3500)
            t += BAR; continue
        steps = 8
        if key == "bridge" and (e - t) > 2 * BAR:   # half-time feel
            steps = 8
            for st in [0, 4]:
                tt = t + st * BEAT / 2
                if tt < e:
                    strum(tt, gtr, BEAT * 1.6, 0.5 + 0.35 * en, 4200)
            t += BAR; continue
        for st in range(steps):
            tt = t + st * BEAT / 2
            if tt >= e:
                break
            accent = 1.3 if st % 2 == 0 else 0.85
            if key == "verse":
                strum(tt, gtr, BEAT * 0.42, 0.34 * accent, 2100, palm=True)
            elif key == "pre":
                last_bar = (e - t) <= BAR + 0.01
                if last_bar and st % 2 == 1:  # 16th chugs
                    strum(tt, gtr, BEAT * 0.2, 0.4, 3200, palm=True)
                else:
                    strum(tt, gtr, BEAT * 0.48, 0.45 * accent, 3400)
            elif key in ("chorus", "solo"):
                g = 0.62 if key == "chorus" else 0.40
                strum(tt, gtr, BEAT * 0.55, g * accent, 5200)
            elif key == "outro":
                strum(tt, gtr, BEAT * 0.9, 0.30 * accent, 3200)
        t += BAR

# ------------------------------------------------------------------- pads
def render_pads():
    t = 0.0
    while t < DURATION - 1e-3:
        name, s, e, en, voc = section_of(t)
        _, gtr = chord_at(t)
        dur = min(BAR * 1.05, e - t + 0.2)
        tones = [osc_saw(midi_freq(m), dur, -4) + osc_saw(midi_freq(m), dur, 4)
                 for m in gtr]
        sig = sum(tones) / len(tones)
        sig = lowpass(sig, 1300, 3)
        a = min(0.35 * BAR, dur * 0.4); r = min(0.4 * BAR, dur * 0.4)
        sig = sig * env_ar(len(sig), a, r)
        g = {"intro": 0.16, "verse": 0.10, "pre": 0.11, "chorus": 0.12,
             "solo": 0.11, "bridge": 0.13, "outro": 0.14}.get(key_of(name), 0.1)
        if name == "outro" and t > 310:
            g *= max(0.0, 1 - (t - 310) / 18)
        place(L, sig * g, t); place(R, sig * g * 0.98, t)
        t += BAR

def key_of(name):
    return sec_key(name)

# ------------------------------------------------------------- lead guitar
def render_lead(phrase_text, t_start, gain, drive=4.0, double=False):
    notes = parse_phrase(phrase_text)
    t = t_start
    prev_f = None
    for midi, beats in notes:
        dur = beats * BEAT * 0.96
        if t + dur > DURATION:
            dur = DURATION - t
            if dur <= 0:
                break
        f = midi_freq(midi)
        n = max(1, int(dur * SR))
        tt = np.arange(n, dtype=np.float32) / SR
        # portamento from previous note
        if prev_f is not None:
            glide = min(0.08, dur * 0.4)
            ngl = int(glide * SR)
            ramp = np.linspace(prev_f / f, 1.0, ngl, dtype=np.float32)
            ff = np.ones(n, dtype=np.float32) * f
            ff[:ngl] = f * ramp
        else:
            ff = np.full(n, f, dtype=np.float32)
        # vibrato grows in
        vib = 0.006 * np.minimum(1.0, tt / max(dur * 0.4, 0.05))
        ff = ff * (1.0 + vib * np.sin(2 * np.pi * 5.6 * tt))
        ph = 2 * np.pi * np.cumsum(ff) / SR
        sig = (2.0 * ((np.cumsum(ff) / SR) % 1.0) - 1.0) + 0.4 * np.sin(ph)
        sig = np.tanh(drive * sig * 0.7)
        sig = lowpass(sig, 4800, 4)
        sig = sig * env_ar(n, 0.012, min(0.09, dur * 0.3))
        sig *= gain
        place(L, sig, t); place(R, sig, t)
        if double:
            sig2 = sig * 0.8
            place(L, sig2 * 0.4, t); place(R, sig2 * 0.4, t)
        # dotted-8th delay
        d = int(1.5 * BEAT * SR)
        fb = 0.32
        delayed = sig.copy()
        for rep in range(1, 4):
            seg = np.zeros(len(sig) + rep * d, dtype=np.float32)
            seg[rep * d:] = sig * (fb ** rep) * 0.5
            place(L, seg, t); place(R, seg * 0.9, t)
        prev_f = f
        t += beats * BEAT

def render_riser(t0, dur, gain=0.22):
    n = int(dur * SR)
    sig = bandpass(noise(n), 900, 9000, 3)
    ramp = np.linspace(0.05, 1.0, n, dtype=np.float32) ** 2
    sig = sig * ramp * gain
    place(L, sig, t0); place(R, sig, t0)

# ------------------------------------------------------------------- main
def main():
    print("rendering drums...")
    duck = render_drums()
    print("rendering bass...")
    render_bass(duck)
    print("rendering rhythm guitars...")
    render_rhythm()
    print("rendering pads...")
    render_pads()
    print("rendering lead guitars...")
    render_lead(INTRO_LEAD, 2.0, 0.30, drive=2.2)
    render_lead(SOLO_LEAD, 165.0 + 0.5, 0.42, drive=4.5, double=True)
    render_lead(OUTRO_LEAD, 276.0, 0.26, drive=2.4)
    render_riser(20.0 - 2 * BAR, 2 * BAR, 0.20)
    render_riser(65.0 - BAR, BAR, 0.22)
    render_riser(230.0 - BAR, BAR, 0.26)
    print("mastering...")
    # gentle bus glue: highpass the whole mix
    sos = signal.butter(2, 35, btype="high", fs=SR, output="sos")
    Lf = signal.sosfilt(sos, L).astype(np.float32)
    Rf = signal.sosfilt(sos, R).astype(np.float32)
    x = 1.15 * (Lf + Rf) / 2
    x = np.tanh(1.4 * x) / np.tanh(1.4)          # soft clip
    x = x.astype(np.float32)
    peak = np.max(np.abs(x)) + 1e-9
    x *= 0.891 / peak                             # -1 dBFS
    fi = int(0.05 * SR); x[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)
    fo_start = int(323.5 * SR)
    x[fo_start:] *= np.linspace(1, 0, N - fo_start, dtype=np.float32) ** 1.5
    stereo = np.stack([x, np.roll(x, 0)], axis=1)
    # tiny haas on right for width
    d = int(0.011 * SR)
    stereo[d:, 1] = x[:-d] * 0.92
    stereo[:d, 1] = x[:d] * 0.92
    import soundfile as sf
    out = WORK / "instrumental.wav"
    sf.write(str(out), stereo, SR, subtype="PCM_16")
    print("wrote", out, f"{N/SR:.1f}s")

    # ---- plan for vocals + video
    plan = {"bpm": BPM, "beat": BEAT, "bar": BAR, "sr": SR, "duration": DURATION,
            "beats": [round(i * BEAT, 4) for i in range(int(DURATION / BEAT) + 1)],
            "sections": [dict(name=n, start=s, end=e, energy=en, vocal=v)
                         for n, s, e, en, v in SECTIONS],
            "vocal_plan": [], "scenes": SCENES}
    for sec_name, lyric_key, s, e in VOCAL_SECTIONS:
        beats_total = (e - s) / BEAT
        notes = bars_to_notes(VOCAL_MELODY[lyric_key], beats_total)
        plan["vocal_plan"].append(dict(
            section=sec_name, lyric_key=lyric_key, start=s, end=e,
            text=LYRICS[lyric_key],
            notes=[[round(s + b * BEAT, 4), round(d * BEAT, 4), m]
                   for b, d, m in notes]))
    with open(WORK / "plan.json", "w") as f:
        json.dump(plan, f, indent=1)
    print("wrote", WORK / "plan.json", "vocal sections:", len(plan["vocal_plan"]))

if __name__ == "__main__":
    main()
