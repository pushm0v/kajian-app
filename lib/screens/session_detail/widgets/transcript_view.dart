import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/utils/formatters.dart';
import '../../../models/kajian_session.dart';
import '../../../widgets/app_toast.dart';

/// Shows the timestamped transcript. Live-captured segments are marked as
/// "live" until the cloud pass finalizes them.
class TranscriptView extends StatelessWidget {
  final KajianSession session;
  const TranscriptView({super.key, required this.session});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    if (session.status == SessionStatus.transcribing) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: 18),
            Text('Transcribing audio…', style: theme.textTheme.headlineSmall),
            const SizedBox(height: 6),
            Text(
              'Turning the recording into clean text.',
              style: theme.textTheme.bodyMedium
                  ?.copyWith(color: scheme.onSurfaceVariant),
            ),
          ],
        ),
      );
    }
    if (!session.hasTranscript) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Text(
            'No transcript available for this session.',
            textAlign: TextAlign.center,
            style: theme.textTheme.bodyLarge
                ?.copyWith(color: scheme.onSurfaceVariant),
          ),
        ),
      );
    }

    return Column(
      children: [
        Expanded(
          child: ListView.separated(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 88),
            itemCount: session.transcript.length,
            separatorBuilder: (_, __) => Divider(
              height: 24,
              color: scheme.outlineVariant.withValues(alpha: 0.6),
            ),
            itemBuilder: (context, i) {
              final seg = session.transcript[i];
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    margin: const EdgeInsets.only(top: 2),
                    padding: const EdgeInsets.symmetric(
                        horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: scheme.primaryContainer.withValues(alpha: 0.55),
                      borderRadius: BorderRadius.circular(7),
                    ),
                    child: Text(
                      Formatters.durationFromMs(seg.startMs),
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: scheme.primary,
                        fontWeight: FontWeight.w700,
                        fontFeatures: const [FontFeature.tabularFigures()],
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if (seg.speaker != null)
                          Text(seg.speaker!,
                              style: theme.textTheme.labelMedium?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  color: scheme.primary)),
                        Text(seg.text,
                            style: theme.textTheme.bodyLarge
                                ?.copyWith(height: 1.4)),
                        if (!seg.isFinal)
                          Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 7, vertical: 2),
                              decoration: BoxDecoration(
                                color: scheme.surfaceContainerHigh,
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Text('live',
                                  style: theme.textTheme.labelSmall?.copyWith(
                                      color: scheme.onSurfaceVariant,
                                      letterSpacing: 0.5)),
                            ),
                          ),
                      ],
                    ),
                  ),
                ],
              );
            },
          ),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 16),
            child: SizedBox(
              width: double.infinity,
              child: FilledButton.tonalIcon(
                onPressed: () {
                  Clipboard.setData(
                      ClipboardData(text: session.plainTranscript));
                  AppToast.success(context, 'Transcript copied');
                },
                icon: const Icon(Icons.copy_rounded, size: 18),
                label: const Text('Copy transcript'),
                style: FilledButton.styleFrom(
                  backgroundColor: scheme.surfaceContainerHigh,
                  foregroundColor: scheme.onSurface,
                  minimumSize: const Size(64, 50),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16)),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
