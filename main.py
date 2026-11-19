#!/usr/bin/env python3
"""news-image-20261118: one front page summing up Wednesday 18 November 2026.

Draws a 1024x1024 PNG to $MAKEFUN_OUTPUT_DIR/entry.png (default: out/).
Pure Pillow drawing, no network, no randomness: two runs write identical bytes.

Design (deliberately NOT the v2/v3 black-band reskin):
  - Broadsheet masthead on cream: giant navy date, red rules, no black band.
  - A navy "DAY IN FIGURES" band sits directly under the masthead (v2/v3 put
    the figures strip at the bottom); the top of the page is date + numbers.
  - 3 equal illustrated leads, 8 illustrated grid stories (4x2), 21-item
    "ALSO ON WEDNESDAY" list in two columns, world map with leader-line badges,
    a "TOMORROW - THURSDAY 19 NOVEMBER" box (labelled UPCOMING), source line.
  - 32 stories total, 11 illustrated. Every word comes from NEWS-20261118.md.
  - All image text is plain ASCII (the bundled Aileron font has no em/en
    dashes, euro sign or bullet glyphs); hyphens only.
"""

import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1024, 1024

# --- palette ---------------------------------------------------------------
CREAM = (247, 241, 222)   # paper
PAPER2 = (238, 230, 203)  # slightly darker paper for panels
INK = (22, 24, 30)        # near-black text
NAVY = (18, 38, 76)       # masthead date, figures band
NAVY2 = (28, 58, 108)     # lighter navy
RED = (178, 34, 34)       # accents, numbers, conflict
RED2 = (205, 60, 50)
GOLD = (184, 134, 11)
GREEN = (34, 110, 72)
TEAL = (14, 110, 110)
AMBER = (176, 110, 10)
PURPLE = (96, 60, 130)
GREY = (74, 74, 70)       # sub-text
HAIR = (150, 140, 115)    # hairlines
SEA = (168, 196, 214)     # map sea
LAND = (232, 222, 190)    # map land
LAND2 = (222, 210, 172)

CAT = {  # category -> (label, colour)
    "WAR": ("WAR", RED),
    "DIP": ("DIPLOMACY", NAVY2),
    "POL": ("POLITICS", GREEN),
    "ECO": ("ECONOMY", TEAL),
    "WEA": ("WEATHER", AMBER),
    "SPO": ("SPORT", PURPLE),
}

# --- fonts -----------------------------------------------------------------
_FONTS = {}


def font(size):
    """Aileron scalable font bundled with Pillow; cached by size."""
    if size not in _FONTS:
        _FONTS[size] = ImageFont.load_default(size)
    return _FONTS[size]


def text_w(s, size):
    return font(size).getlength(s)


def draw_bold(d, xy, s, size, fill, weight=1):
    """Fake-bold: overprint the text on a small offset grid."""
    x, y = xy
    f = font(size)
    for dx in range(weight + 1):
        for dy in range(weight + 1):
            d.text((x + dx, y + dy), s, font=f, fill=fill)


def draw_bold_c(d, cx, y, s, size, fill, weight=1):
    """Bold text centred on cx."""
    w = text_w(s, size)
    draw_bold(d, (cx - w / 2, y), s, size, fill, weight)


def wrap(s, size, maxw):
    """Greedy word wrap to maxw pixels; returns list of lines."""
    words = s.split(" ")
    lines, cur = [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if text_w(trial, size) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def para(d, x, y, s, size, fill, maxw, weight=0, leading=None):
    """Draw a wrapped paragraph; returns y just below the last line."""
    lh = leading if leading is not None else int(size * 1.22)
    for line in wrap(s, size, maxw):
        if weight:
            draw_bold(d, (x, y), line, size, fill, weight)
        else:
            d.text((x, y), line, font=font(size), fill=fill)
        y += lh
    return y


def fit_size(s, size, maxw, minimum=9):
    """Largest size <= size at which s fits maxw."""
    while size > minimum and text_w(s, size) > maxw:
        size -= 1
    return size


def hline(d, x0, x1, y, fill, wdt=1):
    d.rectangle([x0, y, x1, y + wdt - 1], fill=fill)


def badge(d, cx, cy, r, num, fill=RED, fg=(255, 255, 255)):
    """Numbered circle badge, number centred."""
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=(255, 255, 255), width=2)
    s = str(num)
    fs = fit_size(s, r + 4, r * 2 - 4)
    draw_bold_c(d, cx + 1, cy - fs * 0.72, s, fs, fg, 1)


