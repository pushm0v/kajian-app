/// Central runtime configuration for the app.
///
/// SECURITY NOTE
/// -------------
/// Never embed a raw Anthropic / OpenAI API key inside a shipped mobile app —
/// anyone can extract it from the bundle. Instead, stand up a small backend
/// (Cloud Functions, a tiny Node/Go server, Supabase Edge Function, etc.) that
/// holds the secret keys and exposes two endpoints:
///
///   POST {backendBaseUrl}/transcribe   -> multipart audio in, transcript out
///   POST {backendBaseUrl}/summarize    -> transcript in, structured notes out
///
/// The app only talks to *your* backend. For local development you may point
/// these straight at the provider APIs using [devDirectProviderKey], but do NOT
/// ship that build.
///
/// Values can be overridden at build time with --dart-define, e.g.
///   flutter run --dart-define=BACKEND_BASE_URL=https://api.mykajianapp.com
class AppConfig {
  const AppConfig._();

  /// Your backend proxy base URL. Empty string => cloud features run in
  /// "mock mode" so the app is fully usable without any backend wired up yet.
  static const String backendBaseUrl =
      String.fromEnvironment('BACKEND_BASE_URL', defaultValue: '');

  /// DEV ONLY. If set, cloud services call the provider directly instead of
  /// the backend proxy. Do not use in production builds.
  static const String devDirectProviderKey =
      String.fromEnvironment('DEV_PROVIDER_KEY', defaultValue: '');

  /// Anthropic model used for AI note generation. See project docs for options
  /// (claude-opus-4-8 for max quality, claude-sonnet-5 for balanced cost).
  static const String aiNotesModel =
      String.fromEnvironment('AI_NOTES_MODEL', defaultValue: 'claude-sonnet-5');

  /// Whisper model for cloud transcription (via your backend).
  static const String cloudTranscriptionModel = 'whisper-1';

  /// True when no backend is configured. In this state the cloud transcription
  /// and AI-notes services return realistic mock data so the UI is testable.
  static bool get isMockMode =>
      backendBaseUrl.isEmpty && devDirectProviderKey.isEmpty;
}
