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

  /// Bearer token sent to [backendBaseUrl] (as `Authorization: Bearer ...`
  /// for HTTP requests, or `?token=...` for the streaming WebSocket, which
  /// can't carry a bearer header on the handshake). Only needed if your
  /// backend enforces one (e.g. the reference backend's `ASR_API_TOKEN`);
  /// leave unset for LAN-only / trusted-network backends.
  static const String backendAuthToken =
      String.fromEnvironment('BACKEND_AUTH_TOKEN', defaultValue: '');

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

  static const String _qwenBaseUrlEnv =
      String.fromEnvironment('QWEN_BASE_URL', defaultValue: '');
  static const String _whisperBaseUrlEnv =
      String.fromEnvironment('WHISPER_BASE_URL', defaultValue: '');

  /// Base URL of the Qwen3-ASR backend (`backend/`). Falls back to
  /// [backendBaseUrl] when `QWEN_BASE_URL` isn't set, so single-backend
  /// setups keep working unchanged. Set both `QWEN_BASE_URL` and
  /// `WHISPER_BASE_URL` to let the user choose between the two in Settings.
  static String get qwenBaseUrl =>
      _qwenBaseUrlEnv.isNotEmpty ? _qwenBaseUrlEnv : backendBaseUrl;

  /// Base URL of the Whisper backend (`backend-whisper/`). Falls back to
  /// [backendBaseUrl] when `WHISPER_BASE_URL` isn't set.
  static String get whisperBaseUrl =>
      _whisperBaseUrlEnv.isNotEmpty ? _whisperBaseUrlEnv : backendBaseUrl;

  /// True when no backend is configured. In this state the cloud transcription
  /// and AI-notes services return realistic mock data so the UI is testable.
  static bool get isMockMode =>
      backendBaseUrl.isEmpty && devDirectProviderKey.isEmpty;

  /// WebSocket URL for live cloud transcription during recording
  /// (backend/app/streaming.py's `/transcribe/stream`). Derived from
  /// [backendBaseUrl] by swapping the http(s) scheme for ws(s) — same host,
  /// same backend, just the streaming endpoint instead of the batch one.
  /// Empty when [backendBaseUrl] is empty (mock mode / not configured).
  static String get cloudStreamingUrl => httpToWsUrl(backendBaseUrl);

  /// Swaps an http(s) URL's scheme for the matching ws(s) one. Pulled out as
  /// a pure function (rather than inlined in [cloudStreamingUrl]) so it's
  /// unit-testable without needing to override the compile-time
  /// [backendBaseUrl] constant.
  static String httpToWsUrl(String httpUrl) {
    if (httpUrl.isEmpty) return '';
    final uri = Uri.parse(httpUrl);
    final wsScheme = uri.scheme == 'https' ? 'wss' : 'ws';
    return uri.replace(scheme: wsScheme).toString();
  }
}
