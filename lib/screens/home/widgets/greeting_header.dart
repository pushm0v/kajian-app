import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../providers/auth_provider.dart';

/// Warm "Ahlan wa Sahlan" welcome shown at the top of the homepage, with the
/// signed-in user's first name when available.
class GreetingHeader extends StatelessWidget {
  const GreetingHeader({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final displayName = context.watch<AuthProvider>().user?.displayName;
    final firstName = (displayName == null || displayName.trim().isEmpty)
        ? null
        : displayName.trim().split(' ').first;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          firstName == null ? 'Ahlan wa Sahlan!' : 'Ahlan wa Sahlan, $firstName!',
          style: theme.textTheme.headlineSmall,
        ),
        const SizedBox(height: 4),
        Text(
          'Selamat datang kembali. Yuk, catat kajian hari ini.',
          style: theme.textTheme.bodyMedium
              ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
        ),
      ],
    );
  }
}
