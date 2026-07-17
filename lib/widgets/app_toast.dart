import 'package:flutter/material.dart';

/// A dark "pill" toast with a leading icon — matches the app's editorial style.
///
/// Uses the themed [SnackBarThemeData] (charcoal, stadium, floating) and adds a
/// coloured status icon. Prefer this over calling `ScaffoldMessenger` with a
/// raw [SnackBar] so toasts stay consistent across the app.
class AppToast {
  const AppToast._();

  static const Color _green = Color(0xFF34C759);
  static const Color _amber = Color(0xFFFFB020);

  static void show(
    BuildContext context,
    String message, {
    IconData icon = Icons.check_circle,
    Color iconColor = _green,
  }) {
    final messenger = ScaffoldMessenger.of(context);
    messenger.clearSnackBars();
    messenger.showSnackBar(
      SnackBar(
        duration: const Duration(seconds: 3),
        content: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: iconColor, size: 22),
            const SizedBox(width: 12),
            Flexible(child: Text(message)),
          ],
        ),
      ),
    );
  }

  /// Success toast (green check).
  static void success(BuildContext context, String message) =>
      show(context, message);

  /// Error toast (amber warning).
  static void error(BuildContext context, String message) => show(
        context,
        message,
        icon: Icons.error_outline,
        iconColor: _amber,
      );
}
