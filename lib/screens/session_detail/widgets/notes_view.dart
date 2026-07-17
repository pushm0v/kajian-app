import 'package:flutter/material.dart';

import '../../../models/kajian_note.dart';
import '../../../models/kajian_session.dart';

/// Renders the structured AI notes for a session.
class NotesView extends StatelessWidget {
  final KajianSession session;
  final VoidCallback onGenerate;

  const NotesView({
    super.key,
    required this.session,
    required this.onGenerate,
  });

  @override
  Widget build(BuildContext context) {
    if (session.status.isBusy) {
      return _busy(context);
    }
    final note = session.note;
    if (note == null) {
      return _empty(context);
    }
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
      children: [
        if (note.summary.isNotEmpty) ...[
          _SummaryCard(text: note.summary),
          const SizedBox(height: 24),
        ],
        if (note.topics.isNotEmpty)
          _Section(
            title: 'Topics',
            icon: Icons.sell_outlined,
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final t in note.topics) Chip(label: Text(t)),
              ],
            ),
          ),
        if (note.keyPoints.isNotEmpty)
          _Section(
            title: 'Key Points',
            icon: Icons.format_list_bulleted,
            child: _Bullets(items: note.keyPoints),
          ),
        if (note.references.isNotEmpty)
          _Section(
            title: 'References',
            icon: Icons.menu_book,
            child: Column(
              children: [for (final r in note.references) _ReferenceTile(r)],
            ),
          ),
        if (note.actionItems.isNotEmpty)
          _Section(
            title: 'Action Items',
            icon: Icons.check_circle_outline,
            child: _Bullets(items: note.actionItems, checkboxes: true),
          ),
        const SizedBox(height: 8),
        Center(
          child: Text(
            'Notes generated ${note.generatedAt.toLocal()}'.split('.').first,
            style: theme.textTheme.bodySmall
                ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
        ),
      ],
    );
  }

  Widget _busy(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CircularProgressIndicator(),
          const SizedBox(height: 16),
          Text(session.status.label),
        ],
      ),
    );
  }

  Widget _empty(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.auto_awesome,
                size: 56, color: theme.colorScheme.primary),
            const SizedBox(height: 16),
            Text('No notes yet', style: theme.textTheme.headlineSmall),
            const SizedBox(height: 8),
            Text(
              'Generate AI notes from the transcript: a summary, key points, and Quran/Hadith references.',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: onGenerate,
              icon: const Icon(Icons.auto_awesome),
              label: const Text('Generate notes'),
            ),
          ],
        ),
      ),
    );
  }
}

/// Highlighted teal-tinted card for the AI summary — the hero of the notes.
class _SummaryCard extends StatelessWidget {
  final String text;
  const _SummaryCard({required this.text});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: scheme.primaryContainer.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: scheme.primary.withValues(alpha: 0.18)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.auto_awesome, size: 16, color: scheme.primary),
              const SizedBox(width: 8),
              Text(
                'SUMMARY',
                style: theme.textTheme.labelMedium?.copyWith(
                  color: scheme.primary,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 1.2,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            text,
            style: theme.textTheme.titleMedium?.copyWith(
              height: 1.45,
              fontWeight: FontWeight.w400,
              color: scheme.onSurface,
            ),
          ),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  final String title;
  final IconData icon;
  final Widget child;
  const _Section({
    required this.title,
    required this.icon,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 30,
                height: 30,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: scheme.surfaceContainerHigh,
                  borderRadius: BorderRadius.circular(9),
                ),
                child: Icon(icon, size: 17, color: scheme.primary),
              ),
              const SizedBox(width: 10),
              Text(
                title,
                style: const TextStyle(
                  fontFamily: 'PlayfairDisplay',
                  fontWeight: FontWeight.w600,
                  fontSize: 19,
                ).copyWith(color: scheme.onSurface),
              ),
            ],
          ),
          const SizedBox(height: 12),
          child,
        ],
      ),
    );
  }
}

class _Bullets extends StatelessWidget {
  final List<String> items;
  final bool checkboxes;
  const _Bullets({required this.items, this.checkboxes = false});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final item in items)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  checkboxes
                      ? Icons.check_box_outline_blank
                      : Icons.circle,
                  size: checkboxes ? 20 : 7,
                  color: theme.colorScheme.primary,
                ),
                const SizedBox(width: 10),
                Expanded(
                    child:
                        Text(item, style: theme.textTheme.bodyLarge)),
              ],
            ),
          ),
      ],
    );
  }
}

class _ReferenceTile extends StatelessWidget {
  final ScriptureReference reference;
  const _ReferenceTile(this.reference);

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isQuran = reference.type == 'quran';
    final scheme = theme.colorScheme;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: scheme.outlineVariant),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 34,
            height: 34,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: scheme.primaryContainer.withValues(alpha: 0.6),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(isQuran ? Icons.menu_book : Icons.format_quote,
                size: 18, color: scheme.primary),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(reference.citation,
                    style: theme.textTheme.titleSmall
                        ?.copyWith(fontWeight: FontWeight.w600)),
                if (reference.note != null && reference.note!.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(reference.note!,
                        style: theme.textTheme.bodyMedium),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
