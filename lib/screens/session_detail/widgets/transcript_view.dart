import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/utils/formatters.dart';
import '../../../models/kajian_session.dart';

/// Shows the timestamped transcript. Live-captured segments are marked as
/// "live" until the cloud pass finalizes them.
class TranscriptView extends StatelessWidget {
  final KajianSession session;
  const TranscriptView({super.key, required this.session});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    if (session.status == SessionStatus.transcribing) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: const [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Transcribing audio…'),
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
            style: theme.textTheme.bodyMedium
                ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
        ),
      );
    }

    return Column(
      children: [
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 80),
            itemCount: session.transcript.length,
            itemBuilder: (context, i) {
              final seg = session.transcript[i];
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SizedBox(
                      width: 56,
                      child: Text(
                        Formatters.durationFromMs(seg.startMs),
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: theme.colorScheme.primary,
                          fontFeatures: const [FontFeature.tabularFigures()],
                        ),
                      ),
                    ),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (seg.speaker != null)
                            Text(seg.speaker!,
                                style: theme.textTheme.labelMedium?.copyWith(
                                    fontWeight: FontWeight.bold)),
                          Text(seg.text, style: theme.textTheme.bodyLarge),
                          if (!seg.isFinal)
                            Padding(
                              padding: const EdgeInsets.only(top: 2),
                              child: Text('live',
                                  style: theme.textTheme.labelSmall?.copyWith(
                                      color:
                                          theme.colorScheme.onSurfaceVariant)),
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () {
                      Clipboard.setData(
                          ClipboardData(text: session.plainTranscript));
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                            content: Text('Transcript copied')),
                      );
                    },
                    icon: const Icon(Icons.copy),
                    label: const Text('Copy transcript'),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
