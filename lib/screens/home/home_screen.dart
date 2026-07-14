import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/constants/app_constants.dart';
import '../../models/kajian_session.dart';
import '../../providers/session_provider.dart';
import '../record/record_screen.dart';
import '../session_detail/session_detail_screen.dart';
import '../settings/settings_screen.dart';
import 'widgets/session_card.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(AppConstants.appName),
        titleTextStyle: Theme.of(context)
            .textTheme
            .headlineSmall
            ?.copyWith(fontWeight: FontWeight.bold),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            tooltip: 'Settings',
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const SettingsScreen()),
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _startRecording(context),
        icon: const Icon(Icons.mic),
        label: const Text('Record Kajian'),
      ),
      body: Consumer<SessionProvider>(
        builder: (context, provider, _) {
          if (provider.loading) {
            return const Center(child: CircularProgressIndicator());
          }
          if (provider.sessions.isEmpty) {
            return const _EmptyState();
          }
          return RefreshIndicator(
            onRefresh: provider.load,
            child: ListView.separated(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 96),
              itemCount: provider.sessions.length,
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemBuilder: (context, i) {
                final session = provider.sessions[i];
                return SessionCard(
                  session: session,
                  onTap: () => _openSession(context, session),
                  onDelete: () => _confirmDelete(context, provider, session),
                );
              },
            ),
          );
        },
      ),
    );
  }

  Future<void> _startRecording(BuildContext context) async {
    final session = await Navigator.of(context).push<KajianSession>(
      MaterialPageRoute(builder: (_) => const RecordScreen()),
    );
    if (session == null || !context.mounted) return;

    final provider = context.read<SessionProvider>();
    await provider.upsert(session);
    if (!context.mounted) return;
    _openSession(context, session, autoProcess: true);
  }

  void _openSession(
    BuildContext context,
    KajianSession session, {
    bool autoProcess = false,
  }) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => SessionDetailScreen(
          sessionId: session.id,
          autoProcess: autoProcess,
        ),
      ),
    );
  }

  Future<void> _confirmDelete(
    BuildContext context,
    SessionProvider provider,
    KajianSession session,
  ) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete kajian?'),
        content: Text(
            'This removes "${session.title}" and its recording permanently.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Delete')),
        ],
      ),
    );
    if (ok == true) await provider.delete(session.id);
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.menu_book_rounded,
                size: 72, color: theme.colorScheme.primary),
            const SizedBox(height: 16),
            Text('No kajian yet',
                style: theme.textTheme.titleLarge),
            const SizedBox(height: 8),
            Text(
              'Tap “Record Kajian” to capture a lecture. We’ll transcribe it and generate notes automatically.',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
          ],
        ),
      ),
    );
  }
}
