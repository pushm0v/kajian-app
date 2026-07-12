import 'dart:async';

import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart';

/// Result emitted while listening live.
class LiveTranscriptResult {
  final String text;
  final bool isFinal;
  const LiveTranscriptResult(this.text, this.isFinal);
}

/// On-device / native speech recognition for live captions during a kajian.
///
/// This is the "free, offline, instant" half of the hybrid transcription
/// strategy. It gives immediate feedback while recording; the higher-accuracy
/// cloud pass ([CloudTranscriptionService]) refines the full transcript later.
///
/// Note: native STT has platform limits (session length, occasional auto-stop),
/// so this service auto-restarts listening to keep captions flowing across a
/// long lecture.
class LiveTranscriptionService {
  final SpeechToText _speech = SpeechToText();
  final _resultsController =
      StreamController<LiveTranscriptResult>.broadcast();

  bool _available = false;
  bool _wantListening = false;
  String _localeId = 'id_ID';

  Stream<LiveTranscriptResult> get results => _resultsController.stream;
  bool get isAvailable => _available;
  bool get isListening => _speech.isListening;

  Future<bool> init() async {
    _available = await _speech.initialize(
      onError: (e) {
        // Auto-restart on transient errors while we still want to listen.
        if (_wantListening) _restartSoon();
      },
      onStatus: (status) {
        if (status == 'done' && _wantListening) _restartSoon();
      },
    );
    return _available;
  }

  /// Locales the device actually supports for STT.
  Future<List<String>> availableLocaleIds() async {
    if (!_available) return const [];
    final locales = await _speech.locales();
    return locales.map((l) => l.localeId).toList();
  }

  Future<void> start({required String localeId}) async {
    if (!_available) return;
    _localeId = localeId;
    _wantListening = true;
    await _listen();
  }

  Future<void> _listen() async {
    if (!_wantListening) return;
    await _speech.listen(
      localeId: _localeId,
      onResult: _onResult,
      listenOptions: SpeechListenOptions(
        partialResults: true,
        listenMode: ListenMode.dictation,
        cancelOnError: false,
      ),
      // Keep going through natural pauses in a lecture.
      pauseFor: const Duration(seconds: 6),
      listenFor: const Duration(minutes: 5),
    );
  }

  void _restartSoon() {
    Future<void>.delayed(const Duration(milliseconds: 300), () {
      if (_wantListening && !_speech.isListening) _listen();
    });
  }

  void _onResult(SpeechRecognitionResult result) {
    if (_resultsController.isClosed) return;
    _resultsController.add(
      LiveTranscriptResult(result.recognizedWords, result.finalResult),
    );
  }

  Future<void> stop() async {
    _wantListening = false;
    await _speech.stop();
  }

  Future<void> dispose() async {
    _wantListening = false;
    await _speech.cancel();
    await _resultsController.close();
  }
}
