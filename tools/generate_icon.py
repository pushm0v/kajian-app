#!/usr/bin/env python3
"""Generate the Kajian Notes app icon set from a single vector definition.

Concept: a microphone whose grille is an open book (Qur'an / kitab), enclosed by
a mosque onion-arch and topped with a crescent and star — recording, studying,
and Islamic identity in one mark — on the app's soft mint-teal gradient.

Outputs (into ../assets/icon):
  app_icon.svg              master vector (rounded, with background)
  app_icon.png              1024 full-bleed square, opaque  -> iOS / web / legacy
  app_icon_background.png   1024 gradient only               -> Android adaptive bg
  app_icon_foreground.png   1024 transparent glyph (safe zone) -> Android adaptive fg
  app_icon_monochrome.png   1024 white silhouette            -> Android 13 themed icon
And ../docs/app_icon_preview.png for documentation.

Usage:
  pip install cairosvg Pillow
  python3 tools/generate_icon.py
  flutter pub run flutter_launcher_icons     # apply to native projects
"""
import math
import os

import cairosvg

CX = 512

# Palette
WHITE = "#FFFFFF"
BOOKLINE = "#5FBEAA"   # soft teal for the open-book text lines
STROKE_W = 16          # arch / mic-arm line weight

# Vertical offset applied to the whole glyph so it centres in the canvas.
OY = 158


def star(cx, cy, r_out, r_in, points=5, rot=-90):
    pts = []
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(rot + i * 180.0 / points)
        pts.append(f"{cx + r*math.cos(a):.1f} {cy + r*math.sin(a):.1f}")
    return "M " + " L ".join(pts) + " Z"


def glyph(mono=False):
    white = WHITE
    line = WHITE if mono else BOOKLINE

    # Crescent + star finial — the Islamic/kajian identity.
    crescent = (f'<path d="M 500 96 A 40 40 0 1 0 536 148 '
                f'A 30 30 0 1 1 500 96 Z" fill="{white}"/>')
    star_el = f'<path d="{star(540, 118, 20, 8)}" fill="{white}"/>'

    # Onion arch enclosing the mic head — the mosque/mihrab silhouette.
    arch = (f'<path d="M 418 366 '
            f'C 396 312 408 248 460 220 '
            f'C 482 206 500 202 512 200 '
            f'C 524 202 542 206 564 220 '
            f'C 616 248 628 312 606 366" '
            f'fill="none" stroke="{white}" stroke-width="{STROKE_W}" '
            f'stroke-linecap="round"/>')
    finial = f'<circle cx="512" cy="186" r="9" fill="{white}"/>'

    # Mic holder arms hugging the book sides, plus stem + base.
    arms = (f'<path d="M 405 372 C 372 406 372 456 405 492" '
            f'fill="none" stroke="{white}" stroke-width="{STROKE_W}" '
            f'stroke-linecap="round"/>'
            f'<path d="M 619 372 C 652 406 652 456 619 492" '
            f'fill="none" stroke="{white}" stroke-width="{STROKE_W}" '
            f'stroke-linecap="round"/>')
    stem = (f'<line x1="512" y1="476" x2="512" y2="558" stroke="{white}" '
            f'stroke-width="{STROKE_W}" stroke-linecap="round"/>')
    base = (f'<line x1="452" y1="568" x2="572" y2="568" stroke="{white}" '
            f'stroke-width="{STROKE_W}" stroke-linecap="round"/>')

    # Open book = the mic grille (Qur'an / kitab being studied): spine dips,
    # pages fan up and out.
    book = (f'<path d="M 512 388 Q 468 356 405 360 L 416 452 '
            f'Q 464 472 512 468 Z" fill="{white}"/>'
            f'<path d="M 512 388 Q 556 356 619 360 L 608 452 '
            f'Q 560 472 512 468 Z" fill="{white}"/>')
    spine = ("" if mono else
             f'<line x1="512" y1="392" x2="512" y2="466" stroke="{line}" '
             f'stroke-width="7" stroke-linecap="round" opacity="0.6"/>')
    booklines = "" if mono else "\n".join(
        f'<line x1="{xo}" y1="{yo+6}" x2="498" y2="{yo}" stroke="{line}" '
        f'stroke-width="7" stroke-linecap="round"/>'
        f'<line x1="{1024-xo}" y1="{yo+6}" x2="526" y2="{yo}" stroke="{line}" '
        f'stroke-width="7" stroke-linecap="round"/>'
        for xo, yo in [(430, 402), (426, 422), (424, 442)]
    )

    inner = "\n".join(
        [crescent, star_el, arch, finial, arms, stem, base, book, spine, booklines]
    )
    return f'<g transform="translate(0,{OY})">{inner}</g>'


def bg_only(radius=0):
    return ('<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#BFEEE1"/>'
            '<stop offset="0.5" stop-color="#8FE0CE"/>'
            '<stop offset="1" stop-color="#63CBB4"/></linearGradient></defs>'
            f'<rect x="0" y="0" width="1024" height="1024" rx="{radius}" '
            'fill="url(#bg)"/>')


def svg(with_bg=True, scale=1.0, mono=False, radius=228):
    inner = glyph(mono=mono)
    if scale != 1.0:
        inner = (f'<g transform="translate({CX},512) scale({scale}) '
                 f'translate({-CX},-512)">{inner}</g>')
    bg = bg_only(radius) if with_bg else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="1024" '
            f'height="1024" viewBox="0 0 1024 1024">{bg}{inner}</svg>')


def render(svgstr, out, size=1024):
    cairosvg.svg2png(bytestring=svgstr.encode(), write_to=out,
                     output_width=size, output_height=size)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    icon = os.path.join(here, "..", "assets", "icon")
    docs = os.path.join(here, "..", "docs")
    os.makedirs(icon, exist_ok=True)
    os.makedirs(docs, exist_ok=True)

    with open(os.path.join(icon, "app_icon.svg"), "w") as f:
        f.write(svg(with_bg=True, radius=228))
    render(svg(with_bg=True, radius=0), os.path.join(icon, "app_icon.png"))
    render(f'<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" '
           f'viewBox="0 0 1024 1024">{bg_only(0)}</svg>',
           os.path.join(icon, "app_icon_background.png"))
    render(svg(with_bg=False, scale=0.80),
           os.path.join(icon, "app_icon_foreground.png"))
    render(svg(with_bg=False, scale=0.80, mono=True),
           os.path.join(icon, "app_icon_monochrome.png"))
    render(svg(with_bg=True, radius=228),
           os.path.join(docs, "app_icon_preview.png"), 512)
    print("Generated icon set in assets/icon/")


if __name__ == "__main__":
    main()
