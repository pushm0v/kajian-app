import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/constants/app_constants.dart';
import '../../core/utils/formatters.dart';
import '../../models/kajian_session.dart';
import '../../providers/session_provider.dart';
import '../record/record_screen.dart';
import '../session_detail/session_detail_screen.dart';
import '../settings/settings_screen.dart';
import 'widgets/donate_card.dart';
import 'widgets/greeting_header.dart';
import 'widgets/session_card.dart';
import 'widgets/wisdom_card.dart';

/// How many kajian sessions are shown per "page"; tapping "Show more"
/// reveals another batch of this size.
const int _pageSize = 5;

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _visibleCount = _pageSize;

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
          final sessions = provider.sessions;
          final visible = sessions.take(_visibleCount).toList();
          final hasMore = sessions.length > visible.length;

          return RefreshIndicator(
            onRefresh: () async {
              setState(() => _visibleCount = _pageSize);
              await provider.load();
            },
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 96),
              children: [
                const GreetingHeader(),
                const SizedBox(height: 20),
                const WisdomCard(),
                const SizedBox(height: 16),
                const DonateCard(),
                const SizedBox(height: 8),
                if (sessions.isEmpty)
                  const _EmptyState()
                else ...[
                  const SizedBox(height: 20),
                  ..._buildSectioned(context, provider, visible),
                  if (hasMore)
                    Padding(
                      padding: const EdgeInsets.only(top: 4, bottom: 8),
                      child: OutlinedButton(
                        onPressed: () => setState(
                            () => _visibleCount += _pageSize),
                        child: Text(
                          'Show 5 more (${sessions.length - visible.length} left)',
                        ),
                      ),
                    ),
                ],
              ],
            ),
          );
        },
      ),
    );
  }

  /// Groups the visible slice into "Today / Yesterday / This Week / Earlier"
  /// sections (in that order) so older notes read as clearly older, with a
  /// header only where the bucket changes.
  List<Widget> _buildSectioned(
    BuildContext context,
    SessionProvider provider,
    List<KajianSession> visible,
  ) {
    final widgets = <Widget>[];
    String? lastBucket;
    for (final session in visible) {
      final bucket = Formatters.dateBucket(session.createdAt);
      if (bucket != lastBucket) {
        if (lastBucket != null) widgets.add(const SizedBox(height: 8));
        widgets.add(_SectionHeader(label: bucket));
        lastBucket = bucket;
      }
      widgets.add(SessionCard(
        session: session,
        onTap: () => _openSession(context, session),
        onDelete: () => _confirmDelete(context, provider, session),
      ));
      widgets.add(const SizedBox(height: 12));
    }
    return widgets;
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

/// A small, sticky-feeling label ("Today", "This Week", "Earlier"...) that
/// visually separates the kajian list into recognizable time buckets.
class _SectionHeader extends StatelessWidget {
  final String label;
  const _SectionHeader({required this.label});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 8, 4, 10),
      child: Text(
        label.toUpperCase(),
        style: theme.textTheme.labelMedium?.copyWith(
          color: theme.colorScheme.onSurfaceVariant,
          fontWeight: FontWeight.w700,
          letterSpacing: 1.2,
        ),
      ),
    );
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
