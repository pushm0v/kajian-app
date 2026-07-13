#!/usr/bin/env python3
"""Generate the Kajian Notes app icon set from a single vector definition.

Concept: a microphone crowned with a mosque onion-dome and a crescent finial,
with soundwaves radiating outward — fusing the Islamic/kajian tone with the
app's audio-notes purpose, on the app's teal gradient.

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
CREAM = "#FFF7E6"
GOLD = "#EAC57B"
GOLD_D = "#D8A94E"
TEALG = "#0E6E63"


def sound_arc(r, side, spread=48):
    a0, a1 = math.radians(-spread), math.radians(spread)
    cy = 500
    if side == "R":
        x0, y0 = CX + r * math.cos(a0), cy + r * math.sin(a0)
        x1, y1 = CX + r * math.cos(a1), cy + r * math.sin(a1)
        return f"M {x0:.1f} {y0:.1f} A {r} {r} 0 0 1 {x1:.1f} {y1:.1f}"
    x0, y0 = CX - r * math.cos(a0), cy + r * math.sin(a0)
    x1, y1 = CX - r * math.cos(a1), cy + r * math.sin(a1)
    return f"M {x0:.1f} {y0:.1f} A {r} {r} 0 0 0 {x1:.1f} {y1:.1f}"


def glyph(mono=False):
    cream = gold = gold_d = "#FFFFFF" if mono else None
    cream = cream or CREAM
    gold = gold or GOLD
    gold_d = gold_d or GOLD_D

    waves = "\n".join(
        f'<path d="{sound_arc(r, s)}" fill="none" stroke="{gold}" '
        f'stroke-width="{w}" stroke-linecap="round" opacity="{op}"/>'
        for r, w, op in [(200, 20, 0.85), (250, 16, 0.5)]
        for s in ("L", "R")
    )

    dome = (f'<path d="M 418 432 C 398 414 380 396 396 356 '
            f'C 412 314 502 296 512 278 C 522 296 612 314 628 356 '
            f'C 644 396 626 414 606 432 Z" fill="{gold}"/>')
    dome_shade = (f'<path d="M 512 278 C 522 296 612 314 628 356 '
                  f'C 644 396 626 414 606 432 L 512 432 Z" '
                  f'fill="{gold_d}" opacity="0.32"/>')
    neck = f'<rect x="505" y="262" width="14" height="24" rx="6" fill="{gold_d}"/>'
    crescent = (f'<path d="M 512 206 A 32 32 0 1 0 542 246 '
                f'A 25 25 0 1 1 512 206 Z" fill="{gold}"/>')

    capsule = f'<rect x="417" y="420" width="190" height="224" rx="95" fill="{cream}"/>'
    grille = "\n".join(
        f'<line x1="454" y1="{y}" x2="570" y2="{y}" stroke="{TEALG}" '
        f'stroke-width="13" stroke-linecap="round" opacity="0.85"/>'
        for y in (474, 512, 550)
    )
    bracket = (f'<path d="M 360 540 A 152 152 0 0 0 664 540" fill="none" '
               f'stroke="{cream}" stroke-width="26" stroke-linecap="round"/>')
    stem = (f'<line x1="512" y1="690" x2="512" y2="812" stroke="{cream}" '
            f'stroke-width="26" stroke-linecap="round"/>')
    base = (f'<line x1="440" y1="820" x2="584" y2="820" stroke="{cream}" '
            f'stroke-width="26" stroke-linecap="round"/>')

    if mono:
        grille = dome_shade = ""
    return "\n".join(
        [waves, bracket, stem, base, capsule, grille, dome, dome_shade,
         neck, crescent]
    )


def bg_only(radius=0):
    return ('<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
            '<stop offset="0" stop-color="#12A594"/>'
            '<stop offset="0.55" stop-color="#0C8074"/>'
            '<stop offset="1" stop-color="#075E55"/></linearGradient></defs>'
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
