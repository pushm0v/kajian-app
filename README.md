# Kajian Notes 🎙️📖

<p align="center">
  <img src="docs/app_icon_preview.png" width="128" alt="Kajian Notes app icon" />
</p>

A cross-platform (iOS + Android) Flutter app that **records kajian audio**,
**transcribes it**, and **generates structured study notes automatically**.

Built for long-form Islamic lectures that commonly mix **Indonesian, Malay,
English, and Arabic**.

## What it does

1. **Record** a kajian with a live level meter and elapsed timer.
2. **Live captions** appear as you record, using the device's on-device speech
   recognition (works offline, instant feedback).
3. **High-accuracy transcription** runs after recording via a cloud model
   (Whisper) for a clean, timestamped transcript — the *hybrid* strategy:
   fast/offline live captions + accurate cloud pass.
4. **AI notes** are generated from the transcript with an LLM (Claude): a
   summary, key points, topics, Quran/Hadith references, and action items.
5. **Library** of all your saved kajian, stored locally on the device.

> Runs fully in **mock mode** with no backend or API keys, so you can build and
> demo the entire flow immediately.

## Architecture

```
lib/
├── main.dart                 App entry, provider wiring
├── app.dart                  MaterialApp + theming
├── core/
│   ├── config/app_config.dart      Backend URL / model config (--dart-define)
│   ├── constants/                  App + locale constants
│   ├── theme/                      Light & dark Material 3 themes
│   └── utils/formatters.dart       Duration / date formatting
├── models/                   KajianSession, TranscriptSegment, KajianNote
├── services/
│   ├── audio_recorder_service.dart      record plugin (m4a capture + levels)
│   ├── live_transcription_service.dart  on-device speech_to_text (live)
│   ├── cloud_transcription_service.dart Whisper via backend (accurate)
│   ├── ai_notes_service.dart            Claude notes via backend
│   └── storage_service.dart            local JSON persistence
├── providers/
│   ├── session_provider.dart      Library state + processing pipeline
│   └── recording_controller.dart  Live recording session state
├── screens/
│   ├── home/                  Session library + record FAB
│   ├── record/                Live recording UI + waveform
│   └── session_detail/        Notes + Transcript tabs
└── widgets/                   Shared widgets (status chip, …)
```

**State management:** `provider` (ChangeNotifier) — approachable and dependency-light.
**Transcription:** hybrid — `speech_to_text` (live/offline) + cloud Whisper (accurate).
**Notes:** LLM summarization behind a backend proxy (see `docs/BACKEND.md`).
**Storage:** local JSON via `path_provider` (swap for sqflite/Drift later — the
`StorageService` boundary keeps that change localised).

## Getting started

Requires the Flutter SDK (>= 3.19). This repo contains the Dart source; generate
the native iOS/Android projects on your machine:

```bash
# 1. Generate native platform folders (won't overwrite lib/)
flutter create --platforms=android,ios --org com.yourorg .

# 2. Install dependencies
flutter pub get

# 3. Apply microphone/speech permissions
#    -> follow docs/PLATFORM_SETUP.md

# 4. Generate the app launcher icons (see docs/ICONS.md)
dart run flutter_launcher_icons

# 5. Run (mock mode — no backend needed)
flutter run
```

### Wiring real transcription + notes

Stand up the backend from `docs/BACKEND.md`, then run pointing at it:

```bash
flutter run --dart-define=BACKEND_BASE_URL=https://api.yourdomain.com
```

Optionally override the notes model:

```bash
flutter run \
  --dart-define=BACKEND_BASE_URL=https://api.yourdomain.com \
  --dart-define=AI_NOTES_MODEL=claude-opus-4-8
```

## Store deployment

- **Android:** `flutter build appbundle` → upload the `.aab` to Google Play.
- **iOS:** `flutter build ipa` → upload via Xcode / Transporter to App Store Connect.
- Provide privacy-policy disclosures for microphone + speech recognition usage;
  both stores require this for audio-recording apps.

## Roadmap / next steps

- [ ] Background-service recording for lock-screen resilience (see PLATFORM_SETUP.md)
- [ ] Editable transcript with re-generate notes
- [ ] Playback with tap-to-seek from transcript timestamps
- [ ] Search across all kajian by topic/reference
- [ ] Cloud sync & multi-device backup
- [ ] Export notes to PDF / Markdown / share sheet

## Security

Never embed provider API keys in the app bundle — always proxy through your
backend. See `docs/BACKEND.md`. The `.gitignore` excludes `.env` and
`lib/core/config/secrets.dart` to help avoid committing secrets.
