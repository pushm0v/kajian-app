import 'package:flutter/material.dart';

/// Warm, editorial theme: cream/butter surfaces, an elegant serif for
/// headlines, teal/green brand accents, softly-rounded cards and dark "pill"
/// toasts. Body text stays in the platform sans for readability.
class AppTheme {
  const AppTheme._();

  // ── Brand palette ─────────────────────────────────────────────────────
  static const Color teal = Color(0xFF0C8074); // primary accent (icon mid-tone)
  static const Color tealDark = Color(0xFF075E55);
  static const Color tealSoft = Color(0xFFCDE9E2);

  // Warm light surfaces
  static const Color cream = Color(0xFFFBF6E7); // scaffold
  static const Color creamCard = Color(0xFFFFFDF6); // cards / rows
  static const Color creamSunk = Color(0xFFF2EBD6); // sunken fills
  static const Color ink = Color(0xFF221E17); // primary text
  static const Color inkSoft = Color(0xFF6E675A); // secondary text
  static const Color line = Color(0xFFE7DFC9); // hairlines / outlines
  static const Color charcoal = Color(0xFF2A2723); // dark elements / toast

  // Warm dark surfaces
  static const Color darkBg = Color(0xFF16130E);
  static const Color darkCard = Color(0xFF211D17);
  static const Color darkInk = Color(0xFFF2EBD8);
  static const Color darkInkSoft = Color(0xFFB4AC99);
  static const Color darkLine = Color(0xFF34301F);

  static const String serif = 'PlayfairDisplay';

  static ThemeData get light => _build(Brightness.light);
  static ThemeData get dark => _build(Brightness.dark);

  static ThemeData _build(Brightness brightness) {
    final isLight = brightness == Brightness.light;

    final scheme = ColorScheme.fromSeed(
      seedColor: teal,
      brightness: brightness,
    ).copyWith(
      primary: isLight ? teal : const Color(0xFF5CD6C2),
      onPrimary: isLight ? Colors.white : const Color(0xFF00382F),
      primaryContainer: isLight ? tealSoft : tealDark,
      onPrimaryContainer: isLight ? const Color(0xFF04302A) : tealSoft,
      surface: isLight ? cream : darkBg,
      onSurface: isLight ? ink : darkInk,
      onSurfaceVariant: isLight ? inkSoft : darkInkSoft,
      surfaceContainerLowest: isLight ? Colors.white : const Color(0xFF120F0B),
      surfaceContainerLow: isLight ? creamCard : darkCard,
      surfaceContainer: isLight ? const Color(0xFFF6F0DE) : darkCard,
      surfaceContainerHigh: isLight ? creamSunk : const Color(0xFF272219),
      surfaceContainerHighest: isLight ? creamSunk : const Color(0xFF2E2820),
      outline: isLight ? const Color(0xFFCFC6AC) : const Color(0xFF4A4534),
      outlineVariant: isLight ? line : darkLine,
    );

    final ink0 = isLight ? ink : darkInk;
    final baseText =
        isLight ? Typography.material2021().black : Typography.material2021().white;
    final textTheme = baseText.copyWith(
      displayLarge: baseText.displayLarge?.copyWith(
          fontFamily: serif, fontWeight: FontWeight.w700, height: 1.04,
          letterSpacing: -0.5),
      displayMedium: baseText.displayMedium?.copyWith(
          fontFamily: serif, fontWeight: FontWeight.w700, height: 1.05,
          letterSpacing: -0.5),
      displaySmall: baseText.displaySmall?.copyWith(
          fontFamily: serif, fontWeight: FontWeight.w600, height: 1.08),
      headlineLarge: baseText.headlineLarge?.copyWith(
          fontFamily: serif, fontWeight: FontWeight.w700, height: 1.1,
          letterSpacing: -0.3),
      headlineMedium: baseText.headlineMedium?.copyWith(
          fontFamily: serif, fontWeight: FontWeight.w600, height: 1.12),
      headlineSmall: baseText.headlineSmall?.copyWith(
          fontFamily: serif, fontWeight: FontWeight.w600, height: 1.15),
    ).apply(bodyColor: ink0, displayColor: ink0);

    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      brightness: brightness,
      scaffoldBackgroundColor: scheme.surface,
      textTheme: textTheme,
      splashFactory: InkSparkle.splashFactory,
      appBarTheme: AppBarTheme(
        centerTitle: false,
        backgroundColor: scheme.surface,
        surfaceTintColor: Colors.transparent,
        foregroundColor: scheme.onSurface,
        elevation: 0,
        scrolledUnderElevation: 0,
        titleTextStyle: textTheme.headlineSmall?.copyWith(fontSize: 22),
      ),
      cardTheme: CardThemeData(
        elevation: 4,
        color: scheme.surfaceContainerLow,
        surfaceTintColor: Colors.transparent,
        shadowColor: (isLight ? ink : Colors.black).withValues(alpha: 0.10),
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(22),
        ),
        clipBehavior: Clip.antiAlias,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: teal,
          foregroundColor: Colors.white,
          minimumSize: const Size(64, 52),
          textStyle: const TextStyle(
              fontSize: 15, fontWeight: FontWeight.w600, letterSpacing: 0.1),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: scheme.onSurface,
          minimumSize: const Size(64, 52),
          side: BorderSide(color: scheme.outline),
          textStyle:
              const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(foregroundColor: teal),
      ),
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: teal,
        foregroundColor: Colors.white,
        elevation: 4,
        highlightElevation: 6,
        extendedTextStyle:
            const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
        shape: const StadiumBorder(),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: scheme.surfaceContainerHigh,
        side: BorderSide.none,
        labelStyle: TextStyle(
            color: scheme.onSurface,
            fontWeight: FontWeight.w600,
            fontSize: 12.5),
        shape:
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(30)),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surfaceContainerHigh,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: teal, width: 1.5),
        ),
      ),
      dividerTheme: DividerThemeData(
        color: scheme.outlineVariant,
        thickness: 1,
        space: 1,
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: isLight ? charcoal : const Color(0xFF3A352C),
        contentTextStyle: const TextStyle(
            color: Color(0xFFF6F1E3),
            fontSize: 14.5,
            fontWeight: FontWeight.w500),
        actionTextColor: const Color(0xFF7FE0CE),
        elevation: 8,
        insetPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        shape: const StadiumBorder(),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: scheme.surfaceContainerLow,
        surfaceTintColor: Colors.transparent,
        shape:
            RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
        titleTextStyle: textTheme.headlineSmall?.copyWith(fontSize: 20),
      ),
      listTileTheme: const ListTileThemeData(iconColor: teal),
    );
  }
}
