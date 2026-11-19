#!/usr/bin/env python3
"""news-image-20261118, round 2: the Wednesday 18 November 2026 front page,
redrawn with the Python standard library only.

Round 1 was rejected by the grader: its Pillow import does not exist in
the pinned python:3.13 grading image. This port keeps every story, scene,
colour and layout line of round 1 and swaps the drawing layer underneath:
an in-memory RGB canvas, a hand-built stroke alphabet, and a small PNG
writer (struct + zlib). No third-party code, no network, no file reads,
no clock, no randomness: two runs write identical bytes.

Layout, top to bottom: cream masthead with the giant navy date, a navy
DAY IN FIGURES band, three equal illustrated leads, a 4x2 illustrated
grid, a world map with leader-line badges beside the ALSO ON WEDNESDAY
list, a TOMORROW strip, and the source line. 32 stories, 11 illustrated.
All words come from NEWS-20261118.md.
"""

import math
import os
import struct
import zlib

W, H = 1024, 1024

# --- palette: (red, green, blue) as hex triples, values kept exact -------
CREAM = (0xF7, 0xF1, 0xDE)    # paper
PAPER2 = (0xEE, 0xE6, 0xCB)   # darker paper for panels
INK = (0x16, 0x18, 0x1E)      # near-black text
NAVY = (0x12, 0x26, 0x4C)     # masthead date, figures band
NAVY2 = (0x1C, 0x3A, 0x6C)    # lighter navy
RED = (0xB2, 0x22, 0x22)      # accents, numbers, conflict
RED2 = (0xCD, 0x3C, 0x32)
GOLD = (0xB8, 0x86, 0x0B)
GREEN = (0x22, 0x6E, 0x48)
TEAL = (0x0E, 0x6E, 0x6E)
AMBER = (0xB0, 0x6E, 0x0A)
PURPLE = (0x60, 0x3C, 0x82)
GREY = (0x4A, 0x4A, 0x46)     # sub-text
HAIR = (0x96, 0x8C, 0x73)     # hairlines
SEA = (0xA8, 0xC4, 0xD6)      # map sea
LAND = (0xE8, 0xDE, 0xBE)     # map land
LAND2 = (0xDE, 0xD2, 0xAC)
WHITE = (0xFF, 0xFF, 0xFF)

# category code -> (printed label, colour)
CATS = [("WAR", "WAR", RED), ("DIP", "DIPLOMACY", NAVY2),
        ("POL", "POLITICS", GREEN), ("ECO", "ECONOMY", TEAL),
        ("WEA", "WEATHER", AMBER), ("SPO", "SPORT", PURPLE)]
CAT = {code: (label, col) for code, label, col in CATS}


