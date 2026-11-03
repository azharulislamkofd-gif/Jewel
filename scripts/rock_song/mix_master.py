#!/usr/bin/env python3
"""Mix instrumental + sung female vocals, master, and export final audio:

  media/final_rock_song.wav   (44.1 kHz, 16-bit stereo PCM)
  media/final_rock_song.mp3   (320 kbps, libmp3lame)
"""
import subprocess, sys
from pathlib import Path

import numpy as np
import soundfile as sf
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "media" / "work"
MEDIA = ROOT / "media"
SR = 44100
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

inst, sr = sf.read(str(WORK / "instrumental.wav"), dtype="float32")
voc, sr2 = sf.read(str(WORK / "vocals.wav"), dtype="float32")
assert sr == sr2 == SR and inst.shape == voc.shape

# vocals sit on top; slight duck of instrumental under vocal phrases
duck = 1.0 - 0.18 * (np.abs(voc).mean(axis=1) > 0.02)
inst_d = inst * duck[:, None]

mix = inst_d * 0.92 + voc * 0.62
# master: soft clip + normalize to -1 dBFS
mix = np.tanh(1.25 * mix) / np.tanh(1.25)
peak = np.max(np.abs(mix))
mix = (mix * (0.891 / peak)).astype(np.float32)

wav_out = MEDIA / "final_rock_song.wav"
sf.write(str(wav_out), mix, SR, subtype="PCM_16")
mp3_out = MEDIA / "final_rock_song.mp3"
r = subprocess.run([FFMPEG, "-y", "-i", str(wav_out), "-codec:a", "libmp3lame",
                    "-b:a", "320k", str(mp3_out)], capture_output=True, text=True)
assert r.returncode == 0, r.stderr[-400:]
print("wrote", wav_out, f"{len(mix)/SR:.1f}s peak={np.max(np.abs(mix)):.3f}")
print("wrote", mp3_out)
