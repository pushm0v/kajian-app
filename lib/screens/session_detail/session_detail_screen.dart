import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/utils/formatters.dart';
import '../../models/kajian_session.dart';
import '../../providers/session_provider.dart';
import '../../widgets/app_toast.dart';
import '../../widgets/status_chip.dart';
import 'widgets/notes_view.dart';
import 'widgets/transcript_view.dart';

/// Detail view for one kajian: AI notes + transcript, with the ability to
/// (re)run the processing pipeline.
class SessionDetailScreen extends StatefulWidget {
  final String sessionId;

  /// When true, automatically kicks off transcription + notes on open
  /// (used right after a recording is saved).
  final bool autoProcess;

  const SessionDetailScreen({
    super.key,
    required this.sessionId,
    this.autoProcess = false,
  });

  @override
  State<SessionDetailScreen> createState() => _SessionDetailScreenState();
}

class _SessionDetailScreenState extends State<SessionDetailScreen> {
  bool _kicked = false;

  @override
  void initState() {
    super.initState();
    if (widget.autoProcess) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _process());
    }
  }

  Future<void> _process() async {
    if (_kicked) return;
    _kicked = true;
    try {
      await context.read<SessionProvider>().process(widget.sessionId);
    } catch (e) {
      if (mounted) _showError(e);
    }
  }

  Future<void> _regenerate() async {
    try {
      await context.read<SessionProvider>().regenerateNotes(widget.sessionId);
    } catch (e) {
      if (mounted) _showError(e);
    }
  }

  void _showError(Object e) {
    AppToast.error(context, 'Processing failed: $e');
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<SessionProvider>(
      builder: (context, provider, _) {
        final session = provider.byId(widget.sessionId);
        if (session == null) {
          return const Scaffold(
            body: Center(child: Text('Session not found')),
          );
        }
        return DefaultTabController(
          length: 2,
          child: Scaffold(
            appBar: AppBar(
              title: Text(session.title, overflow: TextOverflow.ellipsis),
              actions: [
                if (session.status == SessionStatus.error ||
                    (!session.hasNotes && !session.status.isBusy))
                  IconButton(
                    tooltip: 'Process',
                    icon: const Icon(Icons.auto_awesome),
                    onPressed: _process,
                  ),
                if (session.hasNotes)
                  IconButton(
                    tooltip: 'Regenerate notes',
                    icon: const Icon(Icons.refresh),
                    onPressed:
                        session.status.isBusy ? null : _regenerate,
                  ),
              ],
              bottom: TabBar(
                labelColor: Theme.of(context).colorScheme.primary,
                unselectedLabelColor:
                    Theme.of(context).colorScheme.onSurfaceVariant,
                indicatorColor: Theme.of(context).colorScheme.primary,
                indicatorSize: TabBarIndicatorSize.label,
                indicatorWeight: 2.5,
                labelStyle: const TextStyle(
                    fontWeight: FontWeight.w700, fontSize: 13.5),
                unselectedLabelStyle:
                    const TextStyle(fontWeight: FontWeight.w600, fontSize: 13.5),
                dividerColor: Theme.of(context).colorScheme.outlineVariant,
                tabs: const [
                  Tab(text: 'Notes', icon: Icon(Icons.notes_rounded, size: 20)),
                  Tab(
                      text: 'Transcript',
                      icon: Icon(Icons.subject_rounded, size: 20)),
                ],
              ),
            ),
            body: Column(
              children: [
                _Header(session: session),
                Expanded(
                  child: TabBarView(
                    children: [
                      NotesView(session: session, onGenerate: _process),
                      TranscriptView(session: session),
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _Header extends StatelessWidget {
  final KajianSession session;
  const _Header({required this.session});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final subtitle = [session.speaker, session.location]
        .where((e) => e != null && e!.isNotEmpty)
        .join(' · ');
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _meta(theme, Icons.event_rounded,
                  Formatters.sessionDate(session.createdAt)),
              const SizedBox(width: 14),
              _meta(theme, Icons.schedule_rounded,
                  Formatters.durationFromMs(session.durationMs)),
              const Spacer(),
              StatusChip(status: session.status),
            ],
          ),
          if (subtitle.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Row(
                children: [
                  Icon(Icons.person_outline_rounded,
                      size: 15, color: scheme.onSurfaceVariant),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(subtitle,
                        style: theme.textTheme.bodySmall
                            ?.copyWith(color: scheme.onSurfaceVariant),
                        overflow: TextOverflow.ellipsis),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _meta(ThemeData theme, IconData icon, String text) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 15, color: theme.colorScheme.onSurfaceVariant),
        const SizedBox(width: 6),
        Text(text, style: theme.textTheme.bodySmall),
      ],
    );
  }
}
