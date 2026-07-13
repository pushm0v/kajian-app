# App icon

![Kajian Notes icon](app_icon_preview.png)

**Concept.** A **microphone whose grille is an open book** (Qur'an / kitab),
enclosed by a **mosque onion-arch** and topped with a **crescent and star**, on
the app's soft **mint-teal gradient**. One mark ties together the three things
the app is about: recording audio (mic), studying kajian (open book), and its
Islamic identity (arch + crescent). Clean white line-art keeps it legible at
small sizes.

## Files (`assets/icon/`)

| File                        | Purpose                                             |
| --------------------------- | --------------------------------------------------- |
| `app_icon.svg`              | Master vector source (edit-friendly)                |
| `app_icon.png`              | 1024² full-bleed, opaque — iOS / web / legacy       |
| `app_icon_background.png`   | 1024² gradient — Android **adaptive** background     |
| `app_icon_foreground.png`   | 1024² transparent glyph (safe zone) — adaptive fg    |
| `app_icon_monochrome.png`   | 1024² white silhouette — Android 13+ **themed** icon |

The glyph in the adaptive foreground is scaled to ~80% so it stays inside the
adaptive safe zone and is never clipped by circular or squircle launcher masks.

## Regenerate the source images

The icon is generated from a single vector definition, so it stays crisp and is
easy to tweak (colors live at the top of the script).

```bash
pip install cairosvg Pillow
python3 tools/generate_icon.py
```

## Apply to the native projects

Icons are produced by [`flutter_launcher_icons`](https://pub.dev/packages/flutter_launcher_icons),
configured in `pubspec.yaml`. After running `flutter create` (to create the
native folders) and `flutter pub get`:

```bash
dart run flutter_launcher_icons
```

This writes all required iOS `AppIcon.appiconset` sizes, Android mipmaps +
adaptive `ic_launcher.xml`, the monochrome themed layer, and the web favicons.

## Tweaking the design

Open `tools/generate_icon.py`:

- **Palette** — `WHITE`, `BOOKLINE`, `STROKE_W` and the `bg_only()` gradient
  stops control all colors and line weight.
- **Crescent + star** — the `crescent` path and `star()` helper in `glyph()`.
- **Arch** — the `arch` path (onion curve) and `finial` knob.
- **Mic body** — the `arms`, `stem`, and `base` strokes.
- **Open book** — the `book` pages, `spine`, and `booklines` in `glyph()`.
- **Vertical position** — `OY` shifts the whole motif up/down.

Re-run the two commands above to apply changes.
