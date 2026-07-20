import 'package:shared_preferences/shared_preferences.dart';

/// How the accurate (post-recording) transcription pass is produced.
enum TranscriptionMode {
  /// Send the recorded audio to the backend Whisper API.
  cloud,

  /// Transcribe entirely on-device with whisper.cpp (whisper_ggml).
  onDevice,
}

extension TranscriptionModeLabel on TranscriptionMode {
  String get label => switch (this) {
        TranscriptionMode.cloud => 'Cloud (Whisper API)',
        TranscriptionMode.onDevice => 'Di perangkat (offline)',
      };

  String get description => switch (this) {
        TranscriptionMode.cloud =>
          'Mengirim rekaman ke server untuk ditranskrip. Membutuhkan '
              'koneksi internet.',
        TranscriptionMode.onDevice =>
          'Transkrip sepenuhnya di perangkat ini. Bisa dipakai offline; '
              'penggunaan pertama akan mengunduh model suara.',
      };
}

/// Persisted user preferences, backed by [SharedPreferences].
class SettingsService {
  static const _keyTranscriptionMode = 'transcription_mode';
  static const _keyCloudLiveCaptions = 'cloud_live_captions_enabled';

  Future<TranscriptionMode> getTranscriptionMode() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_keyTranscriptionMode);
    return TranscriptionMode.values.firstWhere(
      (m) => m.name == raw,
      // On-device works with no backend required; cloud mode returns mock
      // data until a backend is configured, so don't default to it silently.
      orElse: () => TranscriptionMode.onDevice,
    );
  }

  Future<void> setTranscriptionMode(TranscriptionMode mode) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyTranscriptionMode, mode.name);
  }

  /// Whether live captions during recording should also stream to the
  /// self-hosted cloud model (backend/app/streaming.py), alongside the
  /// existing on-device captions. Off by default — it requires a backend
  /// to be configured (AppConfig.backendBaseUrl) and uses extra bandwidth
  /// for the whole recording, so this is opt-in even when a backend exists.
  Future<bool> getCloudLiveCaptionsEnabled() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_keyCloudLiveCaptions) ?? false;
  }

  Future<void> setCloudLiveCaptionsEnabled(bool enabled) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_keyCloudLiveCaptions, enabled);
  }
}
