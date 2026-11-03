#!/usr/bin/env python3
"""Build the full-length cinematic music video for 'Rise From The Ashes'.

Pipeline (no AI video generator is available in this environment, so the video
is produced from cinematically generated stills + professional motion/grade):

  1. each scene still -> 1920x1080@30fps segment with a Ken Burns camera move
     (push-in / pull-out / pan / drift / slow-zoom) and a per-scene color grade
  2. segments are concatenated in song order (hard cuts on the beat)
  3. overlays: animated rain (rain scenes), drifting haze, spark/flash pulses
     on chorus beats, film grain, vignette, final cinematic grade
  4. the full 5:30 master audio is muxed in; H.264 + faststart for direct
     download in Android Chrome

Output: media/final_rock_music_video.mp4
"""
import json, subprocess, sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import imageio_ffmpeg
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "media" / "work"
SCENES_DIR = WORK / "scenes"
SEG_DIR = WORK / "segments"
MEDIA = ROOT / "media"
SEG_DIR.mkdir(parents=True, exist_ok=True)

plan = json.load(open(WORK / "plan.json"))
SCENES = plan["scenes"]
BEAT = plan["beat"]
DUR = plan["duration"]
W, H, FPS = 1920, 1080, 30

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1500:])
        raise RuntimeError("cmd failed: " + " ".join(cmd[:6]))

# ---------------------------------------------------------------- overlays
def make_rain_tile(path, seconds=8):
    """Loopable animated rain tile with alpha (RGBA), 960x540."""
    tw, th = 960, 540
    n = int(seconds * FPS)
    rng = np.random.default_rng(42)
    drops = [{"x": rng.uniform(0, tw), "y": rng.uniform(0, th),
              "v": rng.uniform(500, 900), "l": rng.uniform(12, 26),
              "w": rng.uniform(0.6, 1.4)} for _ in range(240)]
    frames_dir = WORK / "rain_frames"
    frames_dir.mkdir(exist_ok=True)
    for i in range(n):
        img = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for dr in drops:
            dr["y"] += dr["v"] / FPS
            if dr["y"] > th + 30:
                dr["y"] = -30; dr["x"] = rng.uniform(0, tw)
            a = int(90 * min(1.0, dr["v"] / 700))
            d.line([(dr["x"], dr["y"]), (dr["x"] - dr["l"] * 0.18, dr["y"] + dr["l"])],
                   fill=(200, 220, 255, a), width=int(dr["w"]))
        img.save(frames_dir / f"r{i:04d}.png")
    run([FFMPEG, "-y", "-framerate", str(FPS), "-i", str(frames_dir / "r%04d.png"),
         "-vf", "format=rgba", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "18", "-pix_fmt", "yuva420p", str(path)])
    print("rain tile:", path)

def make_haze(path):
    """Soft drifting haze plate (grayscale alpha), 1920x1080, loopable-ish."""
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(3)
    for _ in range(26):
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        r = rng.uniform(180, 420)
        v = int(rng.uniform(14, 38))
        d.ellipse([x - r, y - r * 0.6, x + r, y + r * 0.6], fill=v)
    img = img.filter(ImageFilter.GaussianBlur(120))
    img.save(path)
    print("haze plate:", path)

def make_spark_tile(path, seconds=6):
    """Sparks / ember bursts tile with alpha."""
    tw, th = 960, 540
    n = int(seconds * FPS)
    rng = np.random.default_rng(11)
    parts = []
    for _ in range(90):
        parts.append({"x": rng.uniform(0, tw), "y": rng.uniform(th * 0.55, th),
                      "vx": rng.uniform(-60, 60), "vy": rng.uniform(-320, -120),
                      "life": rng.uniform(0.5, 1.6), "t": rng.uniform(0, 1.6),
                      "r": rng.uniform(1.0, 2.6)})
    frames_dir = WORK / "spark_frames"
    frames_dir.mkdir(exist_ok=True)
    for i in range(n):
        img = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for p in parts:
            p["t"] += 1 / FPS
            if p["t"] > p["life"]:
                p["t"] = 0
                p["x"] = rng.uniform(0, tw); p["y"] = rng.uniform(th * 0.55, th)
                p["vy"] = rng.uniform(-320, -120)
            age = p["t"] / p["life"]
            x = p["x"] + p["vx"] * p["t"]
            y = p["y"] + p["vy"] * p["t"] + 300 * p["t"] ** 2
            a = int(220 * (1 - age))
            if a > 0:
                d.ellipse([x - p["r"], y - p["r"], x + p["r"], y + p["r"]],
                          fill=(255, 200 + int(50 * (1 - age)), 90, a))
        img.save(frames_dir / f"s{i:04d}.png")
    run([FFMPEG, "-y", "-framerate", str(FPS), "-i", str(frames_dir / "s%04d.png"),
         "-vf", "format=rgba", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "18", "-pix_fmt", "yuva420p", str(path)])
    print("spark tile:", path)

