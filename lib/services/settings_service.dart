import 'package:shared_preferences/shared_preferences.dart';

import '../core/config/app_config.dart';

/// How the accurate (post-recording) transcription pass is produced.
enum TranscriptionMode {
  /// Send the recorded audio to the backend Whisper API.
  cloud,

  /// Transcribe entirely on-device with whisper.cpp (whisper_ggml).
  onDevice,
}

/// Which self-hosted cloud model handles transcription when
/// [TranscriptionMode.cloud] is selected. Both speak the same
/// `POST /transcribe` contract; they differ in the model behind it.
enum CloudModel { qwen, whisper }

extension CloudModelInfo on CloudModel {
  String get label => switch (this) {
        CloudModel.qwen => 'Qwen3-ASR',
        CloudModel.whisper => 'Whisper large-v3',
      };

  /// Compact name for chips / inline mentions.
  String get shortLabel => switch (this) {
        CloudModel.qwen => 'Qwen',
        CloudModel.whisper => 'Whisper',
      };

  String get description => switch (this) {
        CloudModel.qwen =>
          'Qwen3-ASR 1.7B. Mendukung teks langsung saat merekam.',
        CloudModel.whisper =>
          'Whisper large-v3. Timestamp per segmen, kuat untuk audio panjang.',
      };

  /// Backend base URL serving this model. Empty when not configured.
  String get baseUrl => switch (this) {
        CloudModel.qwen => AppConfig.qwenBaseUrl,
        CloudModel.whisper => AppConfig.whisperBaseUrl,
      };

  /// True when a backend URL is configured for this model.
  bool get isConfigured => baseUrl.isNotEmpty;
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
  static const _keyCloudModel = 'cloud_model';

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

  /// Which cloud model handles transcription in [TranscriptionMode.cloud].
  /// Defaults to whichever is configured (preferring the saved choice), so a
  /// single-backend setup still resolves to a usable model.
  Future<CloudModel> getCloudModel() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_keyCloudModel);
    final saved = CloudModel.values.firstWhere(
      (m) => m.name == raw,
      orElse: () => CloudModel.qwen,
    );
    // If the saved model isn't configured but the other is, fall back to it
    // rather than silently producing mock output.
    if (!saved.isConfigured) {
      final other =
          saved == CloudModel.qwen ? CloudModel.whisper : CloudModel.qwen;
      if (other.isConfigured) return other;
    }
    return saved;
  }

  Future<void> setCloudModel(CloudModel model) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyCloudModel, model.name);
  }
}
