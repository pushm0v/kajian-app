import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:record/record.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../core/config/app_config.dart';

/// Result emitted while streaming to the cloud model. Unlike
/// [LiveTranscriptResult] from on-device STT, [text] here is always the
/// *cumulative* transcript for the whole streaming session so far — the
/// server has no concept of "final" segments mid-stream (see
/// backend/app/streaming.py's wire protocol) — [isFinal] only turns true
/// once, right before the connection closes at the end of recording.
class CloudStreamResult {
  final String text;
  final bool isFinal;
  const CloudStreamResult(this.text, this.isFinal);
}

/// Live, low-latency transcription via a self-hosted Qwen3-ASR backend
/// (see backend/app/streaming.py), as an alternative/supplement to the
/// on-device [LiveTranscriptionService] during recording.
///
/// Owns its own microphone capture via a dedicated [AudioRecorder] instance
/// — separate from the one [AudioRecorderService] uses to write the saved
/// .m4a file. Running two `record` instances at once (one file-based, one
/// streaming) is supported by the plugin (each gets its own native
/// AVAudioEngine tap / AudioRecord session; see the package's v5.0.0
/// "multiple instance support" changelog entry) and is the same pattern
/// [LiveTranscriptionService] follows for on-device STT, which also
/// independently taps the mic.
///
/// This talks directly to `AppConfig.cloudStreamingUrl` over a WebSocket —
/// it is NOT gated by [AppConfig.isMockMode] the way [CloudTranscriptionService]
/// and [AiNotesService] are, since there's no server-side mock for a live
/// socket. Callers must check [AppConfig.cloudStreamingUrl] is non-empty (a
/// backend is actually configured) before calling [start].
class CloudStreamingTranscriptionService {
  final AudioRecorder _recorder = AudioRecorder();
  StreamSubscription<Uint8List>? _micSub;

  WebSocketChannel? _channel;
  StreamSubscription? _channelSub;
  final _resultsController =
      StreamController<CloudStreamResult>.broadcast();

  bool _connected = false;

  Stream<CloudStreamResult> get results => _resultsController.stream;
  bool get isConnected => _connected;

  static const _sampleRate = 16000;

  /// Opens the WebSocket, starts a second mic-capture stream (PCM16LE mono
  /// 16kHz, matching backend/app/streaming.py's expected wire format), and
  /// begins forwarding captured audio to the server as it arrives.
  Future<void> start({required String localeId}) async {
    final base = AppConfig.cloudStreamingUrl;
    if (base.isEmpty) {
      throw StateError(
        'CloudStreamingTranscriptionService.start() called with no backend '
        'configured (AppConfig.cloudStreamingUrl is empty).',
      );
    }

    final uri = Uri.parse('$base/transcribe/stream').replace(
      queryParameters: {
        'locale': localeId,
        if (AppConfig.backendAuthToken.isNotEmpty)
          'token': AppConfig.backendAuthToken,
      },
    );

    _channel = WebSocketChannel.connect(uri);
    _connected = true;
    _channelSub = _channel!.stream.listen(
      _onMessage,
      onError: (Object _) => _connected = false,
      onDone: () => _connected = false,
      cancelOnError: false,
    );

    final micStream = await _recorder.startStream(const RecordConfig(
      encoder: AudioEncoder.pcm16bits,
      sampleRate: _sampleRate,
      numChannels: 1,
    ));
    _micSub = micStream.listen(sendAudioChunk);
  }

  void _onMessage(dynamic message) {
    if (_resultsController.isClosed) return;
    if (message is! String) return;

    final Map<String, dynamic> json;
    try {
      json = jsonDecode(message) as Map<String, dynamic>;
    } catch (_) {
      return; // Ignore malformed frames rather than crashing the session.
    }

    switch (json['type']) {
      case 'partial':
        _resultsController.add(
          CloudStreamResult(json['text'] as String? ?? '', false),
        );
      case 'final':
        _resultsController.add(
          CloudStreamResult(json['text'] as String? ?? '', true),
        );
      case 'error':
        // Surfaced as an empty non-final result rather than throwing —
        // callers already treat this stream as best-effort, same as the
        // on-device live captions.
        break;
    }
  }

  /// Sends one chunk of raw PCM16LE mono 16kHz audio, as produced by
  /// `record`'s `startStream()` when configured with
  /// `AudioEncoder.pcm16bits`, `sampleRate: 16000`, `numChannels: 1`.
  void sendAudioChunk(Uint8List pcm16) {
    if (!_connected) return;
    _channel?.sink.add(pcm16);
  }

  /// Signals end-of-audio to the server and waits for its final cumulative
  /// transcript (the last "final" [CloudStreamResult]), then closes the
  /// connection. Returns null if the socket was never connected or the
  /// server never sent a final result before closing.
  Future<String?> finish() async {
    if (!_connected || _channel == null) return null;

    final completer = Completer<String?>();
    late final StreamSubscription sub;
    sub = results.listen((r) {
      if (r.isFinal) {
        if (!completer.isCompleted) completer.complete(r.text);
        sub.cancel();
      }
    });

    _channel!.sink.add('__end__');

    final text = await completer.future.timeout(
      const Duration(seconds: 15),
      onTimeout: () => null,
    );
    await sub.cancel();
    await _close();
    return text;
  }

  /// Aborts the session without waiting for a final result (e.g. the user
  /// cancelled the recording).
  Future<void> cancel() => _close();

  Future<void> _close() async {
    _connected = false;
    await _micSub?.cancel();
    _micSub = null;
    if (await _recorder.isRecording()) await _recorder.stop();
    await _channelSub?.cancel();
    await _channel?.sink.close();
    _channel = null;
  }

  Future<void> dispose() async {
    await _close();
    await _recorder.dispose();
    await _resultsController.close();
  }
}
