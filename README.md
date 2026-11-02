# Jewel — media renders

Small collection of generated stills, cinematic MP4 renders and a Bengali
documentary script, plus the tooling that rebuilds them.

## Concert render (new)

`tools/make_concert_video.py` animates a single portrait still into a 20-second
cinematic concert clip. Because a 16:9 cover-crop would cut the singer's head and
boots, it keeps the whole portrait sharp in the centre and builds a widescreen
stage out of the de-focused edges of the same image. Layers on top:

- slow camera orbit (foreground/background parallax + tiny roll) and a subtle push-in
- panning cyan/gold spotlight beams and pulsing lamp heads
- drifting fractal floor smoke, flickering side sparks, beat-pulsed crowd lights
- a gentle localised warp for hair sway, skirt-coat flow and a shifting stance
- filmic grade, vignette, grain, beat pulse, fade in/out

```bash
python3 -m pip install Pillow imageio-ffmpeg numpy opencv-python-headless

python3 tools/make_concert_video.py \
  images/rock_singer_concert.jpg media/rock_singer_live_concert.mp4 \
  --seconds 20 --fps 30 --crf 18 --preset fast \
  --fourk media/rock_singer_live_concert_4k.mp4 \
  --poster media/rock_singer_live_concert_poster.jpg

# inspect four sample frames without encoding
python3 tools/make_concert_video.py images/rock_singer_concert.jpg /tmp/x.mp4 \
  --preview-dir /tmp/concert_frames
```

Outputs: `media/rock_singer_live_concert.mp4` (1920×1080, CRF 18) and
`media/rock_singer_live_concert_4k.mp4` (3840×2160, Lanczos upscale of the
master). The full brief and the method are in
`media/rock_singer_live_concert_prompt.txt`.

> This is a **procedural animation of one still**, not a generative video model:
> it cannot invent new bodily motion, vocals or audio, and fine detail is limited
> by the 843×1264 source image. The videos have no audio track.

## Serving / downloads

```bash
bash tools/serve_downloads.sh            # install deps, build missing renders, serve media/ on 0.0.0.0:8000
bash tools/serve_downloads.sh --build    # rebuild only, no server
bash tools/serve_downloads.sh --force    # re-render everything
```

Open `media/index.html` through that server for the preview and download links.

## Older renders

- `tools/make_video.py` — generic still → 1080p Ken Burns MP4 (five eased shots,
  fades). Used for `tech_review_cinematic.mp4` and `rock_singer_cinematic.mp4`.
- `tools/md_to_email.py` — renders `scripts/nokia_full_script_bn.md` into an
  email-friendly HTML page plus a plain-text version under `media/`.
