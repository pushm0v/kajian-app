import 'package:intl/intl.dart';

/// Small formatting helpers used across the UI.
class Formatters {
  const Formatters._();

  /// e.g. 01:23:45 or 04:07 for durations.
  static String duration(Duration d) {
    final h = d.inHours;
    final m = d.inMinutes.remainder(60);
    final s = d.inSeconds.remainder(60);
    two(int n) => n.toString().padLeft(2, '0');
    return h > 0 ? '${two(h)}:${two(m)}:${two(s)}' : '${two(m)}:${two(s)}';
  }

  static String durationFromMs(int ms) =>
      duration(Duration(milliseconds: ms));

  /// e.g. "12 Jul 2026 · 19:30".
  static String sessionDate(DateTime dt) =>
      DateFormat("d MMM yyyy · HH:mm").format(dt);

  /// e.g. "Today", "Yesterday", or "12 Jul".
  static String relativeDay(DateTime dt) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final that = DateTime(dt.year, dt.month, dt.day);
    final diff = today.difference(that).inDays;
    if (diff == 0) return 'Today';
    if (diff == 1) return 'Yesterday';
    if (diff < 7) return DateFormat('EEEE').format(dt);
    return DateFormat('d MMM').format(dt);
  }
}
