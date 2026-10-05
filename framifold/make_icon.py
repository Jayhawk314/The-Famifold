"""Draws framifold.ico: a dark tile with timeline lanes in the app's lane colours."""
from pathlib import Path
from PIL import Image, ImageDraw

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((8, 8, S - 8, S - 8), radius=44, fill=(22, 26, 36))
for x in range(28, S - 28, 30):  # film-strip holes
    d.rounded_rectangle((x, 26, x + 16, 40), radius=3, fill=(120, 126, 140))
    d.rounded_rectangle((x, S - 40, x + 16, S - 26), radius=3, fill=(120, 126, 140))
lanes = [("#4C78A8", 34, 150), ("#B279A2", 90, 200), ("#F58518", 50, 120), ("#54A24B", 130, 222), ("#E45756", 34, 222)]
for i, (col, a, b) in enumerate(lanes):
    y = 60 + i * 28
    d.rounded_rectangle((a, y, b, y + 18), radius=6, fill=col)
d.line((112, 52, 112, 204), fill=(255, 255, 255), width=5)  # playhead
img.save(Path(__file__).parent / "framifold.ico", sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])
