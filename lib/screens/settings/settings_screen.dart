import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../services/on_device_transcription_service.dart';
import '../../services/settings_service.dart';
import '../../widgets/app_toast.dart';

/// App settings: transcription mode, on-device model status, and account.
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _settings = SettingsService();
  final _onDevice = OnDeviceTranscriptionService();

  TranscriptionMode? _mode;
  bool _modelReady = false;
  bool _downloading = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final mode = await _settings.getTranscriptionMode();
    final ready = await _onDevice.isModelReady(
      OnDeviceTranscriptionService.defaultModel,
    );
    if (!mounted) return;
    setState(() {
      _mode = mode;
      _modelReady = ready;
    });
  }

  Future<void> _selectMode(TranscriptionMode mode) async {
    setState(() => _mode = mode);
    await _settings.setTranscriptionMode(mode);

    if (mode == TranscriptionMode.onDevice && !_modelReady) {
      await _downloadModel();
    }
  }

  Future<void> _downloadModel() async {
    setState(() => _downloading = true);
    try {
      await _onDevice.downloadModel(OnDeviceTranscriptionService.defaultModel);
      final ready = await _onDevice.isModelReady(
        OnDeviceTranscriptionService.defaultModel,
      );
      if (!mounted) return;
      setState(() => _modelReady = ready);
      if (ready) AppToast.success(context, 'On-device model ready');
    } catch (e) {
      if (!mounted) return;
      AppToast.error(context, 'Could not download model: $e');
    } finally {
      if (mounted) setState(() => _downloading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final mode = _mode;
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: mode == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
              children: [
                Text('Transcription',
                    style: Theme.of(context)
                        .textTheme
                        .headlineSmall
                        ?.copyWith(fontSize: 19)),
                const SizedBox(height: 4),
                Text(
                  'Choose how the accurate transcript is produced after '
                  'you finish recording. Live captions during recording are '
                  'unaffected.',
                  style: Theme.of(context)
                      .textTheme
                      .bodySmall
                      ?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant),
                ),
                const SizedBox(height: 12),
                _ModeCard(
                  mode: TranscriptionMode.cloud,
                  selected: mode == TranscriptionMode.cloud,
                  onSelect: () => _selectMode(TranscriptionMode.cloud),
                ),
                const SizedBox(height: 8),
                _ModeCard(
                  mode: TranscriptionMode.onDevice,
                  selected: mode == TranscriptionMode.onDevice,
                  onSelect: () => _selectMode(TranscriptionMode.onDevice),
                  trailing: _onDeviceStatus(),
                ),
                const SizedBox(height: 32),
                Text('Account',
                    style: Theme.of(context)
                        .textTheme
                        .headlineSmall
                        ?.copyWith(fontSize: 19)),
                const SizedBox(height: 8),
                const _AccountSection(),
              ],
            ),
    );
  }

  Widget _onDeviceStatus() {
    if (_downloading) {
      return const SizedBox(
        width: 20,
        height: 20,
        child: CircularProgressIndicator(strokeWidth: 2),
      );
    }
    if (_modelReady) {
      return Icon(Icons.check_circle,
          color: Theme.of(context).colorScheme.primary, size: 20);
    }
    return TextButton(
      onPressed: _downloadModel,
      child: const Text('Download'),
    );
  }
}

class _ModeCard extends StatelessWidget {
  final TranscriptionMode mode;
  final bool selected;
  final VoidCallback onSelect;
  final Widget? trailing;

  const _ModeCard({
    required this.mode,
    required this.selected,
    required this.onSelect,
    this.trailing,
  });

  IconData get _icon => mode == TranscriptionMode.onDevice
      ? Icons.smartphone_rounded
      : Icons.cloud_done_rounded;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    return Material(
      color: selected
          ? scheme.primaryContainer.withValues(alpha: 0.45)
          : scheme.surfaceContainerLow,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        onTap: onSelect,
        borderRadius: BorderRadius.circular(18),
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            border: Border.all(
              color: selected ? scheme.primary : scheme.outlineVariant,
              width: selected ? 1.5 : 1,
            ),
          ),
          padding: const EdgeInsets.all(16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 40,
                height: 40,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: selected
                      ? scheme.primary
                      : scheme.surfaceContainerHigh,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(_icon,
                    size: 21,
                    color: selected ? Colors.white : scheme.onSurfaceVariant),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(mode.label,
                              style: theme.textTheme.titleSmall
                                  ?.copyWith(fontWeight: FontWeight.w700)),
                        ),
                        Icon(
                          selected
                              ? Icons.check_circle_rounded
                              : Icons.circle_outlined,
                          size: 20,
                          color: selected ? scheme.primary : scheme.outline,
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      mode.description,
                      style: theme.textTheme.bodySmall
                          ?.copyWith(color: scheme.onSurfaceVariant),
                    ),
                    if (trailing != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 10),
                        child: Align(
                            alignment: Alignment.centerLeft, child: trailing!),
                      ),
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

class _AccountSection extends StatelessWidget {
  const _AccountSection();

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final user = auth.user;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  backgroundImage: user?.photoURL != null
                      ? NetworkImage(user!.photoURL!)
                      : null,
                  child: user?.photoURL == null
                      ? const Icon(Icons.person)
                      : null,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        user?.displayName?.isNotEmpty == true
                            ? user!.displayName!
                            : 'Signed in',
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                      if (user?.email != null)
                        Text(
                          user!.email!,
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color:
                                  Theme.of(context).colorScheme.onSurfaceVariant),
                        ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () => auth.signOut(),
                icon: const Icon(Icons.logout),
                label: const Text('Sign out'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
