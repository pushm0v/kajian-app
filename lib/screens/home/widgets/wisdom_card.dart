import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';
import '../../../models/daily_wisdom.dart';

/// A small card on the homepage that rotates through a short list of Quran
/// verses and hadiths (Arabic + Indonesian meaning), so there's always a
/// moment of reflection alongside the kajian list.
class WisdomCard extends StatefulWidget {
  const WisdomCard({super.key});

  @override
  State<WisdomCard> createState() => _WisdomCardState();
}

class _WisdomCardState extends State<WisdomCard> {
  late int _index = Random().nextInt(kDailyWisdoms.length);
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(seconds: 12), (_) {
      setState(() => _index = (_index + 1) % kDailyWisdoms.length);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final wisdom = kDailyWisdoms[_index];
    final isQuran = wisdom.type == 'quran';

    return Container(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 20),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: theme.colorScheme.outlineVariant),
      ),
      child: AnimatedSwitcher(
        duration: const Duration(milliseconds: 450),
        child: Column(
          key: ValueKey(_index),
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
      ),
    );
  }
}
