import 'package:flutter/material.dart';

import '../models/kajian_session.dart';

/// Small colored chip communicating a session's processing status.
class StatusChip extends StatelessWidget {
  final SessionStatus status;
  const StatusChip({super.key, required this.status});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final (Color bg, Color fg) = switch (status) {
      SessionStatus.completed => (
          scheme.primaryContainer,
          scheme.onPrimaryContainer
        ),
      SessionStatus.error => (scheme.errorContainer, scheme.onErrorContainer),
      _ => (scheme.surfaceContainerHighest, scheme.onSurfaceVariant),
    };

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (status.isBusy)
            SizedBox(
              width: 10,
              height: 10,
              child: CircularProgressIndicator(strokeWidth: 1.5, color: fg),
            ),
          if (status == SessionStatus.completed)
            Icon(Icons.check_circle, size: 12, color: fg),
          if (status.isBusy || status == SessionStatus.completed)
            const SizedBox(width: 5),
          Text(
            status.label,
            style: TextStyle(
                color: fg, fontSize: 11, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }
}