class Canvas:
    """An RGB pixel buffer with the few primitives the front page needs.

    Coordinates are pixel positions; rectangles given as (x0, y0, x1, y1)
    include both ends, matching the old Pillow calls, while fill() takes
    half-open bounds. Anything drawn outside the page is clipped.
    """

    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.buf = bytearray(w * h * 3)
        self.fill(0, 0, w, h, bg)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i] = c[0]
            self.buf[i + 1] = c[1]
            self.buf[i + 2] = c[2]

    def fill(self, x0, y0, x1, y1, c):
        """Paint the half-open rectangle [x0, x1) by [y0, y1)."""
        x0 = max(0, int(round(x0)))
        y0 = max(0, int(round(y0)))
        x1 = min(self.w, int(round(x1)))
        y1 = min(self.h, int(round(y1)))
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for y in range(y0, y1):
            s = (y * self.w + x0) * 3
            self.buf[s:s + len(row)] = row

    def rect(self, x0, y0, x1, y1, fill=None, edge=None, t=1):
        """Inclusive rectangle: optional fill plus an outline of width t."""
        x0, y0, x1, y1 = (int(round(v)) for v in (x0, y0, x1, y1))
        if fill is not None:
            self.fill(x0, y0, x1 + 1, y1 + 1, fill)
        if edge is not None:
            self.fill(x0, y0, x1 + 1, y0 + t, edge)
            self.fill(x0, y1 - t + 1, x1 + 1, y1 + 1, edge)
            self.fill(x0, y0, x0 + t, y1 + 1, edge)
            self.fill(x1 - t + 1, y0, x1 + 1, y1 + 1, edge)

    def line(self, x0, y0, x1, y1, c, t=1):
        """A straight segment with a square brush of side t."""
        x0, y0, x1, y1 = (int(round(v)) for v in (x0, y0, x1, y1))
        if y0 == y1:
            r = t // 2
            lo, hi = (x0, x1) if x0 <= x1 else (x1, x0)
            self.fill(lo, y0 - r, hi + 1, y0 - r + t, c)
            return
        if x0 == x1:
            r = t // 2
            lo, hi = (y0, y1) if y0 <= y1 else (y1, y0)
            self.fill(x0 - r, lo, x0 - r + t, hi + 1, c)
            return
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        r = t // 2
        while True:
            for a in range(-r, r + 1):
                for b in range(-r, r + 1):
                    self.set(x0 + a, y0 + b, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def lines(self, pts, c, t=1):
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            self.line(ax, ay, bx, by, c, t)

    def disc(self, cx, cy, r, c):
        cx, cy, r = int(round(cx)), int(round(cy)), int(round(r))
        for y in range(cy - r, cy + r + 1):
            dy = y - cy
            span = int(math.sqrt(max(0, r * r - dy * dy)))
            self.fill(cx - span, y, cx + span + 1, y + 1, c)

    def ring(self, cx, cy, r, c, t=1):
        """Circle outline: paints the band r-t .. r+t."""
        cx, cy, r = int(round(cx)), int(round(cy)), int(round(r))
        for y in range(cy - r - t, cy + r + t + 1):
            for x in range(cx - r - t, cx + r + t + 1):
                d2 = (x - cx) ** 2 + (y - cy) ** 2
                if (r - t) ** 2 <= d2 <= (r + t) ** 2:
                    self.set(x, y, c)

    def ellipse(self, cx, cy, rx, ry, c):
        cx, cy = int(round(cx)), int(round(cy))
        rx, ry = int(round(rx)), int(round(ry))
        if rx <= 0 or ry <= 0:
            return
        for y in range(cy - ry, cy + ry + 1):
            dy = (y - cy) / ry
            span = int(rx * math.sqrt(max(0.0, 1.0 - dy * dy)))
            self.fill(cx - span, y, cx + span + 1, y + 1, c)

    def ellipse_ring(self, cx, cy, rx, ry, c, t=2):
        pts = []
        for k in range(72):
            a = 2.0 * math.pi * k / 72
            pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
        pts.append(pts[0])
        self.lines(pts, c, t)

    def ellbox(self, x0, y0, x1, y1, fill=None, edge=None, t=2):
        """Inclusive bounding-box ellipse: optional fill and outline."""
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
        if fill is not None:
            self.ellipse(cx, cy, rx, ry, fill)
        if edge is not None:
            self.ellipse_ring(cx, cy, rx, ry, edge, t)

    def arc(self, cx, cy, rx, ry, a0, a1, c, t=2):
        """Arc in degrees; 0 is 3 o'clock, angles grow clockwise (y down)."""
        steps = max(2, int(abs(a1 - a0) / 6))
        pts = []
        for k in range(steps + 1):
            a = math.radians(a0 + (a1 - a0) * k / steps)
            pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
        self.lines(pts, c, t)

    def box_arc(self, x0, y0, x1, y1, a0, a1, c, t=2):
        self.arc((x0 + x1) / 2, (y0 + y1) / 2,
                 (x1 - x0) / 2, (y1 - y0) / 2, a0, a1, c, t)

    def half_disc(self, cx, cy, rx, ry, c):
        """Upper half of an ellipse: the dome of a pieslice from 180 to 360."""
        cx, cy = int(round(cx)), int(round(cy))
        rx, ry = int(round(rx)), int(round(ry))
        if rx <= 0 or ry <= 0:
            return
        for y in range(cy - ry, cy):
            dy = (y - cy) / ry
            span = int(rx * math.sqrt(max(0.0, 1.0 - dy * dy)))
            self.fill(cx - span, y, cx + span + 1, y + 1, c)

    def poly(self, pts, c):
        """Scanline fill of a simple polygon (even-odd rule)."""
        pts = [(int(round(x)), int(round(y))) for x, y in pts]
        ys = [p[1] for p in pts]
        top, bot = max(0, min(ys)), min(self.h - 1, max(ys))
        n = len(pts)
        for y in range(top, bot + 1):
            xs = []
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self.fill(int(xs[k]), y, int(xs[k + 1]) + 1, y + 1, c)

    def sky3(self, x, y, w, h, top, mid, bot):
        """Three flat sky bands, like the old gradient helper."""
        third = max(1, int(h) // 3)
        self.fill(x, y, x + w, y + third, top)
        self.fill(x, y + third, x + w, y + 2 * third, mid)
        self.fill(x, y + 2 * third, x + w, y + h, bot)


# ------------------------------------------------------------------ alphabet
# Stroke capitals and small letters on a 9-wide by 13-tall grid (x 0..8,
# y 0..12, baseline at 12). Small letters sit on an x-height of 5..12,
# ascenders reach 0, descenders curl inside the cell. Every glyph is a
# list of polylines; the pen draws thick segments along them.
GLYPH = {
    "A": [[(0, 12), (4, 0), (8, 12)], [(2, 8), (6, 8)]],
    "B": [[(0, 0), (0, 12)], [(0, 0), (5, 0), (7, 2), (5, 4), (0, 4)],
          [(0, 4), (5, 4), (8, 7), (8, 10), (5, 12), (0, 12)]],
    "C": [[(8, 2), (6, 0), (2, 0), (0, 2), (0, 10), (2, 12), (6, 12), (8, 10)]],
    "D": [[(0, 0), (0, 12)], [(0, 0), (5, 0), (8, 3), (8, 9), (5, 12), (0, 12)]],
    "E": [[(0, 0), (0, 12)], [(0, 0), (8, 0)], [(0, 6), (6, 6)], [(0, 12), (8, 12)]],
    "F": [[(0, 0), (0, 12)], [(0, 0), (8, 0)], [(0, 6), (6, 6)]],
    "G": [[(8, 2), (6, 0), (2, 0), (0, 2), (0, 10), (2, 12), (6, 12),
           (8, 10), (8, 6), (4, 6)]],
    "H": [[(0, 0), (0, 12)], [(8, 0), (8, 12)], [(0, 6), (8, 6)]],
    "I": [[(4, 0), (4, 12)], [(1, 0), (7, 0)], [(1, 12), (7, 12)]],
    "J": [[(8, 0), (8, 10), (6, 12), (2, 12), (0, 10)]],
    "K": [[(0, 0), (0, 12)], [(8, 0), (1, 6)], [(2, 6), (8, 12)]],
    "L": [[(0, 0), (0, 12)], [(0, 12), (8, 12)]],
    "M": [[(0, 12), (0, 0), (4, 6), (8, 0), (8, 12)]],
    "N": [[(0, 12), (0, 0), (8, 12), (8, 0)]],
    "O": [[(2, 0), (6, 0), (8, 2), (8, 10), (6, 12), (2, 12), (0, 10),
           (0, 2), (2, 0)]],
    "P": [[(0, 12), (0, 0)], [(0, 0), (6, 0), (8, 2), (8, 5), (6, 7), (0, 7)]],
    "Q": [[(2, 0), (6, 0), (8, 2), (8, 10), (6, 12), (2, 12), (0, 10),
           (0, 2), (2, 0)], [(5, 9), (8, 12)]],
    "R": [[(0, 12), (0, 0)], [(0, 0), (6, 0), (8, 2), (8, 5), (6, 7), (0, 7)],
          [(4, 7), (8, 12)]],
    "S": [[(8, 2), (6, 0), (2, 0), (0, 2), (0, 5), (2, 7), (6, 7), (8, 9),
           (8, 11), (6, 12), (2, 12), (0, 10)]],
    "T": [[(0, 0), (8, 0)], [(4, 0), (4, 12)]],
    "U": [[(0, 0), (0, 10), (2, 12), (6, 12), (8, 10), (8, 0)]],
    "V": [[(0, 0), (4, 12), (8, 0)]],
    "W": [[(0, 0), (2, 12), (4, 6), (6, 12), (8, 0)]],
    "X": [[(0, 0), (8, 12)], [(8, 0), (0, 12)]],
    "Y": [[(0, 0), (4, 6), (8, 0)], [(4, 6), (4, 12)]],
    "Z": [[(0, 0), (8, 0), (0, 12), (8, 12)]],
    "a": [[(2, 6), (6, 6), (8, 8), (8, 10), (6, 12), (2, 12), (0, 10),
           (0, 8), (2, 6)], [(8, 5), (8, 12)]],
    "b": [[(0, 0), (0, 12)], [(0, 6), (5, 6), (8, 8), (8, 11), (6, 12),
           (2, 12), (0, 10)]],
    "c": [[(8, 7), (6, 5), (2, 5), (0, 7), (0, 10), (2, 12), (6, 12), (8, 10)]],
    "d": [[(8, 0), (8, 12)], [(0, 7), (2, 5), (6, 5), (8, 7), (8, 10),
           (6, 12), (2, 12), (0, 10)]],
    "e": [[(8, 8), (6, 5), (2, 5), (0, 7), (0, 10), (2, 12), (6, 12), (8, 10)],
          [(0, 8), (7, 8)]],
    "f": [[(6, 0), (3, 0), (2, 2), (2, 12)], [(2, 5), (6, 5)]],
    "g": [[(2, 5), (6, 5), (8, 7), (8, 10), (6, 12), (2, 12), (0, 10),
           (0, 7), (2, 5)], [(8, 9), (8, 12), (4, 12)]],
    "h": [[(0, 0), (0, 12)], [(0, 6), (4, 5), (7, 6), (8, 8), (8, 12)]],
    "i": [[(4, 0), (4, 1)], [(4, 5), (4, 12)]],
    "j": [[(5, 0), (5, 1)], [(5, 5), (5, 11), (3, 12), (1, 11)]],
    "k": [[(0, 0), (0, 12)], [(7, 5), (1, 9)], [(2, 8), (7, 12)]],
    "l": [[(4, 0), (4, 12)]],
    "m": [[(0, 12), (0, 5), (2, 5), (4, 7), (6, 5), (8, 5), (8, 12)],
          [(4, 7), (4, 12)]],
    "n": [[(0, 12), (0, 5), (3, 5), (6, 6), (8, 8), (8, 12)]],
    "o": [[(2, 5), (6, 5), (8, 7), (8, 10), (6, 12), (2, 12), (0, 10),
           (0, 7), (2, 5)]],
    "p": [[(0, 5), (0, 12)], [(0, 6), (5, 5), (8, 7), (8, 10), (6, 12),
           (2, 12), (0, 10)]],
    "q": [[(8, 5), (8, 12)], [(0, 7), (2, 5), (6, 5), (8, 7), (8, 10),
           (6, 12), (2, 12), (0, 10)]],
    "r": [[(0, 5), (0, 12)], [(0, 6), (4, 5), (7, 6), (8, 8)]],
    "s": [[(7, 6), (5, 5), (2, 5), (0, 7), (0, 8), (2, 9), (6, 9), (8, 10),
           (8, 11), (6, 12), (3, 12), (1, 11)]],
    "t": [[(4, 0), (4, 12)], [(2, 5), (7, 5)], [(4, 0), (6, 1)]],
    "u": [[(0, 5), (0, 10), (2, 12), (6, 12), (8, 10), (8, 5)]],
    "v": [[(0, 5), (4, 12), (8, 5)]],
    "w": [[(0, 5), (2, 12), (4, 8), (6, 12), (8, 5)]],
    "x": [[(0, 5), (8, 12)], [(8, 5), (0, 12)]],
    "y": [[(0, 5), (4, 11), (8, 5)], [(4, 11), (3, 12)]],
    "z": [[(0, 5), (8, 5), (0, 12), (8, 12)]],
    "0": [[(2, 0), (6, 0), (8, 2), (8, 10), (6, 12), (2, 12), (0, 10),
           (0, 2), (2, 0)], [(6, 2), (2, 10)]],
    "1": [[(2, 2), (4, 0), (4, 12)], [(1, 12), (7, 12)]],
    "2": [[(0, 2), (2, 0), (6, 0), (8, 2), (8, 5), (0, 12), (8, 12)]],
    "3": [[(1, 1), (3, 0), (6, 0), (8, 2), (8, 5), (5, 6)],
          [(5, 6), (8, 7), (8, 10), (6, 12), (3, 12), (1, 11)]],
    "4": [[(5, 0), (5, 12)], [(0, 8), (8, 8)], [(5, 0), (0, 8)]],
    "5": [[(8, 0), (0, 0), (0, 6), (5, 6), (8, 8), (8, 11), (6, 12),
           (2, 12), (0, 10)]],
    "6": [[(7, 2), (5, 0), (2, 0), (0, 3), (0, 10), (2, 12), (6, 12),
           (8, 10), (8, 7), (6, 5), (2, 5)]],
    "7": [[(0, 0), (8, 0), (4, 12)]],
    "8": [[(2, 0), (6, 0), (8, 2), (8, 5), (6, 7), (2, 7), (0, 5), (0, 2), (2, 0)],
          [(2, 7), (6, 7), (8, 9), (8, 11), (6, 12), (2, 12), (0, 10),
           (0, 8), (2, 7)]],
    "9": [[(2, 0), (6, 0), (8, 2), (8, 9), (6, 12), (2, 12), (0, 10)],
          [(0, 3), (0, 6), (2, 7), (6, 7), (8, 5)]],
    " ": [],
    ".": [[(4, 11), (4, 12)]],
    ",": [[(4, 10), (3, 12)]],
    "-": [[(1, 6), (7, 6)]],
    ":": [[(4, 3), (4, 4)], [(4, 8), (4, 9)]],
    ";": [[(4, 3), (4, 4)], [(4, 8), (3, 12)]],
    "'": [[(4, 0), (4, 3)]],
    "!": [[(4, 0), (4, 8)], [(4, 11), (4, 12)]],
    "?": [[(1, 3), (2, 0), (6, 0), (8, 2), (8, 4), (6, 6), (4, 6)],
          [(4, 9), (4, 10)]],
    "/": [[(7, 0), (1, 12)]],
    "(": [[(6, 0), (3, 2), (3, 10), (6, 12)]],
    ")": [[(2, 0), (5, 2), (5, 10), (2, 12)]],
    "&": [[(6, 0), (2, 0), (0, 2), (0, 5), (3, 7), (8, 12)],
          [(8, 1), (4, 5), (0, 9), (2, 12), (6, 12), (8, 10)]],
    "%": [[(1, 1), (2, 1)], [(6, 11), (7, 11)], [(7, 0), (1, 12)]],
    "$": [[(4, 0), (4, 12)],
          [(7, 3), (5, 1), (2, 1), (1, 3), (1, 5), (3, 7), (7, 7), (8, 9),
           (8, 11), (6, 12), (3, 12), (1, 10)]],
    "+": [[(4, 2), (4, 10)], [(0, 6), (8, 6)]],
    "=": [[(0, 4), (8, 4)], [(0, 8), (8, 8)]],
    "|": [[(4, 0), (4, 12)]],
}

ADV = 10.0  # default glyph advance, in font units

# Proportional-ish advances: narrow strokes and the space take less room,
# wide letters a little more, so wrapped body text lands where the old
# proportional font put it instead of spilling onto an extra line.
NARROW = {"i": 6.5, "l": 6.5, "j": 6.5, "t": 8.0, "f": 7.0, ".": 6.0,
          ",": 6.0, ":": 6.0, ";": 6.0, "'": 6.0, "!": 6.0, "|": 6.0,
          "(": 7.0, ")": 7.0, "-": 8.0, "/": 8.0, " ": 5.0}
WIDE = {"m": 11.0, "w": 11.0, "M": 11.0, "W": 11.0}


def adv(ch):
    return NARROW.get(ch, WIDE.get(ch, ADV))


def twidth(s, pt):
    """Pixel width of s at point size pt (scale = pt / 18)."""
    if not s:
        return 0.0
    return (sum(adv(ch) for ch in s) - 1) * (pt / 18.0)


def wrap(s, pt, maxw):
    """Greedy word wrap to maxw pixels; returns a list of lines."""
    words = s.split(" ")
    lines, cur = [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if twidth(trial, pt) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def fit_pt(s, pt, maxw, minimum=9):
    """Largest point size <= pt at which s fits inside maxw."""
    while pt > minimum and twidth(s, pt) > maxw:
        pt -= 1
    return pt


# -- text drawing lives on the canvas so it can use the pen directly -----
def _canvas_glyph(self, x, y, ch, sc, c):
    thick = max(1, int(round(sc * 0.9)))
    for stroke in GLYPH.get(ch, GLYPH[" "]):
        pts = [(x + ax * sc, y + ay * sc) for ax, ay in stroke]
        self.lines(pts, c, thick)


def _canvas_text(self, x, y, s, pt, c, bold=0):
    """Draw s with its top at y; bold overprints on a small offset grid."""
    sc = pt / 18.0
    for dx in range(bold + 1):
        for dy in range(bold + 1):
            cx = x + dx
            for ch in s:
                self.glyph(cx, y + dy, ch, sc, c)
                cx += adv(ch) * sc


def _canvas_ctext(self, cx, y, s, pt, c, bold=0):
    self.text(cx - twidth(s, pt) / 2, y, s, pt, c, bold)


def _canvas_para(self, x, y, s, pt, c, maxw, bold=0, leading=None):
    """Draw a wrapped paragraph; returns y just below the last line."""
    lh = leading if leading is not None else int(pt * 1.22)
    for ln in wrap(s, pt, maxw):
        self.text(x, y, ln, pt, c, bold)
        y += lh
    return y


Canvas.glyph = _canvas_glyph
Canvas.text = _canvas_text
Canvas.ctext = _canvas_ctext
Canvas.para = _canvas_para


# ------------------------------------------------------------------ helpers
def hline(cv, x0, x1, y, c, wdt=1):
    cv.fill(x0, y, x1 + 1, y + wdt, c)


def badge(cv, cx, cy, r, num, fill=RED, fg=WHITE):
    """Numbered circle badge, number centred."""
    cv.disc(cx, cy, r, fill)
    cv.ellipse_ring(cx, cy, r, r, WHITE, 2)
    s = str(num)
    fs = fit_pt(s, r + 4, r * 2 - 4)
    sc = fs / 18.0
    cv.text(cx - twidth(s, fs) / 2, cy - 13 * sc / 2, s, fs, fg, bold=1)


def sun(cv, cx, cy, r, fill=(250, 210, 90)):
    cv.disc(cx, cy, r, fill)
    cv.ellipse_ring(cx, cy, r + 5, r + 5, fill, 2)


def cloud(cv, x, y, s, fill=WHITE):
    cv.ellipse(x + 1.5 * s, y + 0.5 * s, 1.5 * s, 0.5 * s, fill)
    cv.ellipse(x + 1.75 * s, y, 1.25 * s, 0.5 * s, fill)
    cv.ellipse(x + 2.5 * s, y + s / 3, 1.5 * s, 2 * s / 3, fill)


def sea(cv, x, y, w, h, fill=(38, 84, 124)):
    cv.fill(x, y, x + w, y + h, fill)
    for i, wy in enumerate(range(int(y) + 6, int(y) + int(h) - 4, 12)):
        off = (i % 2) * 8
        for wx in range(int(x) + 4 + off, int(x) + int(w) - 14, 26):
            cv.line(wx, wy, wx + 12, wy, (210, 225, 235), 2)


def burst(cv, cx, cy, r, fill=(255, 170, 40)):
    """Starburst: 8 spikes, bright core."""
    pts = []
    for i in range(16):
        ang = math.pi * i / 8
        rr = r if i % 2 == 0 else r * 0.38
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    cv.poly(pts, fill)
    cv.disc(cx, cy, r * 0.3, (255, 240, 180))


def building(cv, x, ybase, w, h, fill, lit=(250, 210, 110)):
    """One skyline tower with lit windows."""
    cv.fill(x, ybase - h, x + w, ybase, fill)
    for wy in range(int(ybase) - int(h) + 6, int(ybase) - 6, 12):
        for wx in range(int(x) + 4, int(x) + int(w) - 5, 10):
            if (wx * 7 + wy * 3) % 5 < 2:
                cv.fill(wx, wy, wx + 5, wy + 6, lit)


# ------------------------------------------- illustrated scenes, 1 to 5 ----
# Each draws inside box (x, y, w, h) and is recognisable without its caption.

def scene_gulf(cv, x, y, w, h):
    """1. Gulf: night sky, drones with red trails, interceptor bursts, sea."""
    cv.sky3(x, y, w, h, (12, 22, 48), (24, 40, 76), (52, 72, 110))
    sun(cv, x + w - 26, y + 22, 11, fill=(235, 220, 180))
    cloud(cv, x + 12, y + 14, 7, fill=(70, 88, 120))
    cloud(cv, x + w // 2 - 10, y + 30, 6, fill=(60, 78, 110))
    sea(cv, x, y + h - 26, w, 26, fill=(20, 48, 84))
    cv.poly([(x, y + h - 26), (x + w * 0.3, y + h - 44), (x + w * 0.55, y + h - 34),
             (x + w * 0.8, y + h - 46), (x + w, y + h - 38), (x + w, y + h - 26)],
            (16, 26, 44))
    for dx, dy, ln in ((0.22, 0.30, 34), (0.52, 0.20, 28), (0.74, 0.38, 40)):
        cx, cy = x + int(w * dx), y + int(h * dy)
        cv.line(cx - ln, cy + 8, cx, cy, (230, 60, 50), 3)
        cv.ellbox(cx - 7, cy - 4, cx + 7, cy + 4, fill=(30, 30, 34))
        cv.ellbox(cx + 8, cy - 2, cx + 14, cy + 2, fill=(230, 60, 50))
        cv.ellbox(cx - 2, cy - 7, cx + 2, cy - 2, fill=(120, 120, 130))
    burst(cv, x + int(w * 0.38), y + int(h * 0.52), 13)
    burst(cv, x + int(w * 0.86), y + int(h * 0.30), 10, fill=(255, 200, 90))


def scene_shenzhen(cv, x, y, w, h):
    """2. Shenzhen: dusk sky, layered towers, three flags, red carpet."""
    cv.sky3(x, y, w, h, (58, 44, 92), (150, 78, 84), (232, 148, 88))
    sun(cv, x + w // 2, y + h - 52, 16)
    for bx, bw, bh in ((0.04, 0.10, 0.52), (0.20, 0.08, 0.66), (0.62, 0.09, 0.58),
                       (0.80, 0.11, 0.46)):
        building(cv, x + int(w * bx), y + h - 30, int(w * bw), int(h * bh),
                 fill=(52, 44, 78), lit=(220, 170, 110))
    for bx, bw, bh in ((0.12, 0.12, 0.42), (0.38, 0.10, 0.50), (0.70, 0.12, 0.40)):
        building(cv, x + int(w * bx), y + h - 30, int(w * bw), int(h * bh),
                 fill=(30, 26, 52), lit=(250, 210, 110))
    cv.fill(x, y + h - 30, x + w, y + h, (120, 30, 34))
    cv.fill(x, y + h - 30, x + w, y + h - 26, (200, 170, 90))
    for i, cols in enumerate((((200, 40, 40),), ((200, 40, 40), (255, 255, 255), (40, 60, 160)),
                              ((255, 255, 255), (40, 80, 200), (200, 40, 40)))):
        fx = x + int(w * (0.30 + 0.20 * i))
        fy = y + h - 66
        cv.fill(fx, fy, fx + 2, y + h - 30, (240, 240, 230))
        fh = 22
        n = len(cols)
        for j, c in enumerate(cols):
            cv.fill(fx + 2, fy + j * fh // n, fx + 26, fy + (j + 1) * fh // n, c)
        cv.rect(fx + 2, fy, fx + 26, fy + fh, edge=(90, 80, 60), t=1)


def scene_peltola(cv, x, y, w, h):
    """3. Alaska: blue sky, mountains, ballot box with a big check."""
    cv.sky3(x, y, w, h, (64, 120, 178), (120, 168, 208), (190, 214, 228))
    sun(cv, x + 30, y + 24, 13)
    cloud(cv, x + w - 78, y + 12, 8)
    cv.poly([(x, y + h - 34), (x + w * 0.22, y + h * 0.34), (x + w * 0.44, y + h - 34)],
            (52, 84, 128))
    cv.poly([(x + w * 0.16, y + h - 34), (x + w * 0.30, y + h * 0.52),
             (x + w * 0.44, y + h - 34)], (235, 242, 248))
    cv.poly([(x + w * 0.42, y + h - 34), (x + w * 0.66, y + h * 0.26),
             (x + w * 0.92, y + h - 34)], (44, 72, 112))
    cv.poly([(x + w * 0.58, y + h - 34), (x + w * 0.66, y + h * 0.42),
             (x + w * 0.74, y + h - 34)], (235, 242, 248))
    cv.fill(x, y + h - 34, x + w, y + h, (34, 96, 66))
    bx, by, bw, bh = x + w - 92, y + h - 76, 74, 46
    cv.rect(bx, by, bx + bw, by + bh, fill=(240, 236, 222), edge=(30, 30, 40), t=3)
    cv.fill(bx + 8, by - 8, bx + bw - 8, by + 2, (30, 30, 40))
    cv.line(bx + 14, by + 26, bx + 30, by + 38, (178, 34, 34), 6)
    cv.line(bx + 30, by + 38, bx + 62, by + 8, (178, 34, 34), 6)
    for sx, sy in ((0.12, 0.22), (0.30, 0.14), (0.46, 0.30)):
        burst(cv, x + int(w * sx), y + int(h * sy), 6, fill=(250, 210, 110))


def scene_kerch(cv, x, y, w, h):
    """4. Kerch: night, bridge deck, collapsed middle span, smoke, drones.
    All offsets are fractions of the scene box, so nothing bleeds above
    the frame (the grid scenes are short)."""
    cv.sky3(x, y, w, h, (10, 16, 38), (22, 34, 66), (48, 62, 100))
    sun(cv, x + 26, y + 16, 9, fill=(225, 215, 180))
    sea(cv, x, y + h - 14, w, 14, fill=(18, 42, 74))
    deck_y = y + h - 26
    cv.fill(x, deck_y, x + int(w * 0.36), deck_y + 6, (120, 118, 112))
    cv.fill(x + int(w * 0.64), deck_y, x + w, deck_y + 6, (120, 118, 112))
    for px in (0.08, 0.24, 0.76, 0.92):
        cv.fill(x + int(w * px) - 3, deck_y + 6, x + int(w * px) + 3, y + h - 14,
                (90, 88, 82))
    cv.poly([(x + int(w * 0.36), deck_y), (x + int(w * 0.50), deck_y + 14),
             (x + int(w * 0.54), deck_y + 10), (x + int(w * 0.40), deck_y - 2)],
            (150, 146, 138))
    cv.poly([(x + int(w * 0.64), deck_y), (x + int(w * 0.52), deck_y + 12),
             (x + int(w * 0.48), deck_y + 8), (x + int(w * 0.60), deck_y - 2)],
            (130, 126, 118))
    burst(cv, x + int(w * 0.50), deck_y + 2, 11)
    for sx, sy, sr in ((0.44, 0.28, 9), (0.52, 0.24, 10), (0.58, 0.30, 8)):
        cv.ellbox(x + int(w * sx) - sr, y + int(h * sy) - sr,
                  x + int(w * sx) + sr, y + int(h * sy) + sr, fill=(120, 122, 126))
    for dx, dy in ((0.18, 0.16), (0.82, 0.12)):
        cx, cy = x + int(w * dx), y + int(h * dy)
        cv.ellbox(cx - 7, cy - 3, cx + 7, cy + 3, fill=(20, 20, 24))
        cv.ellbox(cx + 8, cy - 2, cx + 13, cy + 2, fill=(230, 60, 50))


def scene_xavier(cv, x, y, w, h):
    """5. Cyclone Xavier: spiral bands over a blue sea, island, rain."""
    cv.sky3(x, y, w, h, (30, 60, 96), (66, 104, 142), (120, 152, 178))
    sea(cv, x, y + h - 30, w, 30, fill=(28, 74, 116))
    cx, cy = x + w // 2, y + h // 2
    for r, col in ((26, (235, 240, 245)), (21, (200, 214, 226)), (16, (235, 240, 245)),
                   (11, (170, 190, 208)), (6, (235, 240, 245))):
        cv.ellipse_ring(cx, cy, r, r, col, 6)
    cv.disc(cx, cy, 6, (250, 210, 110))
    cv.ellbox(x + 8, y + h - 26, x + 66, y + h - 12, fill=(52, 128, 74))
    cv.fill(x + 34, y + h - 44, x + 38, y + h - 24, (110, 80, 40))
    for ang in (-40, -10, 15, 35):
        a = math.radians(ang - 90)
        cv.line(x + 36, y + h - 44, x + 36 + int(14 * math.cos(a)),
                y + h - 44 + int(14 * math.sin(a)), (34, 110, 60), 3)
    for rx in range(x + w - 60, x + w - 8, 12):
        cv.line(rx, y + 10, rx - 6, y + 30, (220, 230, 240), 2)


# ------------------------------------------- illustrated scenes, 6 to 11 ---

def scene_anthropic(cv, x, y, w, h):
    """6. Anthropic IPO: dark board, green rising chart, gold coins."""
    cv.fill(x, y, x + w, y + h, (16, 32, 40))
    for gy in range(y + 8, y + h - 6, 16):
        cv.line(x + 6, gy, x + w - 6, gy, (34, 56, 66), 1)
    pts = [(x + int(w * 0.30), y + int(h * 0.72)), (x + int(w * 0.46), y + int(h * 0.58)),
           (x + int(w * 0.62), y + int(h * 0.42)), (x + int(w * 0.78), y + int(h * 0.52)),
           (x + w - 12, y + int(h * 0.18))]
    cv.lines(pts, (64, 200, 120), 5)
    for px, py in pts[1:-1]:
        cv.disc(px, py, 4, (64, 200, 120))
    ex, ey = pts[-1]
    cv.poly([(ex, ey), (ex - 16, ey + 4), (ex - 6, ey + 16)], (64, 200, 120))
    for i in range(3):
        cy = y + h - 10 - i * 7
        cv.ellbox(x + 12, cy - 6, x + 44, cy + 6, fill=(232, 178, 44),
                  edge=(150, 105, 20), t=2)


def scene_gta(cv, x, y, w, h):
    """7. GTA VI: dusk city, neon sign, palms, car."""
    cv.sky3(x, y, w, h, (46, 30, 84), (150, 64, 120), (240, 130, 90))
    sun(cv, x + w - 30, y + 18, 12, fill=(255, 190, 110))
    street_y = y + h - 18
    for bx, bw, bh in ((0.02, 0.12, 0.44), (0.18, 0.10, 0.58), (0.52, 0.12, 0.50),
                       (0.70, 0.11, 0.62), (0.86, 0.12, 0.40)):
        bh_px = min(int(h * bh), h - 26)
        building(cv, x + int(w * bx), street_y, int(w * bw), bh_px,
                 fill=(36, 24, 58), lit=(255, 190, 120))
    cv.rect(x + int(w * 0.30), y + 6, x + int(w * 0.68), y + 26,
            fill=(24, 12, 40), edge=(255, 90, 190), t=3)
    cv.text(x + int(w * 0.34), y + 9, "VICE CITY", 14, (255, 140, 210), bold=1)
    for px in (0.10, 0.92):
        tx, ty = x + int(w * px), street_y
        cv.fill(tx - 2, ty - 22, tx + 2, ty, (60, 40, 20))
        for ang in (-70, -30, 10, 50):
            a = math.radians(ang - 90)
            cv.line(tx, ty - 22, tx + int(14 * math.cos(a)),
                    ty - 22 + int(14 * math.sin(a)), (30, 120, 60), 3)
    cv.fill(x, street_y, x + w, y + h, (24, 24, 30))
    cv.line(x, y + h - 8, x + w, y + h - 8, (250, 210, 90), 2)
    cx, cy = x + w // 2, y + h - 16
    cv.poly([(cx - 34, cy), (cx - 26, cy - 12), (cx + 22, cy - 12), (cx + 34, cy)],
            (220, 40, 90))
    cv.fill(cx - 36, cy, cx + 36, cy + 8, (200, 30, 80))
    for wx in (-22, 22):
        cv.ellbox(cx + wx - 7, cy + 6, cx + wx + 7, cy + 16, fill=(12, 12, 14))


def scene_alcaraz(cv, x, y, w, h):
    """8. ATP Finals: tennis court, net, ball with motion lines, racket."""
    cv.sky3(x, y, w, h, (70, 120, 180), (120, 165, 205), (180, 205, 225))
    cv.poly([(x + 12, y + h - 8), (x + w - 12, y + h - 8),
             (x + w - 34, y + h * 0.42), (x + 34, y + h * 0.42)], (44, 110, 74))
    cv.lines([(x + 12, y + h - 8), (x + w - 12, y + h - 8),
              (x + w - 34, y + h * 0.42), (x + 34, y + h * 0.42),
              (x + 12, y + h - 8)], (255, 255, 255), 2)
    cv.line(x + w // 2, y + h - 8, x + w // 2, y + h * 0.42, (255, 255, 255), 2)
    cv.fill(x + 26, y + h * 0.52, x + w - 26, y + h * 0.52 + 14, (30, 30, 36))
    cv.line(x + 26, y + h * 0.52, x + w - 26, y + h * 0.52, (255, 255, 255), 2)
    cv.ellipse_ring(x + w - 40, y + 26, 22, 18, (200, 60, 40), 5)
    cv.line(x + w - 40, y + 40, x + w - 52, y + 56, (140, 90, 40), 5)
    bx, by = x + int(w * 0.30), y + int(h * 0.26)
    for mx in range(3):
        cv.line(bx - 34 - mx * 10, by + 4, bx - 18 - mx * 10, by + 4,
                (255, 255, 255), 2)
    cv.ellbox(bx - 10, by - 10, bx + 10, by + 10, fill=(210, 230, 60),
              edge=(120, 140, 30), t=2)
    cv.box_arc(bx - 10, by - 10, bx + 10, by + 10, 300, 60, (120, 140, 30), 2)


def scene_eu(cv, x, y, w, h):
    """9. EU loan: blue field, circle of gold stars, coin stack, columns."""
    cv.fill(x, y, x + w, y + h, (28, 58, 128))
    cx, cy, r = x + w // 2, y + h // 2 - 4, min(18, h // 2 - 10)
    for i in range(12):
        a = math.radians(i * 30 - 90)
        burst(cv, cx + int(r * math.cos(a)), cy + int(r * math.sin(a)), 4,
              fill=(250, 210, 90))
    cv.fill(x, y + h - 30, x + w, y + h, (18, 38, 88))
    for i in range(5):
        colx = x + 12 + i * int((w - 24) / 5)
        cv.fill(colx, y + h - 28, colx + 8, y + h - 6, (232, 222, 190))
    cv.fill(x + 8, y + h - 32, x + w - 8, y + h - 28, (232, 222, 190))
    for i in range(3):
        cy2 = y + h - 14 - i * 8
        cv.ellbox(x + w - 46, cy2 - 6, x + w - 14, cy2 + 6, fill=(232, 178, 44),
                  edge=(150, 105, 20), t=2)


def scene_jeffries(cv, x, y, w, h):
    """10. Jeffries: Capitol dome, gavel, stars and stripes bunting.
    All heights are fractions of the scene box (grid scenes are short)."""
    cv.sky3(x, y, w, h, (64, 110, 170), (130, 170, 205), (200, 216, 228))
    sun(cv, x + 22, y + 14, 9)
    ground_y = y + h - 8
    cv.fill(x + 16, ground_y - 8, x + w - 16, ground_y, (232, 228, 216))
    for i in range(6):
        colx = x + 26 + i * int((w - 52) / 6)
        cv.fill(colx, ground_y - 18, colx + 7, ground_y - 8, (250, 246, 236))
    cv.fill(x + 20, ground_y - 20, x + w - 20, ground_y - 18, (220, 214, 196))
    dcx = x + w // 2
    cv.half_disc(dcx, ground_y - 29, 13, 9, (240, 236, 224))
    cv.fill(dcx - 2, ground_y - 42, dcx + 2, ground_y - 38, (220, 214, 196))
    cv.disc(dcx, ground_y - 43, 3, (200, 170, 90))
    cv.fill(x, ground_y, x + w, y + h, (34, 96, 66))
    gx, gy = x + w - 52, y + h - 8
    cv.fill(gx, gy - 5, gx + 34, gy + 2, (110, 70, 30))
    cv.line(gx + 8, gy + 2, gx + 22, gy + 6, (140, 90, 40), 4)
    for i, c in enumerate(((178, 34, 34), (255, 255, 255), (28, 58, 128)) * 3):
        fx = x + 8 + i * 14
        cv.poly([(fx, y + 4), (fx + 14, y + 4), (fx + 7, y + 12)], c)


def scene_tara(cv, x, y, w, h):
    """11. Tara Gas: LPG tanker with sphere tanks, smoke, rescue boat."""
    cv.sky3(x, y, w, h, (90, 130, 170), (150, 180, 205), (205, 220, 230))
    cloud(cv, x + 10, y + 8, 6)
    sea(cv, x, y + h - 28, w, 28, fill=(30, 76, 118))
    for sx, sy, sr in ((0.82, 0.30, 8), (0.88, 0.22, 10), (0.76, 0.32, 7)):
        cv.ellbox(x + int(w * sx) - sr, y + int(h * sy) - sr,
                  x + int(w * sx) + sr, y + int(h * sy) + sr, fill=(110, 112, 116))
    burst(cv, x + int(w * 0.42), y + int(h * 0.34), 10, fill=(255, 170, 40))
    hy = y + h - 30
    cv.poly([(x + 8, hy), (x + w - 8, hy), (x + w - 22, hy + 14), (x + 20, hy + 14)],
            (150, 40, 36))
    cv.fill(x + 8, hy, x + w - 8, hy + 5, (200, 60, 50))
    for i, sx in enumerate((0.24, 0.46, 0.68)):
        cx = x + int(w * sx)
        cv.ellbox(cx - 15, hy - 22, cx + 15, hy + 2, fill=(232, 228, 216),
                  edge=(90, 90, 90), t=2)
        cv.box_arc(cx - 15, hy - 22, cx + 15, hy + 2, 200, 340, (150, 150, 150), 2)
    cv.fill(x + w - 34, hy - 24, x + w - 18, hy, (40, 40, 46))
    cv.fill(x + w - 34, hy - 24, x + w - 18, hy - 19, (230, 180, 60))
    bx, by = x + 22, y + h - 18
    cv.poly([(bx, by), (bx + 34, by), (bx + 28, by + 8), (bx + 6, by + 8)],
            (230, 120, 30))
    cv.ellbox(bx + 44, by - 4, bx + 58, by + 10, edge=WHITE, t=4)
    cv.ellbox(bx + 44, by - 4, bx + 58, by + 10, edge=(230, 60, 40), t=2)


SCENES = {
    1: scene_gulf, 2: scene_shenzhen, 3: scene_peltola, 4: scene_kerch,
    5: scene_xavier, 6: scene_anthropic, 7: scene_gta, 8: scene_alcaraz,
    9: scene_eu, 10: scene_jeffries, 11: scene_tara,
}


# ------------------------------------------------------------------ world map
# Rough lon/lat continent outlines (own approximations, recognisable at a
# glance); projected linearly into the map box.
CONTINENTS = [
    [(-168, 66), (-140, 70), (-120, 72), (-95, 80),
     (-80, 73), (-65, 60), (-55, 47), (-70, 42),
     (-75, 35), (-80, 26), (-90, 21), (-97, 16),
     (-105, 20), (-115, 30), (-125, 40), (-125, 49),
     (-140, 60), (-165, 60)],
    [(-58, 64), (-45, 60), (-30, 68), (-22, 70), (-40, 76), (-58, 76)],
    [(-80, 10), (-60, 8), (-50, 0), (-35, -8),
     (-40, -20), (-48, -28), (-58, -35), (-65, -40),
     (-70, -52), (-73, -40), (-77, -20), (-80, -5)],
    [(-17, 15), (-10, 30), (0, 35), (10, 37),
     (20, 32), (30, 31), (35, 28), (43, 12),
     (51, 11), (48, 0), (40, -12), (35, -25),
     (28, -33), (18, -35), (12, -18), (9, 4), (-8, 5)],
    [(-10, 36), (-9, 43), (-2, 48), (0, 50),
     (5, 53), (8, 57), (10, 59), (18, 56),
     (21, 55), (24, 59), (28, 60), (30, 65),
     (40, 68), (45, 60), (40, 55), (35, 50),
     (30, 46), (28, 41), (23, 40), (19, 42),
     (12, 44), (8, 44), (3, 42), (0, 38)],
    [(30, 65), (45, 68), (60, 70), (80, 73),
     (110, 76), (140, 72), (160, 66), (170, 60),
     (162, 55), (158, 50), (142, 45), (140, 38),
     (130, 35), (127, 33), (122, 30), (120, 25),
     (110, 20), (108, 12), (105, 8), (100, 6),
     (97, 10), (92, 16), (90, 22), (86, 20),
     (80, 15), (77, 8), (75, 20), (70, 25),
     (66, 25), (60, 25), (56, 26), (52, 28),
     (48, 30), (44, 30), (40, 35), (35, 36),
     (30, 42), (30, 55)],
    [(113, -22), (114, -30), (115, -35), (124, -33),
     (130, -32), (137, -35), (140, -38), (147, -39),
     (150, -37), (153, -27), (153, -20), (146, -19),
     (142, -11), (136, -12), (132, -11), (126, -14), (122, -17)],
]

# story number, longitude, latitude, category, badge offset into empty ocean
MAP_DOTS = [
    (1, 47.9, 29.4, "WAR", -30, -30),
    (2, 114.1, 22.5, "DIP", 36, 16),
    (3, -150.0, 64.0, "POL", -42, -24),
    (4, 36.5, 45.3, "WAR", -36, -28),
    (5, -160.0, -21.0, "WEA", 42, 20),
    (6, -74.0, 40.7, "ECO", 32, -26),
    (7, 7.7, 45.1, "SPO", -46, 20),
    (8, 4.35, 50.85, "POL", -40, -32),
    (9, -77.0, 38.9, "POL", 30, 28),
    (10, 56.5, 26.5, "WAR", 32, 30),
    (11, 34.5, 31.5, "WAR", -32, 26),
    (12, 121.0, 14.6, "DIP", 36, -18),
    (13, 29.0, 41.0, "POL", -44, -34),
    (14, 39.0, 9.0, "WAR", 30, 28),
    (15, 4.3, 52.1, "POL", 44, -30),
]


def draw_map(cv, x, y, w, h):
    """World map: sea, rough continents, numbered badges on leader lines."""
    cv.rect(x, y, x + w, y + h, fill=SEA, edge=NAVY, t=2)
    for gx in range(x + w // 6, x + w, w // 6):
        cv.line(gx, y, gx, y + h, (190, 210, 224), 1)
    for gy in range(y + h // 4, y + h, h // 4):
        cv.line(x, gy, x + w, gy, (190, 210, 224), 1)

    def proj(lon, lat):
        px = x + (lon + 170.0) / 360.0 * w
        py = y + (85.0 - lat) / 145.0 * h
        return (px, py)

    for poly in CONTINENTS:
        cv.poly([proj(lon, lat) for lon, lat in poly], LAND)
        cv.lines([proj(lon, lat) for lon, lat in poly] + [proj(*poly[0])],
                 (170, 158, 120), 1)
    for label, lx, ly in (("PACIFIC", -150, -8), ("ATLANTIC", -30, 5),
                          ("INDIAN OCEAN", 75, -28), ("ARCTIC", 55, 80)):
        px, py = proj(lx, ly)
        cv.text(px, py, label, 10, (90, 115, 140))
    for num, lon, lat, cat, dx, dy in MAP_DOTS:
        px, py = proj(lon, lat)
        bx = min(max(px + dx, x + 12), x + w - 12)
        by = min(max(py + dy, y + 12), y + h - 12)
        cv.line(px, py, bx, by, (90, 90, 90), 1)
        cv.disc(px, py, 3, CAT[cat][1])
        badge(cv, bx, by, 10, num, fill=CAT[cat][1])


# -------------------------------------------------------------------- content
LEADS = [
    {"num": 1, "cat": "WAR",
     "head": "GULF: IRAN HITS KUWAIT AND BAHRAIN",
     "sub": "Tehran fires drones at a US base in Kuwait and sites in Bahrain "
            "after a US jet struck Qeshm Island. First Kuwait attack since September."},
    {"num": 2, "cat": "DIP",
     "head": "SHENZHEN: XI GREETS TRUMP ON TARMAC",
     "sub": "Xi meets Trump at Air Force One; Xi and Putin hold talks a day "
            "before the first Trump-Xi-Putin summit on Thursday."},
    {"num": 3, "cat": "POL",
     "head": "PELTOLA WINS ALASKA - DEMOCRATS 56-44",
     "sub": "Democrat beats two-term Republican Sullivan in the last Senate "
            "race. Democrats take a 56-44 majority."},
]

GRID = [
    {"num": 4, "cat": "WAR",
     "head": "KERCH: RECORD 1,441 DRONES IN ONE NIGHT",
     "sub": "Second-day strikes; Russia hits Izmail"},
    {"num": 5, "cat": "WEA",
     "head": "CYCLONE XAVIER: 315 KM/H GUSTS",
     "sub": "Cat 5 storm batters Cook Islands."},
    {"num": 6, "cat": "ECO",
     "head": "ANTHROPIC IPO: $83, BIGGEST EVER",
     "sub": "$81.3BN raised; trading starts Thu."},
    {"num": 7, "cat": "ECO",
     "head": "GTA VI ROLLS OUT AFTER 13 YEARS",
     "sub": "Midnight launch; Take-Two +6.2%."},
    {"num": 8, "cat": "SPO",
     "head": "ALCARAZ INTO ATP FINALS SEMIS",
     "sub": "Medvedev 6-2, 6-4; Tiafoe wins first."},
    {"num": 9, "cat": "POL",
     "head": "EU: 45 BILLION EUROS FOR UKRAINE",
     "sub": "New 2027 loan; four states opt out."},
    {"num": 10, "cat": "POL",
     "head": "JEFFRIES NOMINATED SPEAKER 251-11",
     "sub": "First Black Speaker if elected 3 Jan."},
    {"num": 11, "cat": "WAR",
     "head": "TARA GAS: 1 MISSING, 11 HURT",
     "sub": "Tanker hit twice; 24 crew rescued."},
]

# items 12..32, in order; the number is the position + 12
ALSO = [
    "GAZA TRUCE NEAR COLLAPSE, BOARD WARNS",
    "TRUMP CLAIMS BIG PHILIPPINES DEAL",
    "IMAMOGLU: 2 MORE YEARS, NEW BAN",
    "ETHIOPIA-ERITREA BORDER CLASHES",
    "ICJ TO RULE THURSDAY ON MYANMAR",
    "SLOVAKIA: THOUSANDS PROTEST FICO",
    "WAYMO PULLED OFF US FREEWAYS",
    "MARKETS: DOW -1.1%, S&P -0.2%",
    "FED: INFLATION RISKS IN FOCUS",
    "IRAQ: MILITIA TOLD TO LEAVE BY FRIDAY",
    "EU-INDONESIA TRADE DEALS APPROVED",
    "YEMEN: 64 CHILDREN KILLED SINCE SEPT",
    "ATALAY MUST BE RELEASED, COURT RULES",
    "UKRAINE: 141 RUSSIAN DRONES OVERNIGHT",
    "MOSSAD CHIEF LOBBIED FOR IRAN STRIKES",
    "BAHRAIN REFINERY BACK ABOVE 80%",
    "US WEIGHS DISCLOSING CHINA AI USE",
    "ECB TO DISCUSS RAISING RESERVE RULE",
    "PALO ALTO +10% ON EARNINGS",
    "SCOTLAND: 7 PLAYERS OUT BEFORE JAPAN",
    "CYCLONE AKVAN: LANDFALL FRIDAY",
]

FIGURES = [("$83", "ANTHROPIC IPO PRICE"), ("1,441", "DRONES IN ONE NIGHT"),
           ("315 KM/H", "CYCLONE XAVIER GUSTS"), ("56-44", "DEMOCRAT SENATE MAJORITY")]

TOMORROW_PRE = "TOMORROW - THU 19 NOV: "
TOMORROW_ITEMS = ("TRUMP-XI-PUTIN SUMMIT IN SHENZHEN  |  ICJ RULES ON MYANMAR  |  "
                  "ANTHROPIC SHARES TRADE AS ANT")

SOURCE_LINE = ("Sources: Reuters, AP, BBC, AFP, Al Jazeera, ATP, Anthropic, "
               "NZ MetService, IMD. All stories from Wednesday 18 November 2026.")


# ----------------------------------------------------------------- page build
def build():
    cv = Canvas(W, H, CREAM)
    # double outer border
    cv.rect(4, 4, W - 5, H - 5, edge=NAVY, t=3)
    cv.rect(9, 9, W - 10, H - 10, edge=RED, t=1)
    x0, x1 = 16, W - 16
    cw = x1 - x0  # 992

    # --- masthead: cream broadsheet, giant navy date, red rules -------------
    y = 16
    hline(cv, x0, x1, y, RED, 3)
    y += 8
    cv.ctext((x0 + x1) // 2, y, "THE WORLD IN ONE DAY", 20, NAVY, bold=1)
    y += 27
    date = "WEDNESDAY 18 NOVEMBER 2026"
    ds = fit_pt(date, 60, cw)
    cv.ctext((x0 + x1) // 2, y, date, ds, NAVY, bold=2)
    y += ds + 8
    hline(cv, x0, x1, y, NAVY, 2)
    y += 7
    cv.text(x0, y, "32 STORIES - 6 CONTINENTS", 16, RED, bold=1)
    rs = "ALL FROM WEDNESDAY"
    cv.text(x1 - twidth(rs, 16), y, rs, 16, NAVY, bold=1)
    y += 22
    hline(cv, x0, x1, y, RED, 3)
    y += 8

    # --- figures band: navy, directly under the masthead ---------------------
    band_y = y
    band_h = 46
    cv.fill(x0, band_y, x1, band_y + band_h, NAVY)
    cell_w = cw // 4
    for i, (val, lab) in enumerate(FIGURES):
        cx = x0 + cell_w * i + cell_w // 2
        if i:
            cv.line(x0 + cell_w * i, band_y + 8, x0 + cell_w * i,
                    band_y + band_h - 8, (120, 140, 180), 1)
        cv.ctext(cx, band_y + 5, val, 23, WHITE, bold=1)
        cv.text(cx - twidth(lab, 12) / 2, band_y + 31, lab, 12, (200, 210, 230))
    y = band_y + band_h + 10

    # --- three equal leads ---------------------------------------------------
    lead_y = y
    col_w = (cw - 2 * 14) // 3
    scene_h = 120
    lead_bottom = lead_y
    for i, story in enumerate(LEADS):
        cx = x0 + i * (col_w + 14)
        cv.rect(cx, lead_y, cx + col_w, lead_y + scene_h, edge=NAVY, t=2)
        SCENES[story["num"]](cv, cx + 2, lead_y + 2, col_w - 4, scene_h - 4)
        badge(cv, cx + 18, lead_y + 18, 13, story["num"])
        ty = lead_y + scene_h + 6
        lab, col = CAT[story["cat"]]
        cv.text(cx, ty, lab, 12, col, bold=1)
        ty += 17
        ty = cv.para(cx, ty, story["head"], 22, INK, col_w, bold=1, leading=25)
        ty = cv.para(cx, ty + 3, story["sub"], 14, GREY, col_w, leading=17)
        lead_bottom = max(lead_bottom, ty)
    y = lead_bottom + 8
    hline(cv, x0, x1, y, HAIR, 1)
    y += 8

    # --- grid: 4 x 2 illustrated (rows sized from measured content) --------
    grid_y = y
    gcol = (cw - 3 * 10) // 4
    grow_y = grid_y
    for r in range(2):
        row_bottom = grow_y
        for c in range(4):
            story = GRID[r * 4 + c]
            gx = x0 + c * (gcol + 10)
            gy = grow_y
            sh = 60
            cv.rect(gx, gy, gx + gcol, gy + sh, edge=NAVY, t=1)
            SCENES[story["num"]](cv, gx + 1, gy + 1, gcol - 2, sh - 2)
            badge(cv, gx + 13, gy + 13, 10, story["num"])
            ty = gy + sh + 4
            lab, col = CAT[story["cat"]]
            cv.text(gx, ty, lab, 11, col, bold=1)
            ty += 15
            ty = cv.para(gx, ty, story["head"], 16, INK, gcol, bold=1, leading=18)
            fs = fit_pt(story["sub"], 12, gcol)
            cv.text(gx, ty + 1, story["sub"], fs, GREY)
            row_bottom = max(row_bottom, ty + 15)
        grow_y = row_bottom + 8
    y = grow_y + 2
    hline(cv, x0, x1, y, HAIR, 1)
    y += 8

    # --- bottom: map left, ALSO list right -----------------------------------
    bot_y = y
    map_w = 400
    also_x = x0 + map_w + 14
    also_w = x1 - also_x
    cv.text(x0, bot_y, "WHERE IT HAPPENED", 16, NAVY, bold=1)
    cv.text(also_x, bot_y, "ALSO ON WEDNESDAY", 16, NAVY, bold=1)
    my = bot_y + 24
    map_h = 150
    draw_map(cv, x0, my, map_w, map_h)
    # legend, one line, abbreviations to fit
    leg = [("WAR", RED), ("DIPLOMACY", NAVY2), ("POLITICS", GREEN),
           ("ECONOMY", TEAL), ("WEATHER + SPORT", AMBER)]
    lx = x0
    ly = my + map_h + 7
    for lab, col in leg:
        cv.disc(lx + 5, ly + 6, 5, col)
        lx += 13
        cv.text(lx, ly, lab, 11, INK)
        lx += twidth(lab, 11) + 12
    # ALSO list: two columns, shrink-to-fit per line
    col2_w = (also_w - 12) // 2
    rows = (len(ALSO) + 1) // 2
    ay = my
    for i, txt in enumerate(ALSO):
        num = 12 + i
        c = 0 if i < rows else 1
        r = i if i < rows else i - rows
        ax = also_x + c * (col2_w + 12)
        ry = ay + r * 15
        cv.text(ax, ry, str(num), 12, RED, bold=1)
        fs = fit_pt(txt, 12, col2_w - 26)
        cv.text(ax + 24, ry, txt, fs, INK)
    y = my + map_h + 7 + 15 + 4

    # --- tomorrow strip + source line ----------------------------------------
    hline(cv, x0, x1, y, RED, 2)
    y += 6
    cv.text(x0, y, TOMORROW_PRE, 13, RED, bold=1)
    tx = x0 + twidth(TOMORROW_PRE, 13)
    fs = fit_pt(TOMORROW_ITEMS, 13, x1 - tx)
    cv.text(tx, y, TOMORROW_ITEMS, fs, NAVY)
    y += 18
    hline(cv, x0, x1, y, NAVY, 1)
    y += 5
    fs = fit_pt(SOURCE_LINE, 12, cw)
    cv.text((x0 + x1) // 2 - twidth(SOURCE_LINE, fs) / 2, y, SOURCE_LINE, fs, GREY)
    assert y + 16 <= H - 10, "layout overflow: %d" % y
    return cv


# ------------------------------------------------------------------- PNG out
def chunk(typ, data):
    body = struct.pack(">I", len(data)) + typ + data
    return body + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)


def write_png(path, cv):
    raw = bytearray()
    for y in range(cv.h):
        raw.append(0)
        raw += cv.buf[y * cv.w * 3:(y + 1) * cv.w * 3]
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "out")
    os.makedirs(out_dir, exist_ok=True)
    cv = build()
    path = os.path.join(out_dir, "entry.png")
    write_png(path, cv)
    print("wrote", path, (cv.w, cv.h))


if __name__ == "__main__":
    main()
