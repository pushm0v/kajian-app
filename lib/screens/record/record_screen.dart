import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/constants/app_constants.dart';
import '../../core/utils/formatters.dart';
import '../../providers/recording_controller.dart';
import 'widgets/waveform_bar.dart';

/// Live recording screen. Owns its own [RecordingController] for the session's
/// lifetime and pops a recorded [KajianSession] back to the caller on save.
class RecordScreen extends StatelessWidget {
  const RecordScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => RecordingController(),
      child: const _RecordView(),
    );
  }
}

class _RecordView extends StatefulWidget {
  const _RecordView();

  @override
  State<_RecordView> createState() => _RecordViewState();
}

class _RecordViewState extends State<_RecordView> {
  String _localeId = AppConstants.defaultLocaleId;
  bool _ready = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _prepare());
  }

  Future<void> _prepare() async {
    final controller = context.read<RecordingController>();
    final ok = await controller.ensureReady();
    if (!mounted) return;
    setState(() {
      _ready = ok;
      _error = ok ? null : 'Microphone permission is required to record.';
    });
  }

  @override
  Widget build(BuildContext context) {
    final controller = context.watch<RecordingController>();
    final theme = Theme.of(context);

    return PopScope(
      canPop: !controller.isActive,
      onPopInvokedWithResult: (didPop, _) async {
        if (!didPop && controller.isActive) {
          final leave = await _confirmDiscard();
          if (leave == true && mounted) {
            await controller.cancel();
            if (mounted) Navigator.of(context).pop();
          }
        }
      },
      child: Scaffold(
        appBar: AppBar(title: const Text('Record Kajian')),
        body: SafeArea(
          child: Column(
            children: [
              _LocaleSelector(
                value: _localeId,
                enabled: !controller.isActive,
                onChanged: (v) => setState(() => _localeId = v),
              ),
              Expanded(child: _captions(controller, theme)),
              _timerAndWave(controller, theme),
              const SizedBox(height: 8),
              _controls(controller),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }

  Widget _captions(RecordingController c, ThemeData theme) {
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(_error!,
              textAlign: TextAlign.center,
              style: TextStyle(color: theme.colorScheme.error)),
        ),
      );
    }
    if (c.segments.isEmpty && c.interimText.isEmpty) {
      return Center(
        child: Text(
          c.state == RecordingState.idle
              ? 'Press record to begin. Live captions appear here.'
              : 'Listening…',
          style: theme.textTheme.bodyLarge
              ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
        ),
      );
    }
    return ListView(
      reverse: true,
      padding: const EdgeInsets.all(16),
      children: [
        if (c.interimText.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(c.interimText,
                style: theme.textTheme.bodyLarge?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                    fontStyle: FontStyle.italic)),
          ),
        for (final seg in c.segments.reversed)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 6),
            child: Text(seg.text, style: theme.textTheme.bodyLarge),
          ),
      ],
    );
  }

  Widget _timerAndWave(RecordingController c, ThemeData theme) {
    return Column(
      children: [
        Text(
          Formatters.duration(c.elapsed),
          style: theme.textTheme.displaySmall?.copyWith(
            fontFeatures: const [FontFeature.tabularFigures()],
            fontWeight: FontWeight.w300,
          ),
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: 48,
          child: WaveformBar(
            amplitude: c.amplitude,
            active: c.state == RecordingState.recording,
          ),
        ),
      ],
    );
  }

  Widget _controls(RecordingController c) {
    switch (c.state) {
      case RecordingState.idle:
        return _bigButton(
          icon: Icons.mic,
          label: 'Record',
          color: Theme.of(context).colorScheme.primary,
          onTap: _ready ? () => c.start(localeId: _localeId) : null,
        );
      case RecordingState.finishing:
        return const CircularProgressIndicator();
      case RecordingState.recording:
      case RecordingState.paused:
        final paused = c.state == RecordingState.paused;
        return Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _circleButton(
              icon: paused ? Icons.play_arrow : Icons.pause,
              onTap: () => paused ? c.resume() : c.pause(),
            ),
            const SizedBox(width: 32),
            _bigButton(
              icon: Icons.stop,
              label: 'Finish',
              color: Theme.of(context).colorScheme.error,
              onTap: _finish,
            ),
          ],
        );
    }
  }

  Widget _bigButton({
    required IconData icon,
    required String label,
    required Color color,
    VoidCallback? onTap,
  }) {
    return FilledButton.icon(
      onPressed: onTap,
      icon: Icon(icon),
      label: Text(label),
      style: FilledButton.styleFrom(
        backgroundColor: color,
        padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
      ),
    );
  }

  Widget _circleButton({required IconData icon, required VoidCallback onTap}) {
    return IconButton.filledTonal(
      onPressed: onTap,
      iconSize: 28,
      padding: const EdgeInsets.all(16),
      icon: Icon(icon),
    );
  }

  Future<void> _finish() async {
    final controller = context.read<RecordingController>();
    final meta = await _askMetadata();
    if (meta == null || !mounted) return;
    final session = await controller.stop(
      title: meta.title,
      speaker: meta.speaker,
      location: meta.location,
    );
    if (mounted) Navigator.of(context).pop(session);
  }

  Future<_SessionMeta?> _askMetadata() {
    final titleC = TextEditingController(
        text: 'Kajian ${Formatters.relativeDay(DateTime.now())}');
    final speakerC = TextEditingController();
    final locationC = TextEditingController();
    return showDialog<_SessionMeta>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Save kajian'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: titleC,
                decoration: const InputDecoration(labelText: 'Title'),
                textCapitalization: TextCapitalization.sentences,
              ),
              const SizedBox(height: 12),
              TextField(
                controller: speakerC,
                decoration:
                    const InputDecoration(labelText: 'Ustadz / Speaker'),
                textCapitalization: TextCapitalization.words,
              ),
              const SizedBox(height: 12),
              TextField(
                controller: locationC,
                decoration:
                    const InputDecoration(labelText: 'Masjid / Location'),
                textCapitalization: TextCapitalization.words,
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel')),
          FilledButton(
            onPressed: () => Navigator.pop(
              ctx,
              _SessionMeta(
                title: titleC.text,
                speaker: speakerC.text.trim().isEmpty
                    ? null
                    : speakerC.text.trim(),
                location: locationC.text.trim().isEmpty
                    ? null
                    : locationC.text.trim(),
              ),
            ),
            child: const Text('Save & Process'),
          ),
        ],
      ),
    );
  }

  Future<bool?> _confirmDiscard() {
    return showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Discard recording?'),
        content: const Text('This recording has not been saved.'),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Keep recording')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Discard')),
        ],
      ),
    );
  }
}

class _SessionMeta {
  final String title;
  final String? speaker;
  final String? location;
  _SessionMeta({required this.title, this.speaker, this.location});
}

class _LocaleSelector extends StatelessWidget {
  final String value;
  final bool enabled;
  final ValueChanged<String> onChanged;

  const _LocaleSelector({
    required this.value,
    required this.enabled,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      child: Row(
        children: [
          const Icon(Icons.language, size: 20),
          const SizedBox(width: 8),
          const Text('Language'),
          const Spacer(),
          DropdownButton<String>(
            value: value,
            underline: const SizedBox.shrink(),
            onChanged:
                enabled ? (v) => v == null ? null : onChanged(v) : null,
            items: [
              for (final l in AppConstants.supportedLocales)
                DropdownMenuItem(value: l.id, child: Text(l.label)),
            ],
          ),
        ],
      ),
    );
  }
}
