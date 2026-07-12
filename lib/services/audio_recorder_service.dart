import 'dart:async';

import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

/// Wraps the [record] plugin to capture kajian audio to a local file.
///
/// Produces an `.m4a` (AAC) file — a good balance of quality and size for
/// long-form speech, and a format the cloud transcription endpoint accepts.
class AudioRecorderService {
  final AudioRecorder _recorder = AudioRecorder();

  Timer? _amplitudeTimer;
  final _amplitudeController = StreamController<double>.broadcast();

  /// Normalised amplitude 0..1 for a live waveform / level meter.
  Stream<double> get amplitudeStream => _amplitudeController.stream;

  /// Ask for microphone permission. Returns true if granted.
  Future<bool> ensurePermission() async {
    if (await _recorder.hasPermission()) return true;
    final status = await Permission.microphone.request();
    return status.isGranted;
  }

  Future<bool> get isRecording => _recorder.isRecording();
  Future<bool> get isPaused => _recorder.isPaused();

  /// Start recording. Returns the file path being written to.
  Future<String> start(String sessionId) async {
    final dir = await getApplicationDocumentsDirectory();
    final path = '${dir.path}/kajian_$sessionId.m4a';

    const config = RecordConfig(
      encoder: AudioEncoder.aacLc,
      bitRate: 96000,
      sampleRate: 44100,
      numChannels: 1, // mono is plenty for speech and halves file size
    );

    await _recorder.start(config, path: path);
    _startAmplitudePolling();
    return path;
  }

  Future<void> pause() async {
    await _recorder.pause();
    _amplitudeTimer?.cancel();
  }

  Future<void> resume() async {
    await _recorder.resume();
    _startAmplitudePolling();
  }

  /// Stop recording and return the final file path (or null on failure).
  Future<String?> stop() async {
    _amplitudeTimer?.cancel();
    return _recorder.stop();
  }

  void _startAmplitudePolling() {
    _amplitudeTimer?.cancel();
    _amplitudeTimer =
        Timer.periodic(const Duration(milliseconds: 200), (_) async {
      try {
        final amp = await _recorder.getAmplitude();
        // getAmplitude returns dBFS (<= 0). Map roughly to 0..1.
        final normalized = ((amp.current + 45) / 45).clamp(0.0, 1.0);
        if (!_amplitudeController.isClosed) {
          _amplitudeController.add(normalized);
        }
      } catch (_) {
        // ignore transient read errors
      }
    });
  }

  Future<void> dispose() async {
    _amplitudeTimer?.cancel();
    await _amplitudeController.close();
    await _recorder.dispose();
  }
}
