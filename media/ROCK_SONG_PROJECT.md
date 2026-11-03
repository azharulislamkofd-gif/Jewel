# 🔥 Rise From The Ashes — Original Female Rock Song + Full Music Video

**Artist:** AURORA VEIL (fictional original artist) · **Song:** "Rise From The Ashes"
**Genre:** cinematic hard rock / modern alternative rock · **Key:** E minor · **Tempo:** 132 BPM · **Length:** 5:30

## Deliverables (in `media/`)

| File | Format |
|---|---|
| `final_rock_music_video.mp4` | Full music video — H.264 High, 1920×1080, 30 fps, 16:9, AAC 320 kbps audio, `+faststart` (moov at front) so it streams/downloads directly in Android Chrome |
| `final_rock_song.mp3` | Full song — MP3, 320 kbps, 44.1 kHz stereo |
| `final_rock_song.wav` | Full song — WAV, 44.1 kHz, 16-bit stereo PCM |
| `final_rock_lyrics.txt` | Original English lyrics with timestamps |
| `rock_video_poster.jpg` | Video poster frame |
| `index.html` | Download page (Download buttons) — serve with `python3 -m http.server 8000` from `media/` |

## Song structure (fully original lyrics & composition)

Intro 0:00–0:20 · Verse 1 0:20–0:50 · Pre-chorus 0:50–1:05 · Chorus 1:05–1:40 ·
Verse 2 1:40–2:10 · Chorus 2:10–2:45 · Guitar solo 2:45–3:20 · Bridge 3:20–3:50 ·
Final chorus 3:50–4:35 · Outro 4:35–5:30 (final hit + ring-out fade)

Story: a woman facing darkness, heartbreak and doubt — rising stronger than ever.

## Music video

20 scenes cut on the beat across the whole 5:30: dark concert stage with blue/golden
spotlights, the same fictional female singer (long flowing black hair, black leather
rock outfit) performing, emotional close-ups, guitarist / drummer shots, rainy night
city, rainy rooftop, smoke, spark fountains, a dramatic guitar-solo scene, beat-synced
light flashes, and a pyro final chorus. Ken Burns camera moves, per-scene cinematic
color grades, film grain + vignette, hard cuts synced to the arrangement.

## How it was produced (tools available in this environment)

No commercial AI music/video generator is available here, so the project was built
with a custom open pipeline (`scripts/rock_song/`):

- `song_data.py` — single source of truth: structure, chords, original lyrics,
  vocal melodies, video scene schedule (song and video are generated from the same
  timeline, so they are sample-accurate in sync).
- `render_instrumental.py` — numpy/scipy synthesis of the full rock arrangement:
  live-style drums (kick/snare/hats/crashes, snare rolls, risers), distorted
  dual-tracked rhythm guitars (palm-muted verses, power-chord choruses), bass with
  kick sidechain, atmospheric pads, melodic lead guitar with vibrato/portamento
  and dotted-8th delay (intro hook, 35 s solo, outro reprise), soft-clip mastering.
- `make_vocals.py` — the female lead vocal: a registered female English voice reads
  each section; every melody note is rendered by time-stretching + pitch-shifting
  (ffmpeg rubberband, formant-preserving) the speech onto the composed melody —
  one consistent female singer, verses soft / choruses powerful, plus reverb and
  delay. No male voices anywhere.
- `build_video.py` + `derive_scenes.py` — scene stills (AI-generated, singer kept
  consistent via a reference portrait) turned into 1080p30 segments with camera
  moves and grades, concatenated, with animated rain/spark/haze overlays,
  beat-synced flashes, grain/vignette, then muxed with the master audio.

Working files (regenerable) live in `media/work/` (git-ignored); only the final
deliverables are tracked.
