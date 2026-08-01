import 'package:shared_preferences/shared_preferences.dart';

import '../core/config/app_config.dart';

/// Which self-hosted cloud model handles transcription. Both speak the
/// same `POST /transcribe` contract; they differ in the model behind it.
///
/// There is no on-device option any more: whisper.cpp (whisper_ggml) ran
/// a small `base` model downloaded to the phone, which was meaningfully
/// worse than the self-hosted large-v3 the backend serves, and it forced
/// an ffmpeg_kit dependency override to keep iOS simulator builds linking.
/// All transcription now goes to the cloud.
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

/// Persisted user preferences, backed by [SharedPreferences].
class SettingsService {
  static const _keyCloudLiveCaptions = 'cloud_live_captions_enabled';
  static const _keyCloudModel = 'cloud_model';

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

  /// Which cloud model handles transcription.
  /// Defaults to whichever is configured (preferring the saved choice), so a
  /// single-backend setup still resolves to a usable model.
  Future<CloudModel> getCloudModel() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_keyCloudModel);
    // Whisper is the default: the Qwen worker holds GPU device 0, which the
    // dedicated speaker embedding service now needs, so Qwen is expected to
    // be stopped in the current deployment. It stays selectable for setups
    // that still run it.
    final saved = CloudModel.values.firstWhere(
      (m) => m.name == raw,
      orElse: () => CloudModel.whisper,
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
