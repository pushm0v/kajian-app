import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/constants/app_constants.dart';
import '../../../core/theme/app_theme.dart';

/// Invites the user to help Kajian App keep running and growing. Framed as
/// a small act of ongoing charity (sadaqah jariyah) rather than a plain ask,
/// since every kajian saved here was made possible by someone's support.
class DonateCard extends StatelessWidget {
  const DonateCard({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 18),
      decoration: BoxDecoration(
        color: AppTheme.teal,
        borderRadius: BorderRadius.circular(22),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.volunteer_activism_rounded,
                  color: Colors.white, size: 20),
              const SizedBox(width: 8),
              Text(
                'Dukung Kajian App',
                style: theme.textTheme.titleMedium?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            '"Sebaik-baik manusia adalah yang paling bermanfaat bagi manusia lain." '
            'Setiap kajian yang tersimpan di sini semoga menjadi ilmu yang terus '
            'mengalir manfaatnya. Bantu kami merawat dan mengembangkan aplikasi '
            'ini agar lebih banyak kajian bisa dijaga dan disebarkan.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: Colors.white.withValues(alpha: 0.92),
              height: 1.45,
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: FilledButton.tonal(
              onPressed: () => _openDonateLink(context),
              style: FilledButton.styleFrom(
                backgroundColor: Colors.white,
                foregroundColor: AppTheme.teal,
              ),
              child: const Text('Bantu Kajian App Tumbuh'),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _openDonateLink(BuildContext context) async {
    final uri = Uri.parse(AppConstants.donateUrl);
    final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!opened && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Tidak dapat membuka tautan donasi.')),
      );
    }
  }
}
