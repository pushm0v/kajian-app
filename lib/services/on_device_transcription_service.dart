import 'dart:io';

import 'package:whisper_ggml/whisper_ggml.dart';

import '../models/transcript_segment.dart';

/// Offline, on-device high-accuracy transcription via whisper.cpp
/// (whisper_ggml), used as an alternative to [CloudTranscriptionService].
///
/// This is the "private, no backend needed" half of the transcription
/// strategy: it runs a quantized multilingual Whisper model directly on the
/// phone. On iOS/Android, whisper_ggml converts non-WAV input (our .m4a
/// recordings) with its bundled FFmpeg, so no manual audio conversion step
/// is needed here.
class OnDeviceTranscriptionService {
  final WhisperController _controller = WhisperController();

  /// Model used for on-device transcription. `base` (multilingual, ~57MB
  /// quantized) balances accuracy and download/bundle size for Indonesian +
  /// Arabic kajian content; `small` is offered as a higher-accuracy option.
  static const WhisperModel defaultModel = WhisperModel.base;

  /// Whether [model]'s weights are already downloaded on this device.
  Future<bool> isModelReady(WhisperModel model) async {
    final path = await _controller.getPath(model);
    return File(path).existsSync();
  }

  /// Download [model]'s weights. No-ops if already present.
  /// [onProgress] is best-effort; whisper_ggml's downloadModel does not
  /// currently report progress, so this exists for forward compatibility.
  Future<void> downloadModel(WhisperModel model) async {
    await _controller.downloadModel(model);
  }

  /// Transcribe the recorded audio at [audioFilePath] entirely on-device.
  ///
  /// [localeId] is a BCP-47 id (e.g. "id_ID"); whisper_ggml expects a bare
  /// ISO-639-1 language code, so only the language portion is used.
  Future<List<TranscriptSegment>> transcribe({
    required String audioFilePath,
    required String localeId,
    WhisperModel model = defaultModel,
    void Function(int percent)? onProgress,
  }) async {
    final ready = await isModelReady(model);
    if (!ready) {
      await downloadModel(model);
    }

    final result = await _controller.transcribe(
      model: model,
      audioPath: audioFilePath,
      lang: _whisperLangCode(localeId),
      withSegments: true,
      onProgress: onProgress,
    );

    if (result == null) {
      throw StateError('On-device transcription failed to produce a result.');
    }

    final segments = result.transcription.segments;
    if (segments == null || segments.isEmpty) {
      final text = result.transcription.text.trim();
      if (text.isEmpty) return const [];
      return [
        TranscriptSegment(id: 'ondevice_0', text: text, startMs: 0),
      ];
    }

    return [
      for (var i = 0; i < segments.length; i++)
        TranscriptSegment(
          id: 'ondevice_$i',
          text: segments[i].text.trim(),
          startMs: segments[i].fromTs.inMilliseconds,
          endMs: segments[i].toTs.inMilliseconds,
        ),
    ].where((s) => s.text.isNotEmpty).toList();
  }

  /// Maps a BCP-47 locale id (e.g. "id_ID", "ar_SA") to the ISO-639-1 code
  /// whisper.cpp expects (e.g. "id", "ar").
  String _whisperLangCode(String localeId) {
    final base = localeId.split(RegExp('[_-]')).first.toLowerCase();
    return base.isEmpty ? 'auto' : base;
  }
}
