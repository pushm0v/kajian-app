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

  Future<TranscriptionMode> getTranscriptionMode() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_keyTranscriptionMode);
    return TranscriptionMode.values.firstWhere(
      (m) => m.name == raw,
      orElse: () => TranscriptionMode.cloud,
    );
  }

  Future<void> setTranscriptionMode(TranscriptionMode mode) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyTranscriptionMode, mode.name);
  }
}
