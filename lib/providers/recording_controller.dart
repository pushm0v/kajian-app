import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';

import '../core/config/app_config.dart';
import '../models/kajian_session.dart';
import '../models/transcript_segment.dart';
import '../services/audio_recorder_service.dart';
import '../services/cloud_streaming_transcription_service.dart';
import '../services/live_transcription_service.dart';

enum RecordingState { idle, recording, paused, finishing }

/// Drives a single live recording: audio capture + live captions + timer.
///
/// On [stop] it returns a [KajianSession] in the `recorded` state, ready to be
/// saved and handed to [SessionProvider.process] for cloud refinement + notes.
class RecordingController extends ChangeNotifier {
  final AudioRecorderService _recorder;
  final LiveTranscriptionService _live;
  final CloudStreamingTranscriptionService _cloudStream;
  final _uuid = const Uuid();

  RecordingController({
    AudioRecorderService? recorder,
    LiveTranscriptionService? live,
    CloudStreamingTranscriptionService? cloudStream,
  })  : _recorder = recorder ?? AudioRecorderService(),
        _live = live ?? LiveTranscriptionService(),
        _cloudStream = cloudStream ?? CloudStreamingTranscriptionService();

  RecordingState _state = RecordingState.idle;
  RecordingState get state => _state;

  String? _sessionId;
  String? _audioPath;
  String _localeId = 'id_ID';
  DateTime? _startedAt;
  Duration _elapsed = Duration.zero;
  Timer? _ticker;

  /// Whether this recording should also stream live audio to a self-hosted
  /// cloud model for captions (backend/app/streaming.py), in addition to
  /// on-device captions. Set per-recording via [start]; the caller (record
  /// screen) is responsible for reading the user's setting and only passing
  /// true when a backend is actually configured
  /// (AppConfig.cloudStreamingUrl.isNotEmpty).
  bool _cloudCaptionsRequested = false;

  double _amplitude = 0;
  double get amplitude => _amplitude;
  Duration get elapsed => _elapsed;

  /// Finalized live-caption segments captured so far (on-device source).
  final List<TranscriptSegment> _segments = [];

  /// The current interim (not-yet-final) caption line — on-device source.
  String _interim = '';
  String get interimText => _interim;
  List<TranscriptSegment> get segments => List.unmodifiable(_segments);

  /// Cumulative cloud-streamed transcript so far, if cloud live captions are
  /// enabled for this recording. Empty when not requested, not configured,
  /// or not yet connected.
  String _cloudInterim = '';
  String get cloudInterimText => _cloudInterim;
  bool get isCloudStreamingActive => _cloudCaptionsRequested;

  StreamSubscription<double>? _ampSub;
  StreamSubscription<LiveTranscriptResult>? _liveSub;
  StreamSubscription<CloudStreamResult>? _cloudSub;

  bool get isActive =>
      _state == RecordingState.recording || _state == RecordingState.paused;

  Future<bool> ensureReady() async {
    final micOk = await _recorder.ensurePermission();
    if (!micOk) return false;
    await _live.init(); // live captions are best-effort; recording still works
    return true;
  }

  /// [enableCloudLiveCaptions] additionally streams this recording's audio
  /// to the self-hosted cloud model for live captions. Ignored (treated as
  /// false) when no backend is configured, since there's nothing to stream
  /// to.
  Future<void> start({
    required String localeId,
    bool enableCloudLiveCaptions = false,
  }) async {
    if (_state != RecordingState.idle) return;
    _localeId = localeId;
    _sessionId = _uuid.v4();
    _segments.clear();
    _interim = '';
    _cloudInterim = '';
    _elapsed = Duration.zero;
    _cloudCaptionsRequested =
        enableCloudLiveCaptions && AppConfig.cloudStreamingUrl.isNotEmpty;

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

    if (_cloudCaptionsRequested) {
      _cloudSub = _cloudStream.results.listen(_onCloudResult);
      try {
        await _cloudStream.start(localeId: localeId);
      } catch (_) {
        // Best-effort, same philosophy as on-device captions: a failure to
        // connect shouldn't stop the recording itself.
        _cloudCaptionsRequested = false;
      }
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

  void _onCloudResult(CloudStreamResult r) {
    _cloudInterim = r.text;
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
    if (_cloudCaptionsRequested) await _cloudStream.finish();
    await _ampSub?.cancel();
    await _liveSub?.cancel();
    await _cloudSub?.cancel();

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
    if (_cloudCaptionsRequested) await _cloudStream.cancel();
    await _ampSub?.cancel();
    await _liveSub?.cancel();
    await _cloudSub?.cancel();
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
    _cloudInterim = '';
    _cloudCaptionsRequested = false;
  }

  @override
  void dispose() {
    _ticker?.cancel();
    _ampSub?.cancel();
    _liveSub?.cancel();
    _cloudSub?.cancel();
    _recorder.dispose();
    _live.dispose();
    _cloudStream.dispose();
    super.dispose();
  }
}