def sky(d, box, top, mid, bot):
    """Three-band vertical sky gradient inside box."""
    x, y, w, h = box
    third = max(1, h // 3)
    d.rectangle([x, y, x + w, y + third], fill=top)
    d.rectangle([x, y + third, x + w, y + 2 * third], fill=mid)
    d.rectangle([x, y + 2 * third, x + w, y + h], fill=bot)


def sun(d, cx, cy, r, fill=(250, 210, 90)):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
    d.ellipse([cx - r - 5, cy - r - 5, cx + r + 5, cy + r + 5], outline=fill, width=2)


def cloud(d, x, y, s, fill=(255, 255, 255)):
    d.ellipse([x, y, x + 3 * s, y + s], fill=fill)
    d.ellipse([x + s // 2, y - s // 2, x + 3 * s, y + s // 2], fill=fill)
    d.ellipse([x + s, y - s // 3, x + 4 * s, y + s], fill=fill)


def sea(d, box, fill=(38, 84, 124)):
    x, y, w, h = box
    d.rectangle([x, y, x + w, y + h], fill=fill)
    for i, wy in enumerate(range(y + 6, y + h - 4, 12)):
        off = (i % 2) * 8
        for wx in range(x + 4 + off, x + w - 14, 26):
            d.line([wx, wy, wx + 12, wy], fill=(210, 225, 235), width=2)


def burst(d, cx, cy, r, fill=(255, 170, 40)):
    """Starburst: 8 spikes."""
    import math
    pts = []
    for i in range(16):
        ang = math.pi * i / 8
        rr = r if i % 2 == 0 else r * 0.38
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    d.polygon(pts, fill=fill)
    d.ellipse([cx - r * 0.3, cy - r * 0.3, cx + r * 0.3, cy + r * 0.3],
              fill=(255, 240, 180))


def building(d, x, ybase, w, h, fill, lit=(250, 210, 110)):
    """One skyline tower with lit windows."""
    d.rectangle([x, ybase - h, x + w, ybase], fill=fill)
    for wy in range(ybase - h + 6, ybase - 6, 12):
        for wx in range(x + 4, x + w - 5, 10):
            if (wx * 7 + wy * 3) % 5 < 2:
                d.rectangle([wx, wy, wx + 4, wy + 5], fill=lit)

# --- illustrated scenes (layered: sky, mid-ground, foreground, figures) -----
# Each draws inside box (x, y, w, h) and is recognisable without its caption.

def scene_gulf(d, x, y, w, h):
    """1. Gulf: night sky, drones with red trails, interceptor bursts, sea."""
    sky(d, (x, y, w, h), (12, 22, 48), (24, 40, 76), (52, 72, 110))
    sun(d, x + w - 26, y + 22, 11, fill=(235, 220, 180))
    cloud(d, x + 12, y + 14, 7, fill=(70, 88, 120))
    cloud(d, x + w // 2 - 10, y + 30, 6, fill=(60, 78, 110))
    sea(d, (x, y + h - 26, w, 26), fill=(20, 48, 84))
    # coastline silhouette
    d.polygon([(x, y + h - 26), (x + w * 0.3, y + h - 44), (x + w * 0.55, y + h - 34),
               (x + w * 0.8, y + h - 46), (x + w, y + h - 38), (x + w, y + h - 26)],
              fill=(16, 26, 44))
    # three drones with red trails
    for dx, dy, ln in ((0.22, 0.30, 34), (0.52, 0.20, 28), (0.74, 0.38, 40)):
        cx, cy = x + int(w * dx), y + int(h * dy)
        d.line([cx - ln, cy + 8, cx, cy], fill=(230, 60, 50), width=3)
        d.ellipse([cx - 7, cy - 4, cx + 7, cy + 4], fill=(30, 30, 34))
        d.ellipse([cx + 8, cy - 2, cx + 14, cy + 2], fill=(230, 60, 50))
        d.ellipse([cx - 2, cy - 7, cx + 2, cy - 2], fill=(120, 120, 130))
    burst(d, x + int(w * 0.38), y + int(h * 0.52), 13)
    burst(d, x + int(w * 0.86), y + int(h * 0.30), 10, fill=(255, 200, 90))


def scene_shenzhen(d, x, y, w, h):
    """2. Shenzhen: dusk sky, layered towers, three flags, red carpet."""
    sky(d, (x, y, w, h), (58, 44, 92), (150, 78, 84), (232, 148, 88))
    sun(d, x + w // 2, y + h - 52, 16)
    # far towers
    for bx, bw, bh in ((0.04, 0.10, 0.52), (0.20, 0.08, 0.66), (0.62, 0.09, 0.58),
                       (0.80, 0.11, 0.46)):
        building(d, x + int(w * bx), y + h - 30, int(w * bw), int(h * bh),
                 fill=(52, 44, 78), lit=(220, 170, 110))
    # near towers
    for bx, bw, bh in ((0.12, 0.12, 0.42), (0.38, 0.10, 0.50), (0.70, 0.12, 0.40)):
        building(d, x + int(w * bx), y + h - 30, int(w * bw), int(h * bh),
                 fill=(30, 26, 52), lit=(250, 210, 110))
    # red carpet + three flags
    d.rectangle([x, y + h - 30, x + w, y + h], fill=(120, 30, 34))
    d.rectangle([x, y + h - 30, x + w, y + h - 26], fill=(200, 170, 90))
    for i, cols in enumerate((((200, 40, 40),), ((200, 40, 40), (255, 255, 255), (40, 60, 160)),
                              ((255, 255, 255), (40, 80, 200), (200, 40, 40)))):
        fx = x + int(w * (0.30 + 0.20 * i))
        fy = y + h - 66
        d.rectangle([fx, fy, fx + 2, y + h - 30], fill=(240, 240, 230))
        fh = 22
        n = len(cols)
        for j, c in enumerate(cols):
            d.rectangle([fx + 2, fy + j * fh // n, fx + 26, fy + (j + 1) * fh // n], fill=c)
        d.rectangle([fx + 2, fy, fx + 26, fy + fh], outline=(90, 80, 60))


def scene_peltola(d, x, y, w, h):
    """3. Alaska: blue sky, mountains, Alaska map shape, ballot box + check."""
    sky(d, (x, y, w, h), (64, 120, 178), (120, 168, 208), (190, 214, 228))
    sun(d, x + 30, y + 24, 13)
    cloud(d, x + w - 78, y + 12, 8)
    # mountains
    d.polygon([(x, y + h - 34), (x + w * 0.22, y + h * 0.34), (x + w * 0.44, y + h - 34)],
              fill=(52, 84, 128))
    d.polygon([(x + w * 0.16, y + h - 34), (x + w * 0.30, y + h * 0.52),
               (x + w * 0.44, y + h - 34)], fill=(235, 242, 248))
    d.polygon([(x + w * 0.42, y + h - 34), (x + w * 0.66, y + h * 0.26),
               (x + w * 0.92, y + h - 34)], fill=(44, 72, 112))
    d.polygon([(x + w * 0.58, y + h - 34), (x + w * 0.66, y + h * 0.42),
               (x + w * 0.74, y + h - 34)], fill=(235, 242, 248))
    d.rectangle([x, y + h - 34, x + w, y + h], fill=(34, 96, 66))
    # ballot box with big check
    bx, by, bw, bh = x + w - 92, y + h - 76, 74, 46
    d.rectangle([bx, by, bx + bw, by + bh], fill=(240, 236, 222),
                outline=(30, 30, 40), width=3)
    d.rectangle([bx + 8, by - 8, bx + bw - 8, by + 2], fill=(30, 30, 40))
    d.line([bx + 14, by + 26, bx + 30, by + 38, bx + 62, by + 8],
           fill=(178, 34, 34), width=6)
    # stars
    for sx, sy in ((0.12, 0.22), (0.30, 0.14), (0.46, 0.30)):
        burst(d, x + int(w * sx), y + int(h * sy), 6, fill=(250, 210, 110))


def scene_kerch(d, x, y, w, h):
    """4. Kerch: night, bridge deck, collapsed middle span, smoke, drones.
    All offsets are fractions of the scene box, so nothing bleeds above
    the frame (the grid scenes are short)."""
    sky(d, (x, y, w, h), (10, 16, 38), (22, 34, 66), (48, 62, 100))
    sun(d, x + 26, y + 16, 9, fill=(225, 215, 180))
    sea(d, (x, y + h - 14, w, 14), fill=(18, 42, 74))
    deck_y = y + h - 26
    # intact deck left and right
    d.rectangle([x, deck_y, x + int(w * 0.36), deck_y + 6], fill=(120, 118, 112))
    d.rectangle([x + int(w * 0.64), deck_y, x + w, deck_y + 6], fill=(120, 118, 112))
    # pillars (short, down to the sea band)
    for px in (0.08, 0.24, 0.76, 0.92):
        d.rectangle([x + int(w * px) - 3, deck_y + 6, x + int(w * px) + 3, y + h - 14],
                    fill=(90, 88, 82))
    # collapsed span falling into the sea
    d.polygon([(x + int(w * 0.36), deck_y), (x + int(w * 0.50), deck_y + 14),
               (x + int(w * 0.54), deck_y + 10), (x + int(w * 0.40), deck_y - 2)],
              fill=(150, 146, 138))
    d.polygon([(x + int(w * 0.64), deck_y), (x + int(w * 0.52), deck_y + 12),
               (x + int(w * 0.48), deck_y + 8), (x + int(w * 0.60), deck_y - 2)],
              fill=(130, 126, 118))
    burst(d, x + int(w * 0.50), deck_y + 2, 11)
    # smoke plumes (above the deck)
    for sx, sy, sr in ((0.44, 0.28, 9), (0.52, 0.24, 10), (0.58, 0.30, 8)):
        d.ellipse([x + int(w * sx) - sr, y + int(h * sy) - sr,
                   x + int(w * sx) + sr, y + int(h * sy) + sr], fill=(120, 122, 126))
    # drone silhouettes
    for dx, dy in ((0.18, 0.16), (0.82, 0.12)):
        cx, cy = x + int(w * dx), y + int(h * dy)
        d.ellipse([cx - 7, cy - 3, cx + 7, cy + 3], fill=(20, 20, 24))
        d.ellipse([cx + 8, cy - 2, cx + 13, cy + 2], fill=(230, 60, 50))


def scene_xavier(d, x, y, w, h):
    """5. Cyclone Xavier: spiral bands over a blue sea, island, rain."""
    sky(d, (x, y, w, h), (30, 60, 96), (66, 104, 142), (120, 152, 178))
    sea(d, (x, y + h - 30, w, 30), fill=(28, 74, 116))
    cx, cy = x + w // 2, y + h // 2
    # spiral: concentric arc bands (radii clamped to the scene box)
    for r, col in ((26, (235, 240, 245)), (21, (200, 214, 226)), (16, (235, 240, 245)),
                   (11, (170, 190, 208)), (6, (235, 240, 245))):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=6)
    d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=(250, 210, 110))
    # island bottom-left with palm (all inside the box)
    d.ellipse([x + 8, y + h - 26, x + 66, y + h - 12], fill=(52, 128, 74))
    d.rectangle([x + 34, y + h - 44, x + 38, y + h - 24], fill=(110, 80, 40))
    for ang in (-40, -10, 15, 35):
        import math
        a = math.radians(ang - 90)
        d.line([x + 36, y + h - 44, x + 36 + int(14 * math.cos(a)),
                y + h - 44 + int(14 * math.sin(a))], fill=(34, 110, 60), width=3)
    # rain streaks
    for rx in range(x + w - 60, x + w - 8, 12):
        d.line([rx, y + 10, rx - 6, y + 30], fill=(220, 230, 240), width=2)


def scene_anthropic(d, x, y, w, h):
    """6. Anthropic IPO: dark board, green rising chart, gold coins."""
    d.rectangle([x, y, x + w, y + h], fill=(16, 32, 40))
    for gy in range(y + 8, y + h - 6, 16):
        d.line([x + 6, gy, x + w - 6, gy], fill=(34, 56, 66), width=1)
    pts = [(x + int(w * 0.30), y + int(h * 0.72)), (x + int(w * 0.46), y + int(h * 0.58)),
           (x + int(w * 0.62), y + int(h * 0.42)), (x + int(w * 0.78), y + int(h * 0.52)),
           (x + w - 12, y + int(h * 0.18))]
    d.line(pts, fill=(64, 200, 120), width=5)
    for px, py in pts[1:-1]:
        d.ellipse([px - 4, py - 4, px + 4, py + 4], fill=(64, 200, 120))
    # arrowhead
    ex, ey = pts[-1]
    d.polygon([(ex, ey), (ex - 16, ey + 4), (ex - 6, ey + 16)],
              fill=(64, 200, 120))
    # gold coin stack, bottom-left (clear of the chart)
    for i in range(3):
        cy = y + h - 10 - i * 7
        d.ellipse([x + 12, cy - 6, x + 44, cy + 6], fill=(232, 178, 44),
                  outline=(150, 105, 20), width=2)


def scene_gta(d, x, y, w, h):
    """7. GTA VI: dusk city, neon sign, palms, car."""
    sky(d, (x, y, w, h), (46, 30, 84), (150, 64, 120), (240, 130, 90))
    sun(d, x + w - 30, y + 18, 12, fill=(255, 190, 110))
    street_y = y + h - 18
    for bx, bw, bh in ((0.02, 0.12, 0.44), (0.18, 0.10, 0.58), (0.52, 0.12, 0.50),
                       (0.70, 0.11, 0.62), (0.86, 0.12, 0.40)):
        bh_px = min(int(h * bh), h - 26)
        building(d, x + int(w * bx), street_y, int(w * bw), bh_px,
                 fill=(36, 24, 58), lit=(255, 190, 120))
    # neon sign
    d.rectangle([x + int(w * 0.30), y + 6, x + int(w * 0.68), y + 26],
                fill=(24, 12, 40), outline=(255, 90, 190), width=3)
    draw_bold(d, (x + int(w * 0.34), y + 9), "VICE CITY", 14, (255, 140, 210), 1)
    # palms
    import math
    for px in (0.10, 0.92):
        tx, ty = x + int(w * px), street_y
        d.rectangle([tx - 2, ty - 22, tx + 2, ty], fill=(60, 40, 20))
        for ang in (-70, -30, 10, 50):
            a = math.radians(ang - 90)
            d.line([tx, ty - 22, tx + int(14 * math.cos(a)), ty - 22 + int(14 * math.sin(a))],
                   fill=(30, 120, 60), width=3)
    # street + car
    d.rectangle([x, street_y, x + w, y + h], fill=(24, 24, 30))
    d.line([x, y + h - 8, x + w, y + h - 8], fill=(250, 210, 90), width=2)
    cx, cy = x + w // 2, y + h - 16
    d.polygon([(cx - 34, cy), (cx - 26, cy - 12), (cx + 22, cy - 12), (cx + 34, cy)],
              fill=(220, 40, 90))
    d.rectangle([cx - 36, cy, cx + 36, cy + 8], fill=(200, 30, 80))
    for wx in (-22, 22):
        d.ellipse([cx + wx - 7, cy + 6, cx + wx + 7, cy + 16], fill=(12, 12, 14))


def scene_alcaraz(d, x, y, w, h):
    """8. ATP Finals: tennis court, net, ball with motion lines, racket."""
    sky(d, (x, y, w, h), (70, 120, 180), (120, 165, 205), (180, 205, 225))
    # court in perspective
    d.polygon([(x + 12, y + h - 8), (x + w - 12, y + h - 8),
               (x + w - 34, y + h * 0.42), (x + 34, y + h * 0.42)], fill=(44, 110, 74))
    d.polygon([(x + 12, y + h - 8), (x + w - 12, y + h - 8),
               (x + w - 34, y + h * 0.42), (x + 34, y + h * 0.42)],
              outline=(255, 255, 255), width=2)
    d.line([x + w // 2, y + h - 8, x + w // 2, y + h * 0.42], fill=(255, 255, 255), width=2)
    # net
    d.rectangle([x + 26, y + h * 0.52, x + w - 26, y + h * 0.52 + 14],
                fill=(30, 30, 36))
    d.line([x + 26, y + h * 0.52, x + w - 26, y + h * 0.52], fill=(255, 255, 255), width=2)
    # racket (arc + handle, inside the box)
    d.ellipse([x + w - 62, y + 8, x + w - 18, y + 44], outline=(200, 60, 40), width=5)
    d.line([x + w - 40, y + 40, x + w - 52, y + 56], fill=(140, 90, 40), width=5)
    # ball with motion lines
    bx, by = x + int(w * 0.30), y + int(h * 0.26)
    for mx in range(3):
        d.line([bx - 34 - mx * 10, by + 4, bx - 18 - mx * 10, by + 4],
               fill=(255, 255, 255), width=2)
    d.ellipse([bx - 10, by - 10, bx + 10, by + 10], fill=(210, 230, 60),
              outline=(120, 140, 30), width=2)
    d.arc([bx - 10, by - 10, bx + 10, by + 10], 300, 60, fill=(120, 140, 30), width=2)


def scene_eu(d, x, y, w, h):
    """9. EU loan: blue field, circle of gold stars, coin stack, bank columns."""
    d.rectangle([x, y, x + w, y + h], fill=(28, 58, 128))
    import math
    cx, cy, r = x + w // 2, y + h // 2 - 4, min(18, h // 2 - 10)
    for i in range(12):
        a = math.radians(i * 30 - 90)
        burst(d, cx + int(r * math.cos(a)), cy + int(r * math.sin(a)), 4,
              fill=(250, 210, 90))
    # bank columns at the bottom
    d.rectangle([x, y + h - 30, x + w, y + h], fill=(18, 38, 88))
    for i in range(5):
        colx = x + 12 + i * int((w - 24) / 5)
        d.rectangle([colx, y + h - 28, colx + 8, y + h - 6], fill=(232, 222, 190))
    d.rectangle([x + 8, y + h - 32, x + w - 8, y + h - 28], fill=(232, 222, 190))
    # coin stack right
    for i in range(3):
        cy2 = y + h - 14 - i * 8
        d.ellipse([x + w - 46, cy2 - 6, x + w - 14, cy2 + 6], fill=(232, 178, 44),
                  outline=(150, 105, 20), width=2)


def scene_jeffries(d, x, y, w, h):
    """10. Jeffries: Capitol dome, gavel, stars and stripes bunting.
    All heights are fractions of the scene box (grid scenes are short)."""
    sky(d, (x, y, w, h), (64, 110, 170), (130, 170, 205), (200, 216, 228))
    sun(d, x + 22, y + 14, 9)
    ground_y = y + h - 8
    # Capitol: base + columns + dome, all above the ground strip
    d.rectangle([x + 16, ground_y - 8, x + w - 16, ground_y], fill=(232, 228, 216))
    for i in range(6):
        colx = x + 26 + i * int((w - 52) / 6)
        d.rectangle([colx, ground_y - 18, colx + 7, ground_y - 8],
                    fill=(250, 246, 236))
    d.rectangle([x + 20, ground_y - 20, x + w - 20, ground_y - 18],
                fill=(220, 214, 196))
    dcx = x + w // 2
    d.pieslice([dcx - 13, ground_y - 38, dcx + 13, ground_y - 20], 180, 360,
               fill=(240, 236, 224))
    d.rectangle([dcx - 2, ground_y - 42, dcx + 2, ground_y - 38],
                fill=(220, 214, 196))
    d.ellipse([dcx - 3, ground_y - 46, dcx + 3, ground_y - 40],
              fill=(200, 170, 90))
    d.rectangle([x, ground_y, x + w, y + h], fill=(34, 96, 66))
    # gavel bottom-right
    gx, gy = x + w - 52, y + h - 8
    d.rectangle([gx, gy - 5, gx + 34, gy + 2], fill=(110, 70, 30))
    d.line([gx + 8, gy + 2, gx + 22, gy + 6], fill=(140, 90, 40), width=4)
    # bunting
    for i, c in enumerate(((178, 34, 34), (255, 255, 255), (28, 58, 128)) * 3):
        fx = x + 8 + i * 14
        d.polygon([(fx, y + 4), (fx + 14, y + 4), (fx + 7, y + 12)], fill=c)


def scene_tara(d, x, y, w, h):
    """11. Tara Gas: LPG tanker with sphere tanks, smoke, rescue boat."""
    sky(d, (x, y, w, h), (90, 130, 170), (150, 180, 205), (205, 220, 230))
    cloud(d, x + 10, y + 8, 6)
    sea(d, (x, y + h - 28, w, 28), fill=(30, 76, 118))
    # smoke plume rising from the funnel (right side, inside the box)
    for sx, sy, sr in ((0.82, 0.30, 8), (0.88, 0.22, 10), (0.76, 0.32, 7)):
        d.ellipse([x + int(w * sx) - sr, y + int(h * sy) - sr,
                   x + int(w * sx) + sr, y + int(h * sy) + sr], fill=(110, 112, 116))
    burst(d, x + int(w * 0.42), y + int(h * 0.34), 10, fill=(255, 170, 40))
    # tanker hull + LPG spheres (all inside the box)
    hy = y + h - 30
    d.polygon([(x + 8, hy), (x + w - 8, hy), (x + w - 22, hy + 14), (x + 20, hy + 14)],
              fill=(150, 40, 36))
    d.rectangle([x + 8, hy, x + w - 8, hy + 5], fill=(200, 60, 50))
    for i, sx in enumerate((0.24, 0.46, 0.68)):
        cx = x + int(w * sx)
        d.ellipse([cx - 15, hy - 22, cx + 15, hy + 2], fill=(232, 228, 216),
                  outline=(90, 90, 90), width=2)
        d.arc([cx - 15, hy - 22, cx + 15, hy + 2], 200, 340, fill=(150, 150, 150), width=2)
    # funnel
    d.rectangle([x + w - 34, hy - 24, x + w - 18, hy], fill=(40, 40, 46))
    d.rectangle([x + w - 34, hy - 24, x + w - 18, hy - 19], fill=(230, 180, 60))
    # rescue boat + life ring
    bx, by = x + 22, y + h - 18
    d.polygon([(bx, by), (bx + 34, by), (bx + 28, by + 8), (bx + 6, by + 8)],
              fill=(230, 120, 30))
    d.ellipse([bx + 44, by - 4, bx + 58, by + 10], outline=(255, 255, 255), width=4)
    d.ellipse([bx + 44, by - 4, bx + 58, by + 10], outline=(230, 60, 40), width=2)


SCENES = {
    1: scene_gulf, 2: scene_shenzhen, 3: scene_peltola, 4: scene_kerch,
    5: scene_xavier, 6: scene_anthropic, 7: scene_gta, 8: scene_alcaraz,
    9: scene_eu, 10: scene_jeffries, 11: scene_tara,
}


# --- world map ---------------------------------------------------------------
# Rough lon/lat continent outlines (own approximations, recognisable at a
# glance); projected linearly into the map box.
CONTINENTS = [
    [(-168, 66), (-140, 70), (-120, 72), (-95, 80), (-80, 73), (-65, 60),
     (-55, 47), (-70, 42), (-75, 35), (-80, 26), (-90, 21), (-97, 16),
     (-105, 20), (-115, 30), (-125, 40), (-125, 49), (-140, 60), (-165, 60)],
    [(-58, 64), (-45, 60), (-30, 68), (-22, 70), (-40, 76), (-58, 76)],
    [(-80, 10), (-60, 8), (-50, 0), (-35, -8), (-40, -20), (-48, -28),
     (-58, -35), (-65, -40), (-70, -52), (-73, -40), (-77, -20), (-80, -5)],
    [(-17, 15), (-10, 30), (0, 35), (10, 37), (20, 32), (30, 31), (35, 28),
     (43, 12), (51, 11), (48, 0), (40, -12), (35, -25), (28, -33), (18, -35),
     (12, -18), (9, 4), (-8, 5)],
    [(-10, 36), (-9, 43), (-2, 48), (0, 50), (5, 53), (8, 57), (10, 59),
     (18, 56), (21, 55), (24, 59), (28, 60), (30, 65), (40, 68), (45, 60),
     (40, 55), (35, 50), (30, 46), (28, 41), (23, 40), (19, 42), (12, 44),
     (8, 44), (3, 42), (0, 38)],
    [(30, 65), (45, 68), (60, 70), (80, 73), (110, 76), (140, 72), (160, 66),
     (170, 60), (162, 55), (158, 50), (142, 45), (140, 38), (130, 35),
     (127, 33), (122, 30), (120, 25), (110, 20), (108, 12), (105, 8),
     (100, 6), (97, 10), (92, 16), (90, 22), (86, 20), (80, 15), (77, 8),
     (75, 20), (70, 25), (66, 25), (60, 25), (56, 26), (52, 28), (48, 30),
     (44, 30), (40, 35), (35, 36), (30, 42), (30, 55)],
    [(113, -22), (114, -30), (115, -35), (124, -33), (130, -32), (137, -35),
     (140, -38), (147, -39), (150, -37), (153, -27), (153, -20), (146, -19),
     (142, -11), (136, -12), (132, -11), (126, -14), (122, -17)],
]

# (number, lon, lat, category, badge offset dx, dy into empty ocean)
MAP_DOTS = [
    (1, 47.9, 29.4, "WAR", (-30, -30)),
    (2, 114.1, 22.5, "DIP", (36, 16)),
    (3, -150.0, 64.0, "POL", (-42, -24)),
    (4, 36.5, 45.3, "WAR", (-36, -28)),
    (5, -160.0, -21.0, "WEA", (42, 20)),
    (6, -74.0, 40.7, "ECO", (32, -26)),
    (7, 7.7, 45.1, "SPO", (-46, 20)),
    (8, 4.35, 50.85, "POL", (-40, -32)),
    (9, -77.0, 38.9, "POL", (30, 28)),
    (10, 56.5, 26.5, "WAR", (32, 30)),
    (11, 34.5, 31.5, "WAR", (-32, 26)),
    (12, 121.0, 14.6, "DIP", (36, -18)),
    (13, 29.0, 41.0, "POL", (-44, -34)),
    (14, 39.0, 9.0, "WAR", (30, 28)),
    (15, 4.3, 52.1, "POL", (44, -30)),
]


def draw_map(d, x, y, w, h):
    """World map: sea, rough continents, numbered badges on leader lines."""
    d.rectangle([x, y, x + w, y + h], fill=SEA, outline=NAVY, width=2)
    # graticule
    for gx in range(x + w // 6, x + w, w // 6):
        d.line([gx, y, gx, y + h], fill=(190, 210, 224), width=1)
    for gy in range(y + h // 4, y + h, h // 4):
        d.line([x, gy, x + w, gy], fill=(190, 210, 224), width=1)

    def proj(lon, lat):
        px = x + (lon + 170.0) / 360.0 * w
        py = y + (85.0 - lat) / 145.0 * h
        return (px, py)

    for poly in CONTINENTS:
        d.polygon([proj(lon, lat) for lon, lat in poly], fill=LAND,
                  outline=(170, 158, 120))
    # small labels for the big oceans, so the map reads at a glance
    for label, lx, ly in (("PACIFIC", -150, -8), ("ATLANTIC", -30, 5),
                          ("INDIAN OCEAN", 75, -28), ("ARCTIC", 55, 80)):
        px, py = proj(lx, ly)
        d.text((px, py), label, font=font(10), fill=(90, 115, 140))
    for num, lon, lat, cat, (dx, dy) in MAP_DOTS:
        px, py = proj(lon, lat)
        bx, by = px + dx, py + dy
        bx = min(max(bx, x + 12), x + w - 12)
        by = min(max(by, y + 12), y + h - 12)
        d.line([px, py, bx, by], fill=(90, 90, 90), width=1)
        d.ellipse([px - 3, py - 3, px + 3, py + 3], fill=CAT[cat][1])
        badge(d, bx, by, 10, num, fill=CAT[cat][1])


# --- content -----------------------------------------------------------------
LEADS = [
    (1, "WAR", "GULF: IRAN HITS KUWAIT AND BAHRAIN",
     "Tehran fires drones at a US base in Kuwait and sites in Bahrain after a US "
     "jet struck Qeshm Island. First Kuwait attack since September."),
    (2, "DIP", "SHENZHEN: XI GREETS TRUMP ON TARMAC",
     "Xi meets Trump at Air Force One; Xi and Putin hold talks a day before the "
     "first Trump-Xi-Putin summit on Thursday."),
    (3, "POL", "PELTOLA WINS ALASKA - DEMOCRATS 56-44",
     "Democrat beats two-term Republican Sullivan in the last Senate race. "
     "Democrats take a 56-44 majority."),
]

GRID = [
    (4, "WAR", "KERCH: RECORD 1,441 DRONES IN ONE NIGHT",
     "Second-day strikes; Russia hits Izmail"),
    (5, "WEA", "CYCLONE XAVIER: 315 KM/H GUSTS",
     "Cat 5 storm batters Cook Islands."),
    (6, "ECO", "ANTHROPIC IPO: $83, BIGGEST EVER",
     "$81.3BN raised; trading starts Thu."),
    (7, "ECO", "GTA VI ROLLS OUT AFTER 13 YEARS",
     "Midnight launch; Take-Two +6.2%."),
    (8, "SPO", "ALCARAZ INTO ATP FINALS SEMIS",
     "Medvedev 6-2, 6-4; Tiafoe wins first."),
    (9, "POL", "EU: 45 BILLION EUROS FOR UKRAINE",
     "New 2027 loan; four states opt out."),
    (10, "POL", "JEFFRIES NOMINATED SPEAKER 251-11",
     "First Black Speaker if elected 3 Jan."),
    (11, "WAR", "TARA GAS: 1 MISSING, 11 HURT",
     "Tanker hit twice; 24 crew rescued."),
]

ALSO = [
    (12, "GAZA TRUCE NEAR COLLAPSE, BOARD WARNS"),
    (13, "TRUMP CLAIMS BIG PHILIPPINES DEAL"),
    (14, "IMAMOGLU: 2 MORE YEARS, NEW BAN"),
    (15, "ETHIOPIA-ERITREA BORDER CLASHES"),
    (16, "ICJ TO RULE THURSDAY ON MYANMAR"),
    (17, "SLOVAKIA: THOUSANDS PROTEST FICO"),
    (18, "WAYMO PULLED OFF US FREEWAYS"),
    (19, "MARKETS: DOW -1.1%, S&P -0.2%"),
    (20, "FED: INFLATION RISKS IN FOCUS"),
    (21, "IRAQ: MILITIA TOLD TO LEAVE BY FRIDAY"),
    (22, "EU-INDONESIA TRADE DEALS APPROVED"),
    (23, "YEMEN: 64 CHILDREN KILLED SINCE SEPT"),
    (24, "ATALAY MUST BE RELEASED, COURT RULES"),
    (25, "UKRAINE: 141 RUSSIAN DRONES OVERNIGHT"),
    (26, "MOSSAD CHIEF LOBBIED FOR IRAN STRIKES"),
    (27, "BAHRAIN REFINERY BACK ABOVE 80%"),
    (28, "US WEIGHS DISCLOSING CHINA AI USE"),
    (29, "ECB TO DISCUSS RAISING RESERVE RULE"),
    (30, "PALO ALTO +10% ON EARNINGS"),
    (31, "SCOTLAND: 7 PLAYERS OUT BEFORE JAPAN"),
    (32, "CYCLONE AKVAN: LANDFALL FRIDAY"),
]

FIGURES = [
    ("$83", "ANTHROPIC IPO PRICE"),
    ("1,441", "DRONES IN ONE NIGHT"),
    ("315 KM/H", "CYCLONE XAVIER GUSTS"),
    ("56-44", "DEMOCRAT SENATE MAJORITY"),
]

TOMORROW = ("TOMORROW - THU 19 NOV: ",
             "TRUMP-XI-PUTIN SUMMIT IN SHENZHEN  |  ICJ RULES ON MYANMAR  |  "
             "ANTHROPIC SHARES TRADE AS ANT")

SOURCE_LINE = ("Sources: Reuters, AP, BBC, AFP, Al Jazeera, ATP, Anthropic, "
               "NZ MetService, IMD. All stories from Wednesday 18 November 2026.")


# --- page build --------------------------------------------------------------
def build():
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    # double outer border
    d.rectangle([4, 4, W - 5, H - 5], outline=NAVY, width=3)
    d.rectangle([9, 9, W - 10, H - 10], outline=RED, width=1)
    x0, x1 = 16, W - 16
    cw = x1 - x0  # 992

    # --- masthead: cream broadsheet, giant navy date, red rules -------------
    y = 16
    hline(d, x0, x1, y, RED, 3)
    y += 8
    draw_bold_c(d, (x0 + x1) // 2, y, "THE WORLD IN ONE DAY", 20, NAVY, 1)
    y += 27
    date = "WEDNESDAY 18 NOVEMBER 2026"
    ds = fit_size(date, 60, cw)
    draw_bold_c(d, (x0 + x1) // 2, y, date, ds, NAVY, 2)
    y += ds + 8
    hline(d, x0, x1, y, NAVY, 2)
    y += 7
    draw_bold(d, (x0, y), "32 STORIES - 6 CONTINENTS", 16, RED, 1)
    rs = "ALL FROM WEDNESDAY"
    draw_bold(d, (x1 - text_w(rs, 16), y), rs, 16, NAVY, 1)
    y += 22
    hline(d, x0, x1, y, RED, 3)
    y += 8

    # --- figures band: navy, directly under the masthead ---------------------
    band_y = y
    band_h = 46
    d.rectangle([x0, band_y, x1, band_y + band_h], fill=NAVY)
    cell_w = cw // 4
    for i, (val, lab) in enumerate(FIGURES):
        cx = x0 + cell_w * i + cell_w // 2
        if i:
            d.line([x0 + cell_w * i, band_y + 8, x0 + cell_w * i,
                    band_y + band_h - 8], fill=(120, 140, 180), width=1)
        draw_bold_c(d, cx, band_y + 5, val, 23, (255, 255, 255), 1)
        d.text((cx - text_w(lab, 12) / 2, band_y + 31), lab, font=font(12),
               fill=(200, 210, 230))
    y = band_y + band_h + 10

    # --- three equal leads ---------------------------------------------------
    lead_y = y
    col_w = (cw - 2 * 14) // 3
    scene_h = 120
    lead_bottom = lead_y
    for i, (num, cat, head, sub) in enumerate(LEADS):
        cx = x0 + i * (col_w + 14)
        d.rectangle([cx, lead_y, cx + col_w, lead_y + scene_h], outline=NAVY, width=2)
        SCENES[num](d, cx + 2, lead_y + 2, col_w - 4, scene_h - 4)
        badge(d, cx + 18, lead_y + 18, 13, num)
        ty = lead_y + scene_h + 6
        lab, col = CAT[cat]
        draw_bold(d, (cx, ty), lab, 12, col, 1)
        ty += 17
        ty = para(d, cx, ty, head, 22, INK, col_w, weight=1, leading=25)
        ty = para(d, cx, ty + 3, sub, 14, GREY, col_w, leading=17)
        lead_bottom = max(lead_bottom, ty)
    y = lead_bottom + 8
    hline(d, x0, x1, y, HAIR, 1)
    y += 8

    # --- grid: 4 x 2 illustrated (rows sized from measured content) --------
    grid_y = y
    gcol = (cw - 3 * 10) // 4
    grow_y = grid_y
    for r in range(2):
        row_bottom = grow_y
        for c in range(4):
            idx = r * 4 + c
            num, cat, head, sub = GRID[idx]
            gx = x0 + c * (gcol + 10)
            gy = grow_y
            sh = 60
            d.rectangle([gx, gy, gx + gcol, gy + sh], outline=NAVY, width=1)
            SCENES[num](d, gx + 1, gy + 1, gcol - 2, sh - 2)
            badge(d, gx + 13, gy + 13, 10, num)
            ty = gy + sh + 4
            lab, col = CAT[cat]
            draw_bold(d, (gx, ty), lab, 11, col, 1)
            ty += 15
            ty = para(d, gx, ty, head, 16, INK, gcol, weight=1, leading=18)
            fs = fit_size(sub, 12, gcol)
            d.text((gx, ty + 1), sub, font=font(fs), fill=GREY)
            row_bottom = max(row_bottom, ty + 15)
        grow_y = row_bottom + 8
    y = grow_y + 2
    hline(d, x0, x1, y, HAIR, 1)
    y += 8

    # --- bottom: map left, ALSO list right -----------------------------------
    bot_y = y
    map_w = 400
    also_x = x0 + map_w + 14
    also_w = x1 - also_x
    draw_bold(d, (x0, bot_y), "WHERE IT HAPPENED", 16, NAVY, 1)
    draw_bold(d, (also_x, bot_y), "ALSO ON WEDNESDAY", 16, NAVY, 1)
    my = bot_y + 24
    map_h = 150
    draw_map(d, x0, my, map_w, map_h)
    # legend, one line, abbreviations to fit
    leg = [("WAR", RED), ("DIPLOMACY", NAVY2), ("POLITICS", GREEN),
           ("ECONOMY", TEAL), ("WEATHER + SPORT", AMBER)]
    lx = x0
    ly = my + map_h + 7
    for lab, col in leg:
        d.ellipse([lx, ly + 2, lx + 9, ly + 11], fill=col)
        lx += 13
        d.text((lx, ly), lab, font=font(11), fill=INK)
        lx += text_w(lab, 11) + 12
    # ALSO list: two columns, shrink-to-fit per line
    col2_w = (also_w - 12) // 2
    rows = (len(ALSO) + 1) // 2
    ay = my
    for i, (num, txt) in enumerate(ALSO):
        c = 0 if i < rows else 1
        r = i if i < rows else i - rows
        ax = also_x + c * (col2_w + 12)
        ry = ay + r * 15
        draw_bold(d, (ax, ry), str(num), 12, RED, 1)
        fs = fit_size(txt, 12, col2_w - 26)
        d.text((ax + 24, ry), txt, font=font(fs), fill=INK)
    y = my + map_h + 7 + 15 + 4

    # --- tomorrow strip + source line ----------------------------------------
    hline(d, x0, x1, y, RED, 2)
    y += 6
    pre, items = TOMORROW
    draw_bold(d, (x0, y), pre, 13, RED, 1)
    tx = x0 + text_w(pre, 13)
    fs = fit_size(items, 13, x1 - tx)
    d.text((tx, y), items, font=font(fs), fill=NAVY)
    y += 18
    hline(d, x0, x1, y, NAVY, 1)
    y += 5
    fs = fit_size(SOURCE_LINE, 12, cw)
    d.text(((x0 + x1) // 2 - text_w(SOURCE_LINE, fs) / 2, y), SOURCE_LINE,
           font=font(fs), fill=GREY)
    assert y + 16 <= H - 10, "layout overflow: %d" % y
    return img


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "out")
    os.makedirs(out_dir, exist_ok=True)
    img = build()
    path = os.path.join(out_dir, "entry.png")
    img.save(path, format="PNG", optimize=True)
    print("wrote", path, img.size)


if __name__ == "__main__":
    main()
