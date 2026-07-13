# App icon

![Kajian Notes icon](app_icon_preview.png)

**Concept.** A **microphone whose grille is an open book** (Qur'an / kitab),
enclosed by a **mosque onion-arch** and topped with a **crescent and star**, on
the app's soft **mint-teal gradient**. One mark ties together the three things
the app is about: recording audio (mic), studying kajian (open book), and its
Islamic identity (arch + crescent).

## Source

`assets/icon/app_icon.png` — 1024² full-bleed, opaque, cropped and cleaned up
from the reference artwork (`source_master.png`) to remove its mockup framing
(rounded-corner preview shadow on a black canvas). Used as-is for iOS,
Android, and web; no separate adaptive-icon layers.

## Apply to the native projects

Icons are produced by [`flutter_launcher_icons`](https://pub.dev/packages/flutter_launcher_icons),
configured in `pubspec.yaml`. After running `flutter create` (to create the
native folders) and `flutter pub get`:

```bash
dart run flutter_launcher_icons
```

This writes all required iOS `AppIcon.appiconset` sizes, Android mipmaps, and
the web favicons.

## Updating the icon

Replace `assets/icon/app_icon.png` with a new 1024×1024 full-bleed square
(opaque, no transparency needed — `remove_alpha_ios` strips any alpha for
iOS) and re-run `dart run flutter_launcher_icons`.
