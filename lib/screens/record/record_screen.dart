import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/config/app_config.dart';
import '../../core/constants/app_constants.dart';
import '../../core/utils/formatters.dart';
import '../../providers/recording_controller.dart';
import '../../services/settings_service.dart';
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
  final _settings = SettingsService();

  String _localeId = AppConstants.defaultLocaleId;
  bool _ready = false;
  bool _cloudLiveCaptionsEnabled = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _prepare());
  }

  Future<void> _prepare() async {
    final controller = context.read<RecordingController>();
    final ok = await controller.ensureReady();
    final cloudLiveCaptionsEnabled =
        await _settings.getCloudLiveCaptionsEnabled();
    if (!mounted) return;
    setState(() {
      _ready = ok;
      _cloudLiveCaptionsEnabled = cloudLiveCaptionsEnabled;
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
        if (didPop || !controller.isActive) return;
        final navigator = Navigator.of(context);
        final leave = await _confirmDiscard();
        if (leave != true) return;
        await controller.cancel();
        navigator.pop();
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
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 40),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                c.state == RecordingState.idle
                    ? Icons.graphic_eq_rounded
                    : Icons.hearing_rounded,
                size: 40,
                color: theme.colorScheme.primary.withValues(alpha: 0.7),
              ),
              const SizedBox(height: 16),
              Text(
                c.state == RecordingState.idle
                    ? 'Ready when you are'
                    : 'Listening…',
                style: theme.textTheme.headlineSmall,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 6),
              Text(
                c.state == RecordingState.idle
                    ? 'Live captions will appear here as the\nkajian is spoken.'
                    : 'Keep the mic near the speaker.',
                style: theme.textTheme.bodyMedium
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      );
    }
    return ListView(
      reverse: true,
      padding: const EdgeInsets.all(16),
      children: [
        if (c.isCloudStreamingActive && c.cloudInterimText.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.cloud_outlined,
                        size: 14, color: theme.colorScheme.primary),
                    const SizedBox(width: 4),
                    Text('CLOUD',
                        style: theme.textTheme.labelSmall?.copyWith(
                            color: theme.colorScheme.primary,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 1)),
                  ],
                ),
                const SizedBox(height: 4),
                Text(c.cloudInterimText, style: theme.textTheme.bodyLarge),
              ],
            ),
          ),
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
    final recording = c.state == RecordingState.recording;
    final paused = c.state == RecordingState.paused;
    final (Color dot, String label) = recording
        ? (const Color(0xFFE5484D), 'Recording')
        : paused
            ? (const Color(0xFFFFB020), 'Paused')
            : (theme.colorScheme.onSurfaceVariant, 'Ready');
    return Column(
      children: [
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 9,
              height: 9,
              decoration: BoxDecoration(color: dot, shape: BoxShape.circle),
            ),
            const SizedBox(width: 8),
            Text(
              label.toUpperCase(),
              style: theme.textTheme.labelMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
                letterSpacing: 1.5,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Text(
          Formatters.duration(c.elapsed),
          style: TextStyle(
            fontFamily: 'Roboto', // sans, not the serif display face
            fontSize: 52,
            fontWeight: FontWeight.w300,
            letterSpacing: 1,
            color: theme.colorScheme.onSurface,
            fontFeatures: const [FontFeature.tabularFigures()],
          ),
        ),
        const SizedBox(height: 12),
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
    final scheme = Theme.of(context).colorScheme;
    switch (c.state) {
      case RecordingState.idle:
        return _CircleControl(
          icon: Icons.mic,
          label: 'Record',
          background: scheme.primary,
          foreground: Colors.white,
          size: 84,
          onTap: _ready
              ? () => c.start(
                    localeId: _localeId,
                    enableCloudLiveCaptions: _cloudLiveCaptionsEnabled &&
                        AppConfig.cloudStreamingUrl.isNotEmpty,
                  )
              : null,
        );
      case RecordingState.finishing:
        return const Padding(
          padding: EdgeInsets.all(24),
          child: CircularProgressIndicator(),
        );
      case RecordingState.recording:
      case RecordingState.paused:
        final paused = c.state == RecordingState.paused;
        return Row(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _CircleControl(
              icon: paused ? Icons.play_arrow : Icons.pause,
              label: paused ? 'Resume' : 'Pause',
              background: scheme.surfaceContainerHigh,
              foreground: scheme.onSurface,
              size: 66,
              onTap: () => paused ? c.resume() : c.pause(),
            ),
            const SizedBox(width: 44),
            _CircleControl(
              icon: Icons.stop_rounded,
              label: 'Finish',
              background: const Color(0xFFE5484D),
              foreground: Colors.white,
              size: 84,
              onTap: _finish,
            ),
          ],
        );
    }
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
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      child: Align(
        alignment: Alignment.center,
        child: Container(
          padding: const EdgeInsets.only(left: 16, right: 8),
          decoration: BoxDecoration(
            color: scheme.surfaceContainerHigh,
            borderRadius: BorderRadius.circular(30),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.language, size: 18, color: scheme.primary),
              const SizedBox(width: 8),
              DropdownButtonHideUnderline(
                child: DropdownButton<String>(
                  value: value,
                  isDense: true,
                  borderRadius: BorderRadius.circular(16),
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      color: scheme.onSurface, fontWeight: FontWeight.w600),
                  onChanged: enabled
                      ? (v) => v == null ? null : onChanged(v)
                      : null,
                  items: [
                    for (final l in AppConstants.supportedLocales)
                      DropdownMenuItem(value: l.id, child: Text(l.label)),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// A large circular control (record / pause / finish) with a caption below.
class _CircleControl extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color background;
  final Color foreground;
  final double size;
  final VoidCallback? onTap;

  const _CircleControl({
    required this.icon,
    required this.label,
    required this.background,
    required this.foreground,
    required this.size,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final disabled = onTap == null;
    final bg = disabled ? background.withValues(alpha: 0.4) : background;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: size,
          height: size,
          decoration: BoxDecoration(
            color: bg,
            shape: BoxShape.circle,
            boxShadow: disabled
                ? null
                : [
                    BoxShadow(
                      color: background.withValues(alpha: 0.35),
                      blurRadius: 18,
                      offset: const Offset(0, 8),
                    ),
                  ],
          ),
          child: Material(
            color: Colors.transparent,
            shape: const CircleBorder(),
            clipBehavior: Clip.antiAlias,
            child: InkResponse(
              onTap: onTap,
              radius: size / 2,
              child: Icon(icon, size: size * 0.42, color: foreground),
            ),
          ),
        ),
        const SizedBox(height: 10),
        Text(
          label,
          style: theme.textTheme.labelLarge?.copyWith(
            fontWeight: FontWeight.w600,
            color: disabled
                ? theme.colorScheme.onSurfaceVariant
                : theme.colorScheme.onSurface,
          ),
        ),
      ],
    );
  }
}
