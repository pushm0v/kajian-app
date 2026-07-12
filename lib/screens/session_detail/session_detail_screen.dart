import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/utils/formatters.dart';
import '../../models/kajian_session.dart';
import '../../providers/session_provider.dart';
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
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Processing failed: $e')),
    );
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
              bottom: const TabBar(
                tabs: [
                  Tab(text: 'Notes', icon: Icon(Icons.notes)),
                  Tab(text: 'Transcript', icon: Icon(Icons.subject)),
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
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
      child: Row(
        children: [
          Icon(Icons.event, size: 16, color: theme.colorScheme.onSurfaceVariant),
          const SizedBox(width: 6),
          Text(Formatters.sessionDate(session.createdAt),
              style: theme.textTheme.bodySmall),
          const SizedBox(width: 12),
          Icon(Icons.schedule,
              size: 16, color: theme.colorScheme.onSurfaceVariant),
          const SizedBox(width: 6),
          Text(Formatters.durationFromMs(session.durationMs),
              style: theme.textTheme.bodySmall),
          const Spacer(),
          StatusChip(status: session.status),
        ],
      ),
    );
  }
}
