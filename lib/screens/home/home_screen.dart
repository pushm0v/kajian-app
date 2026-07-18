import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/constants/app_constants.dart';
import '../../models/kajian_session.dart';
import '../../providers/session_provider.dart';
import '../record/record_screen.dart';
import '../session_detail/session_detail_screen.dart';
import '../settings/settings_screen.dart';
import 'widgets/donate_card.dart';
import 'widgets/greeting_header.dart';
import 'widgets/session_card.dart';
import 'widgets/wisdom_card.dart';

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
          return RefreshIndicator(
            onRefresh: provider.load,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 96),
              children: [
                const GreetingHeader(),
                const SizedBox(height: 20),
                const WisdomCard(),
                const SizedBox(height: 16),
                const DonateCard(),
                const SizedBox(height: 8),
                if (provider.sessions.isEmpty)
                  const _EmptyState()
                else ...[
                  const SizedBox(height: 20),
                  for (final session in provider.sessions) ...[
                    SessionCard(
                      session: session,
                      onTap: () => _openSession(context, session),
                      onDelete: () =>
                          _confirmDelete(context, provider, session),
                    ),
                    const SizedBox(height: 12),
                  ],
                ],
              ],
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
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 32, 20, 40),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 96,
            height: 96,
            decoration: BoxDecoration(
              color: theme.colorScheme.surfaceContainerHigh,
              shape: BoxShape.circle,
            ),
            child: Icon(Icons.auto_stories_rounded,
                size: 46, color: theme.colorScheme.primary),
          ),
          const SizedBox(height: 24),
          Text('Your kajian journal\nstarts here',
              textAlign: TextAlign.center,
              style: theme.textTheme.headlineMedium),
          const SizedBox(height: 12),
          Text(
            'Tap Record Kajian to capture a lecture. We’ll transcribe it and write up the notes for you.',
            textAlign: TextAlign.center,
            style: theme.textTheme.bodyLarge
                ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
        ],
      ),
    );
  }
}
