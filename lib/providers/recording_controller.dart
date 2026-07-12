import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';

import '../models/kajian_session.dart';
import '../models/transcript_segment.dart';
import '../services/audio_recorder_service.dart';
import '../services/live_transcription_service.dart';

enum RecordingState { idle, recording, paused, finishing }

/// Drives a single live recording: audio capture + live captions + timer.
///
/// On [stop] it returns a [KajianSession] in the `recorded` state, ready to be
/// saved and handed to [SessionProvider.process] for cloud refinement + notes.
class RecordingController extends ChangeNotifier {
  final AudioRecorderService _recorder;
  final LiveTranscriptionService _live;
  final _uuid = const Uuid();

  RecordingController({
    AudioRecorderService? recorder,
    LiveTranscriptionService? live,
  })  : _recorder = recorder ?? AudioRecorderService(),
        _live = live ?? LiveTranscriptionService();

  RecordingState _state = RecordingState.idle;
  RecordingState get state => _state;

  String? _sessionId;
  String? _audioPath;
  String _localeId = 'id_ID';
  DateTime? _startedAt;
  Duration _elapsed = Duration.zero;
  Timer? _ticker;

  double _amplitude = 0;
  double get amplitude => _amplitude;
  Duration get elapsed => _elapsed;

  /// Finalized live-caption segments captured so far.
  final List<TranscriptSegment> _segments = [];

  /// The current interim (not-yet-final) caption line.
  String _interim = '';
  String get interimText => _interim;
  List<TranscriptSegment> get segments => List.unmodifiable(_segments);

  StreamSubscription<double>? _ampSub;
  StreamSubscription<LiveTranscriptResult>? _liveSub;

  bool get isActive =>
      _state == RecordingState.recording || _state == RecordingState.paused;

  Future<bool> ensureReady() async {
    final micOk = await _recorder.ensurePermission();
    if (!micOk) return false;
    await _live.init(); // live captions are best-effort; recording still works
    return true;
  }

  Future<void> start({required String localeId}) async {
    if (_state != RecordingState.idle) return;
    _localeId = localeId;
    _sessionId = _uuid.v4();
    _segments.clear();
    _interim = '';
    _elapsed = Duration.zero;

    _audioPath = await _recorder.start(_sessionId!);
    _startedAt = DateTime.now();
    _state = RecordingState.recording;

    _ampSub = _recorder.amplitudeStream.listen((a) {
      _amplitude = a;
      notifyListeners();
    });
    _liveSub = _live.results.listen(_onLiveResult);
    if (_live.isAvailable) {
      await _live.start(localeId: localeId);
    }
    _startTicker();
    notifyListeners();
  }

  void _onLiveResult(LiveTranscriptResult r) {
    if (r.text.trim().isEmpty) return;
    if (r.isFinal) {
      _segments.add(TranscriptSegment(
        id: _uuid.v4(),
        text: r.text.trim(),
        startMs: _elapsed.inMilliseconds,
        endMs: _elapsed.inMilliseconds,
        isFinal: false, // "false" = live-quality; cloud pass will finalize
      ));
      _interim = '';
    } else {
      _interim = r.text.trim();
    }
    notifyListeners();
  }

  Future<void> pause() async {
    if (_state != RecordingState.recording) return;
    await _recorder.pause();
    await _live.stop();
    _ticker?.cancel();
    _state = RecordingState.paused;
    notifyListeners();
  }

  Future<void> resume() async {
    if (_state != RecordingState.paused) return;
    await _recorder.resume();
    if (_live.isAvailable) await _live.start(localeId: _localeId);
    _startTicker();
    _state = RecordingState.recording;
    notifyListeners();
  }

  /// Stop everything and produce the recorded session.
  Future<KajianSession> stop({
    required String title,
    String? speaker,
    String? location,
  }) async {
    _state = RecordingState.finishing;
    notifyListeners();

    _ticker?.cancel();
    await _live.stop();
    final path = await _recorder.stop();
    await _ampSub?.cancel();
    await _liveSub?.cancel();

    final session = KajianSession(
      id: _sessionId ?? _uuid.v4(),
      title: title.trim().isEmpty ? 'Kajian' : title.trim(),
      speaker: speaker,
      location: location,
      createdAt: _startedAt ?? DateTime.now(),
      durationMs: _elapsed.inMilliseconds,
      audioFilePath: path ?? _audioPath,
      localeId: _localeId,
      transcript: List.of(_segments),
      status: SessionStatus.recorded,
    );

    _reset();
    return session;
  }

  Future<void> cancel() async {
    _ticker?.cancel();
    await _live.stop();
    await _recorder.stop();
    await _ampSub?.cancel();
    await _liveSub?.cancel();
    _reset();
    notifyListeners();
  }

  void _startTicker() {
    _ticker?.cancel();
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
      _elapsed += const Duration(seconds: 1);
      notifyListeners();
    });
  }

  void _reset() {
    _state = RecordingState.idle;
    _sessionId = null;
    _audioPath = null;
    _startedAt = null;
    _amplitude = 0;
    _interim = '';
    _segments.clear();
  }

  @override
  void dispose() {
    _ticker?.cancel();
    _ampSub?.cancel();
    _liveSub?.cancel();
    _recorder.dispose();
    _live.dispose();
    super.dispose();
  }
}