# ------------------------------------------------------------- scene render
GRADES = {
    "blue_gold": "eq=contrast=1.10:saturation=1.18:brightness=0.01,      colorbalance=rs=0.04:gs=0.01:bs=-0.07:rh=0.10:gh=0.05:bh=-0.04",
    "blue":      "eq=contrast=1.08:saturation=1.12:brightness=-0.02,     colorbalance=bs=-0.10:bh=-0.06:gs=-0.02",
    "gold":      "eq=contrast=1.10:saturation=1.20:brightness=0.02,      colorbalance=rh=0.12:gh=0.07:bh=-0.05:rs=0.05:gs=0.03",
    "dark":      "eq=contrast=1.15:saturation=1.05:brightness=-0.10,     colorbalance=bs=-0.08:bh=-0.10",
}

def zoompan_expr(move, dur):
    """Return zoompan z/x/y expressions for the camera move."""
    d = max(1, int(dur * FPS))
    if move == "push_in":
        return (f"min(1.0+0.9/{d},1.45)",
                "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)")
    if move == "pull_out":
        return (f"max(1.45-0.45*on/{d},1.0)",
                "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)")
    if move == "slow_zoom":
        return (f"min(1.0+0.25/{d},1.25)",
                "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)")
    if move == "pan":
        return ("1.18",
                f"(iw-iw/zoom)*(on/{d})", "ih/2-(ih/zoom/2)*0.6")
    # drift
    return ("1.22",
            f"(iw-iw/zoom)*0.5+sin(on/{d}*2*PI)*iw/zoom*0.12",
            f"(ih-ih/zoom)*0.5+cos(on/{d}*2*PI)*ih/zoom*0.08")

def render_segment(sc):
    img = SCENES_DIR / sc["file"]
    dur = sc["end"] - sc["start"]
    out = SEG_DIR / f"{sc['id']}.mp4"
    if out.exists():
        return out
    z, x, y = zoompan_expr(sc["move"], dur)
    grade = GRADES[sc["grade"]]
    # slight per-scene fade in/out (0.25s) except first/last handled globally
    fade = f"fade=t=in:st=0:d=0.25,fade=t=out:st={max(0,dur-0.25)}:d=0.25"
    vf = (f"scale=2560:1440:flags=lanczos,zoompan=z='{z}':x='{x}':y='{y}':"
          f"d={max(1,int(dur*FPS))}:s={W}x{H}:fps={FPS},"
          f"crop={W}:{H}, {grade}, {fade}, format=yuv420p")
    run([FFMPEG, "-y", "-loop", "1", "-framerate", str(FPS), "-i", str(img),
         "-t", f"{dur:.3f}", "-vf", vf,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
         "-an", str(out)])
    print("segment", sc["id"], f"{dur:.1f}s")
    return out

