"""Regenerates every app icon from desktop/logo-source.png (the Tim-Tim logo). Needs Pillow:  pip install pillow
Run from the project folder:  python scripts/make_icons.py"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "desktop" / "logo-source.png"
im = Image.open(SRC).convert("RGB")
W = im.size[0]
k = W / 1254.0                                                         # the logo was drawn at 1254 px; scale the crop for other sizes

# 1) the orb (without the wordmark) as a square on pure black: used for every small icon
box = tuple(int(v * k) for v in (246, 60, 1006, 820))
orb = im.crop(box)
d = ImageDraw.Draw(orb)
d.rectangle([0, int(722 * k), orb.size[0], orb.size[1]], fill=(0, 0, 0))   # wipe the top of the lettering that falls inside the crop
black = lambda s: Image.new("RGB", (s, s), (0, 0, 0))


def sized(img, s):
    return img.resize((s, s), Image.LANCZOS)


def padded(img, s, scale):
    c = black(s); inner = sized(img, int(s * scale)); c.paste(inner, ((s - inner.size[0]) // 2, (s - inner.size[1]) // 2)); return c


def save(img, rel, **kw):
    p = ROOT / rel; p.parent.mkdir(parents=True, exist_ok=True); img.save(p, **kw)


master = sized(orb, 1024)
save(master, "desktop/app-icon.png")
save(master, "mobile/assets/icon.png")
save(padded(orb, 1024, 0.68), "mobile/assets/icon_foreground.png")           # Android adaptive icon: keep the art inside the safe zone
for name, s in (("icon-192.png", 192), ("icon-512.png", 512)):
    save(sized(orb, s), f"desktop/src/icons/{name}")
save(padded(orb, 512, 0.78), "desktop/src/icons/maskable-512.png")
save(sized(orb, 180), "desktop/src/icons/apple-touch-icon.png")
save(sized(orb, 32), "desktop/src/icons/favicon-32.png")
save(sized(orb, 48), "desktop/src/icons/favicon-48.png")
save(sized(orb, 160), "desktop/src/icons/logo-mark.png")
save(sized(orb, 256), "desktop/src/icons/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])

# 2) the full logo with transparent rounded corners: sign-in screen and splash
full = im.resize((640, 640), Image.LANCZOS).convert("RGBA")
mask = Image.new("L", (640, 640), 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, 639, 639], radius=96, fill=255); full.putalpha(mask)
save(full, "desktop/src/icons/logo-full.png")

# 3) Windows / macOS app icons for the Tauri build
t = "desktop/src-tauri/icons"
for name, s in (("32x32.png", 32), ("128x128.png", 128), ("128x128@2x.png", 256), ("icon.png", 512)):
    save(sized(orb, s), f"{t}/{name}")
save(sized(orb, 256), f"{t}/icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
save(sized(orb, 512), f"{t}/icon.icns")
print("icons written from", SRC.name)
