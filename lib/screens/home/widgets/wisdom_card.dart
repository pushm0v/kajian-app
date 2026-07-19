import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/constants/app_constants.dart';
import '../../../core/theme/app_theme.dart';
import '../../../models/daily_wisdom.dart';

/// A small card on the homepage showing a Quran verse or hadith (Arabic +
/// Indonesian meaning). Advances to the next entry each time the homepage
/// is visited (persisted across app launches), rather than on a timer, so
/// it reads as a fresh reminder every time rather than something ticking
/// away while you're looking at it.
class WisdomCard extends StatefulWidget {
  const WisdomCard({super.key});

  @override
  State<WisdomCard> createState() => _WisdomCardState();
}

class _WisdomCardState extends State<WisdomCard> {
  int? _index;

  @override
  void initState() {
    super.initState();
    _advance();
  }

  Future<void> _advance() async {
    final prefs = await SharedPreferences.getInstance();
    final last = prefs.getInt(AppConstants.prefsWisdomIndex) ?? -1;
    final next = (last + 1) % kDailyWisdoms.length;
    await prefs.setInt(AppConstants.prefsWisdomIndex, next);
    if (mounted) setState(() => _index = next);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final index = _index;
    if (index == null) return const SizedBox.shrink();

    final wisdom = kDailyWisdoms[index];
    final isQuran = wisdom.type == 'quran';

    return Container(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 20),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                isQuran ? Icons.menu_book_rounded : Icons.mosque_rounded,
                size: 16,
                color: AppTheme.teal,
              ),
              const SizedBox(width: 6),
              Text(
                isQuran ? 'AYAT PILIHAN' : 'HADITS PILIHAN',
                style: theme.textTheme.labelMedium?.copyWith(
                  color: AppTheme.teal,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 1.2,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Text(
            wisdom.arabic,
            textAlign: TextAlign.right,
            textDirection: TextDirection.rtl,
            style: theme.textTheme.headlineSmall?.copyWith(
              fontFamily: null, // platform Arabic-capable font, not the serif
              fontWeight: FontWeight.w600,
              height: 1.7,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            wisdom.meaningId,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            wisdom.source,
            style: theme.textTheme.labelMedium?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
