/// App-wide constants.
class AppConstants {
  const AppConstants._();

  static const String appName = 'Kajian Notes';

  /// Storage keys.
  static const String sessionsStorageFile = 'kajian_sessions.json';
  static const String prefsOnboardingDone = 'onboarding_done';
  static const String prefsPreferredLocale = 'preferred_locale';

  /// Supported transcription locales. Kajian is commonly delivered in
  /// Indonesian with embedded Arabic quotations, so both are offered.
  static const List<LocaleOption> supportedLocales = [
    LocaleOption('id_ID', 'Bahasa Indonesia'),
    LocaleOption('ar_SA', 'العربية (Arabic)'),
    LocaleOption('en_US', 'English'),
    LocaleOption('ms_MY', 'Bahasa Melayu'),
  ];

  static const String defaultLocaleId = 'id_ID';
}

class LocaleOption {
  final String id;
  final String label;
  const LocaleOption(this.id, this.label);
}
