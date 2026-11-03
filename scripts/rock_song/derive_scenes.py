#!/usr/bin/env python3
"""Fallback: derive any missing scene stills from the already-generated ones
with cinematic transforms (crop, regrade, silhouette, dim, mirror). Only used
for scenes that could not be freshly generated (image-gen rate limit)."""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from song_data import SCENES

ROOT = Path(__file__).resolve().parents[2]
SC = ROOT / "media" / "work" / "scenes"
W, H = 1920, 1080

def load(name):
    return Image.open(SC / name).convert("RGB").resize((W, H), Image.LANCZOS)

def save(img, name):
    img.save(SC / name, quality=92)
    print("derived", name)

def crop_zoom(img, box, zoom=1.0):
    """box = (x0,y0,x1,y1) normalized crop, then resize to 1920x1080."""
    x0, y0, x1, y1 = box
    c = img.crop((int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)))
    return c.resize((W, H), Image.LANCZOS)

def regrade(img, sat=1.1, con=1.1, bri=0.0, tint=None, blur=0):
    img = ImageEnhance.Color(img).enhance(sat)
    img = ImageEnhance.Contrast(img).enhance(con)
    img = ImageEnhance.Brightness(img).enhance(1 + bri)
    if tint:
        r, g, b = tint
        arr = np.asarray(img).astype(np.float32)
        arr[..., 0] = np.clip(arr[..., 0] * r, 0, 255)
        arr[..., 1] = np.clip(arr[..., 1] * g, 0, 255)
        arr[..., 2] = np.clip(arr[..., 2] * b, 0, 255)
        img = Image.fromarray(arr.astype(np.uint8))
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    return img

def silhouette(img, keep=0.35):
    """Crush shadows toward black, keep highlights -> backlit silhouette look."""
    arr = np.asarray(ImageOps.autocontrast(img, cutoff=2)).astype(np.float32) / 255
    lum = arr.mean(axis=2)
    mask = np.clip((lum - keep) / max(1e-3, 1 - keep), 0, 1) ** 1.4
    arr = arr * mask[..., None]
    # warm backlight tint
    arr[..., 0] = np.clip(arr[..., 0] * 1.25 + 0.10, 0, 1)
    arr[..., 2] = np.clip(arr[..., 2] * 0.75, 0, 1)
    return Image.fromarray((arr * 255).astype(np.uint8))

def vignette(img, strength=0.55):
    arr = np.asarray(img).astype(np.float32) / 255
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    m = np.clip(1 - strength * np.clip(d - 0.45, 0, 1) ** 1.6, 0, 1)
    return Image.fromarray((arr * m[..., None] * 255).astype(np.uint8))

DERIVATIONS = {
    # scene -> (source, transform)
    "s10_emotional_close.jpg":   lambda: save(regrade(crop_zoom(load("s04_face_closeup.jpg"), (0.18, 0.05, 0.85, 0.85)), sat=1.05, con=1.15, bri=-0.08, tint=(0.92, 0.97, 1.12)), "s10_emotional_close.jpg"),
    "s11_chorus_sparks.jpg":     lambda: save(regrade(crop_zoom(load("s07_chorus_wide.jpg"), (0.05, 0.10, 0.98, 0.95), ), sat=1.25, con=1.12, bri=0.03, tint=(1.0, 0.98, 1.06)), "s11_chorus_sparks.jpg"),
    "s12_singer_silhouette.jpg": lambda: save(silhouette(crop_zoom(load("s08_singer_power.jpg"), (0.25, 0.02, 0.80, 0.95))), "s12_singer_silhouette.jpg"),
    "s13_solo_hands.jpg":        lambda: save(regrade(crop_zoom(load("s05_guitarist.jpg"), (0.15, 0.35, 0.90, 1.0)), sat=1.2, con=1.18, bri=0.02, tint=(1.12, 1.0, 0.85)), "s13_solo_hands.jpg"),
    "s14_singer_spotlight.jpg":  lambda: save(vignette(regrade(crop_zoom(load("s03_singer_stage.jpg"), (0.28, 0.05, 0.78, 0.90)), sat=1.0, con=1.15, bri=-0.22, tint=(0.85, 0.95, 1.25)), 0.75), "s14_singer_spotlight.jpg"),
    "s15_bridge_dark.jpg":       lambda: save(vignette(regrade(crop_zoom(load("s04_face_closeup.jpg"), (0.05, 0.0, 0.95, 0.9)), sat=0.85, con=1.2, bri=-0.28, tint=(0.9, 0.95, 1.15)), 0.7), "s15_bridge_dark.jpg"),
    "s16_bridge_smoke.jpg":      lambda: save(regrade(load("s01_stage_wide.jpg"), sat=1.0, con=1.05, bri=-0.15, tint=(0.8, 0.9, 1.2), blur=1.5), "s16_bridge_smoke.jpg"),
    "s17_final_pyro.jpg":        lambda: save(regrade(crop_zoom(load("s07_chorus_wide.jpg"), (0.0, 0.0, 1.0, 0.9)), sat=1.3, con=1.15, bri=0.06, tint=(1.15, 1.02, 0.85)), "s17_final_pyro.jpg"),
    "s18_final_closeup.jpg":     lambda: save(regrade(crop_zoom(load("s04_face_closeup.jpg"), (0.30, 0.10, 0.72, 0.75)), sat=1.2, con=1.2, bri=0.02, tint=(1.15, 1.0, 0.88)), "s18_final_closeup.jpg"),
    "s19_outro_edge.jpg":        lambda: save(vignette(regrade(load("s01_stage_wide.jpg"), sat=0.9, con=1.1, bri=-0.25, tint=(1.2, 1.0, 0.8)), 0.6), "s19_outro_edge.jpg"),
    "s20_final_spot.jpg":        lambda: save(vignette(regrade(load("s01_stage_wide.jpg"), sat=0.7, con=1.25, bri=-0.45, tint=(0.85, 0.9, 1.1)), 0.85), "s20_final_spot.jpg"),
}

def main():
    todo = [sc["file"] for sc in SCENES if not (SC / sc["file"]).exists()]
    print("missing scenes:", todo)
    for name in todo:
        if name in DERIVATIONS:
            DERIVATIONS[name]()
        else:
            print("NO derivation for", name)

if __name__ == "__main__":
    main()
