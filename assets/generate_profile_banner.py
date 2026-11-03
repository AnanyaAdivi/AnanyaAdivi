from pathlib import Path
import math
import re

import cairosvg
from PIL import Image, ImageDraw, ImageFilter

WIDTH, HEIGHT = 1200, 320
FRAMES = 24
SOURCE = Path("assets/profile-banner.svg")
OUTPUT = Path("assets/profile-banner.gif")

# Keep the exact existing banner artwork and Didone lettering.
svg = SOURCE.read_text(encoding="utf-8")
svg, removed = re.subn(
    r'<g transform="translate\(196 0\) scale\(\.82 1\)"[\s\S]*?</g>',
    "",
    svg,
)
if removed != 2:
    raise RuntimeError(f"Expected two static network-graphic groups, found {removed}")

base_png = cairosvg.svg2png(
    bytestring=svg.encode("utf-8"),
    output_width=WIDTH,
    output_height=HEIGHT,
)
from io import BytesIO
base = Image.open(BytesIO(base_png)).convert("RGBA")

# A flowing signal curve on the right side of the banner.
segments = [
    ((790, 220), (835, 207), (855, 174), (900, 178)),
    ((900, 178), (944, 181), (965, 211), (1010, 158)),
    ((1010, 158), (1052, 117), (1082, 117), (1145, 88)),
]

def bezier(p0, p1, p2, p3, t):
    u = 1 - t
    return (
        u**3*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t**3*p3[0],
        u**3*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t**3*p3[1],
    )

path = []
for p0, p1, p2, p3 in segments:
    for j in range(41):
        if path and j == 0:
            continue
        path.append(bezier(p0, p1, p2, p3, j / 40))

def point_at(t):
    pos = (len(path) - 1) * (t % 1)
    idx = int(pos)
    frac = pos - idx
    a = path[idx]
    b = path[min(idx + 1, len(path) - 1)]
    return (a[0]*(1-frac) + b[0]*frac, a[1]*(1-frac) + b[1]*frac)

frames = []
for frame_index in range(FRAMES):
    phase = frame_index / FRAMES
    frame = base.copy()

    # Low-contrast chart guides.
    guides = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gd = ImageDraw.Draw(guides)
    for x in range(810, 1160, 60):
        gd.line((x, 78, x, 254), fill=(156, 232, 232, 16), width=1)
    for y in (92, 132, 172, 212, 252):
        gd.line((790, y, 1160, y), fill=(156, 232, 232, 16), width=1)
    frame = Image.alpha_composite(frame, guides)

    # Subtle animated histogram bars.
    bars = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bars)
    for k, x in enumerate((818, 870, 922, 974, 1026, 1078)):
        height = 34 + 18*math.sin(2*math.pi*phase + k*0.85) + (k % 3)*7
        top = 252 - height
        bd.rounded_rectangle((x, top, x+20, 252), radius=3, fill=(103, 201, 210, 22))
    frame = Image.alpha_composite(frame, bars)

    curve = [tuple(map(int, p)) for p in path]
    area = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ImageDraw.Draw(area).polygon(curve + [(1145, 252), (790, 252)], fill=(103, 201, 210, 18))
    frame = Image.alpha_composite(frame, area)

    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ImageDraw.Draw(glow).line(curve, fill=(117, 212, 218, 90), width=10, joint="curve")
    frame = Image.alpha_composite(frame, glow.filter(ImageFilter.GaussianBlur(7)))

    signal = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    sd = ImageDraw.Draw(signal)
    sd.line(curve, fill=(128, 221, 222, 225), width=2, joint="curve")

    # A moving dotted shimmer follows the signal.
    for k in range(28):
        x, y = point_at((k/28 + phase) % 1)
        radius = 1 if k % 3 else 2
        alpha = int(65 + 160*(1 - abs(k-14)/14))
        sd.ellipse((x-radius, y-radius, x+radius, y+radius), fill=(220, 255, 252, alpha))

    # Data nodes pulse gently.
    for k, (x, y) in enumerate(((790, 220), (900, 178), (1010, 158), (1145, 88))):
        pulse = (1 + math.sin(2*math.pi*phase*1.5 + k*1.3)) / 2
        halo = 12 + 5*pulse
        radius = 3.5 + 1.4*pulse
        sd.ellipse((x-halo, y-halo, x+halo, y+halo), fill=(103, 201, 210, int(22+10*pulse)))
        sd.ellipse((x-radius, y-radius, x+radius, y+radius), fill=(165, 242, 237, 235))

    frame = Image.alpha_composite(frame, signal)

    # The traveling light point.
    x, y = point_at(phase)
    moving_glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ImageDraw.Draw(moving_glow).ellipse((x-18, y-18, x+18, y+18), fill=(103, 201, 210, 52))
    frame = Image.alpha_composite(frame, moving_glow.filter(ImageFilter.GaussianBlur(8)))
    ImageDraw.Draw(frame).ellipse((x-4, y-4, x+4, y+4), fill=(230, 255, 253, 255))

    # A pair of slow-moving particles adds depth without distracting from the title.
    d = ImageDraw.Draw(frame)
    for offset, baseline, amplitude, radius in ((0.16, 112, 17, 2.4), (0.57, 245, 10, 1.8)):
        t = (phase + offset) % 1
        px = 810 + 335*t
        py = baseline + amplitude*math.sin(2*math.pi*(t+0.15))
        d.ellipse((px-radius, py-radius, px+radius, py+radius), fill=(181, 240, 234, 210))

    frames.append(frame.convert("RGB"))

# Use one shared palette so static banner pixels do not flicker between frames.
palette_source = frames[0].quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
indexed = [frame.quantize(palette=palette_source, dither=Image.Dither.NONE) for frame in frames]
indexed[0].save(
    OUTPUT,
    save_all=True,
    append_images=indexed[1:],
    duration=110,
    loop=0,
    disposal=1,
    optimize=True,
)
print(f"Generated {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")
