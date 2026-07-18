/// App-wide constants.
class AppConstants {
  const AppConstants._();

  static const String appName = 'Kajian App';

  /// Storage keys.
  static const String sessionsStorageFile = 'kajian_sessions.json';
  static const String prefsOnboardingDone = 'onboarding_done';
  static const String prefsPreferredLocale = 'preferred_locale';
  static const String prefsWisdomIndex = 'wisdom_index';

  /// Supported transcription locales. Kajian is commonly delivered in
  /// Indonesian with embedded Arabic quotations, so both are offered.
  static const List<LocaleOption> supportedLocales = [
    LocaleOption('id_ID', 'Bahasa Indonesia'),
    LocaleOption('ar_SA', 'العربية (Arabic)'),
    LocaleOption('en_US', 'English'),
    LocaleOption('ms_MY', 'Bahasa Melayu'),
  ];

  static const String defaultLocaleId = 'id_ID';

  /// Where "Dukung Kajian App" points to.
  static const String donateUrl = 'https://kawanbantu.com/kajianapp';
}

class LocaleOption {
  final String id;
  final String label;
  const LocaleOption(this.id, this.label);
}