def main():
    # overlays
    rain = WORK / "rain.mp4"
    haze_png = WORK / "haze.png"
    sparks = WORK / "sparks.mp4"
    if not rain.exists():
        make_rain_tile(rain)
    if not haze_png.exists():
        make_haze(haze_png)
    if not sparks.exists():
        make_spark_tile(sparks)

    segs = [render_segment(sc) for sc in SCENES]

    # concat segments (video only)
    lst = WORK / "concat.txt"
    lst.write_text("".join(f"file '{s.resolve()}'\n" for s in segs))
    concat = WORK / "concat.mp4"
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", str(concat)])

    # beat flash times: strong on chorus/solo sections, soft elsewhere
    plan_secs = {s["name"]: (s["start"], s["end"], s["energy"]) for s in plan["sections"]}
    strong, soft = [], []
    t = 0.0
    while t < DUR:
        name, (s, e, en) = next((n, v) for n, v in plan_secs.items() if v[0] <= t < v[1])
        if name in ("chorus1", "chorus2", "chorus3", "solo"):
            strong.append(t)
        elif name not in ("intro", "outro"):
            soft.append(t + 2 * BEAT)  # snare backbeat
        t += BEAT

    def enable(times):
        return "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in times) or "0"

    # scene overlay windows (short expressions, safe)
    rain_win = enable([(sc["start"], sc["end"]) for sc in SCENES if sc["overlay"] == "rain"])
    spark_win = enable([(sc["start"], sc["end"]) for sc in SCENES if "spark" in sc["overlay"]])
    haze_win = enable([(sc["start"], sc["end"]) for sc in SCENES
                       if "haze" in sc["overlay"] or "smoke" in sc["overlay"]]) 

    fc = (
        f"[0:v]format=yuv420p,setpts=PTS-STARTPTS[v0];"
        f"[1:v]scale={W}:{H},format=rgba,geq=r='r(X,Y)':a='alpha(X,Y)*0.55',setpts=PTS-STARTPTS[rain];"
        f"[2:v]scale={W}:{H},format=rgba,colorchannelmixer=aa=0.5,setpts=PTS-STARTPTS[sprk];"
        f"[3:v]scale={W}:{H},format=gray,geq=lum='lum(X,Y)':a='255',format=rgba,colorchannelmixer=aa=0.35,setpts=PTS-STARTPTS[haze];"
        f"[v0][sprk]overlay=format=auto:shortest=1:enable='{spark_win}'[v3];"
        f"[v3][rain]overlay=format=auto:shortest=1:enable='{rain_win}'[v4];"
        f"[v4][haze]overlay=format=auto:shortest=1:enable='{haze_win}'[v5];"
        f"[v5]eq=contrast=1.06:saturation=1.10,vignette=PI/4.2,"
        f"noise=alls=5:allf=t,format=yuv420p[vout]"
    )

    # pass A: graded video with rain/sparks/haze overlays (no audio)
    base = WORK / "final_base.mp4"
    if not base.exists():
        run([FFMPEG, "-y",
         "-i", str(concat),
         "-stream_loop", "-1", "-i", str(rain),
         "-stream_loop", "-1", "-i", str(sparks),
         "-loop", "1", "-i", str(haze_png),
         "-filter_complex", fc,
         "-map", "[vout]",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
         "-r", str(FPS), "-s", f"{W}x{H}", "-pix_fmt", "yuv420p",
         "-an", "-t", f"{DUR:.3f}", str(base)])
    print("pass A done:", base)

    # pass B: beat-synced light flashes (baked into a low-res alpha overlay
    # via numpy, then scaled up) + mux the full master audio
    flash = WORK / "flash.mp4"
    if not flash.exists():
        fw, fh = 192, 108
        nframes = int(DUR * FPS)
        # per-second flash level from section energy map
        level = np.zeros(int(DUR) + 2, dtype=np.float32)
        lv = {"intro": 0.0, "verse1": 0.10, "pre1": 0.16, "chorus1": 0.32,
              "verse2": 0.10, "chorus2": 0.32, "solo": 0.26, "bridge": 0.14,
              "chorus3": 0.36, "outro": 0.0}
        for s in plan["sections"]:
            for tt in range(int(s["start"]), min(int(s["end"]) + 1, len(level))):
                level[tt] = lv[s["name"]]
        proc = subprocess.Popen(
            [FFMPEG, "-y", "-f", "rawvideo", "-pix_fmt", "gray",
             "-s", f"{fw}x{fh}", "-r", str(FPS), "-i", "-",
             "-vf", f"scale={W}:{H}:flags=neighbor,format=gray",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "gray",
             str(flash)],
            stdin=subprocess.PIPE)
        for n in range(nframes):
            t = n / FPS
            phase = (t / BEAT) % 1.0
            pulse = np.exp(-phase / 0.022)
            a = int(min(255, 255 * level[min(int(t), len(level) - 1)] * pulse))
            proc.stdin.write(np.full((fh, fw), a, dtype=np.uint8).tobytes())
        proc.stdin.close()
        assert proc.wait() == 0
        print("flash overlay:", flash)

    audio = MEDIA / "final_rock_song.wav"
    out = MEDIA / "final_rock_music_video.mp4"
    run([FFMPEG, "-y",
         "-i", str(base),
         "-stream_loop", "-1", "-i", str(flash),
         "-i", str(audio),
         "-filter_complex", "[0:v]format=gbrp[b];[1:v]format=gray,format=gbrp[fl];[b][fl]blend=all_mode=screen:shortest=1,scale=out_range=tv,format=yuv420p,setparams=range=tv[v]",
         "-map", "[v]", "-map", "2:a",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-r", str(FPS), "-s", f"{W}x{H}", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "320k", "-ar", "44100",
         "-movflags", "+faststart", "-t", f"{DUR:.3f}",
         str(out)])
    print("wrote", out)

if __name__ == "__main__":
    main()
