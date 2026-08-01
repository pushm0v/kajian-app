import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:record/record.dart';

import '../core/config/app_config.dart';

/// Live captions for the Whisper backend, by slicing the microphone into
/// short windows and transcribing each one as an ordinary batch request.
///
/// Why not a WebSocket like [CloudStreamingTranscriptionService]: that path
/// only works against the Qwen worker, because faster-whisper has no
/// incremental-decoding API (see backend-core/app/routers/streaming.py's
/// module docstring). Chunking is how Whisper does "live" — there is no
/// streaming mode to reach for, only many small independent transcriptions.
///
/// The text this produces is provisional and display-only. The real
/// transcript comes from the batch pass over the whole recording once
/// recording stops, which sees full-file context that per-chunk inference
/// cannot match. Nothing here is persisted.
///
/// Owns its own [AudioRecorder], separate from the one writing the saved
/// .m4a — the same two-instance pattern [CloudStreamingTranscriptionService]
/// and [LiveTranscriptionService] already use.
class ChunkedTranscriptionService {
  /// Audio per request. Long enough for Whisper to have usable context
  /// (very short windows transcribe noticeably worse), short enough that
  /// captions don't lag far behind the speaker.
  static const chunkDuration = Duration(seconds: 20);

  /// How much of the previous chunk is replayed at the head of the next
  /// one. Whisper sees each chunk independently, so a word straddling a cut
  /// would be mangled in both halves without this; with it, the word falls
  /// well inside at least one chunk. The cost is that the overlapped speech
  /// is transcribed twice, which [_stitch] then has to reconcile.
  static const overlapDuration = Duration(seconds: 2);

  static const _sampleRate = 16000;
  static const _bytesPerSample = 2; // PCM16
  static int get _bytesPerSecond => _sampleRate * _bytesPerSample;
  static int get _chunkBytes => chunkDuration.inSeconds * _bytesPerSecond;
  static int get _overlapBytes => overlapDuration.inSeconds * _bytesPerSecond;

  final AudioRecorder _recorder = AudioRecorder();
  final http.Client _client;

  StreamSubscription<Uint8List>? _micSub;
  final _resultsController = StreamController<String>.broadcast();

  /// Raw PCM awaiting the next chunk boundary.
  final BytesBuilder _buffer = BytesBuilder(copy: false);

  /// Transcript accumulated from completed chunks, in order.
  final List<String> _pieces = [];

  /// In-flight chunk requests. Kept so [finish] can wait for the tail of
  /// them instead of dropping captions that were still being transcribed
  /// when the user hit stop.
  final List<Future<void>> _inFlight = [];

  bool _running = false;

  ChunkedTranscriptionService({http.Client? client})
      : _client = client ?? http.Client();

  /// Cumulative transcript so far, emitted each time a chunk completes.
  Stream<String> get results => _resultsController.stream;

  bool get isRunning => _running;

  /// Everything transcribed so far, joined.
  String get transcript => _pieces.join(' ').trim();

  /// Starts capturing and transcribing.
  ///
  /// Requires a configured backend and a signed-in user — the chunk
  /// endpoint authenticates exactly like the rest of the REST API.
  Future<void> start({required String localeId}) async {
    if (_running) return;
    if (AppConfig.backendBaseUrl.isEmpty) {
      throw StateError(
        'ChunkedTranscriptionService.start() called with no backend '
        'configured (AppConfig.backendBaseUrl is empty).',
      );
    }
    if (FirebaseAuth.instance.currentUser == null) {
      throw StateError(
        'ChunkedTranscriptionService.start() called while signed out.',
      );
    }

    _running = true;
    _pieces.clear();
    _buffer.clear();

    final micStream = await _recorder.startStream(const RecordConfig(
      encoder: AudioEncoder.pcm16bits,
      sampleRate: _sampleRate,
      numChannels: 1,
    ));
    _micSub = micStream.listen(
      (pcm) => _onAudio(pcm, localeId),
      cancelOnError: false,
    );
  }

  void _onAudio(Uint8List pcm, String localeId) {
    if (!_running) return;
    _buffer.add(pcm);
    if (_buffer.length < _chunkBytes) return;

    // takeBytes() drains the builder, so the overlap tail has to be put
    // back explicitly for the next chunk to start with it.
    final full = _buffer.takeBytes();
    final overlap = full.length > _overlapBytes
        ? Uint8List.sublistView(full, full.length - _overlapBytes)
        : full;
    _buffer.add(overlap);

    // Fire and continue: capture must not stall while a chunk is on the
    // wire. Whisper on a busy GPU can take seconds, and blocking here would
    // drop audio for the length of every request.
    _dispatch(full, localeId);
  }

  void _dispatch(Uint8List pcm, String localeId) {
    late final Future<void> job;
    job = _transcribeChunk(pcm, localeId).then((text) {
      if (text != null && text.isNotEmpty) {
        _pieces.add(_stitch(_pieces.isEmpty ? '' : _pieces.last, text));
        if (!_resultsController.isClosed) {
          _resultsController.add(transcript);
        }
      }
    }).catchError((Object e) {
      // A dropped chunk costs a few seconds of provisional captions, and
      // the authoritative batch pass still covers the whole recording — so
      // this must never surface as an error or stop the recording.
      _resultsController.addError(e);
    }).whenComplete(() => _inFlight.remove(job));
    _inFlight.add(job);
  }

  /// Removes text at the start of [next] that already appeared at the end
  /// of [previous], which the overlap window causes it to repeat.
  ///
  /// Matches on words rather than characters, since Whisper won't
  /// necessarily transcribe the overlapped audio identically twice —
  /// punctuation and casing routinely differ between the two passes.
  @visibleForTesting
  static String stitch(String previous, String next) => _stitch(previous, next);

  static String _stitch(String previous, String next) {
    if (previous.isEmpty) return next;

    final prevWords = _words(previous);
    final nextWords = _words(next);
    if (prevWords.isEmpty || nextWords.isEmpty) return next;

    // The overlap is bounded by overlapDuration, so only a short tail can
    // possibly repeat; cap the search rather than scanning whole chunks.
    final maxOverlap = [prevWords.length, nextWords.length, 12]
        .reduce((a, b) => a < b ? a : b);

    for (var n = maxOverlap; n > 1; n--) {
      final tail = prevWords.sublist(prevWords.length - n);
      final head = nextWords.sublist(0, n);
      if (_normalized(tail) == _normalized(head)) {
        final rest = next.trim().split(RegExp(r'\s+')).sublist(n);
        return rest.join(' ');
      }
    }
    return next;
  }

  static List<String> _words(String s) =>
      s.trim().split(RegExp(r'\s+')).where((w) => w.isNotEmpty).toList();

  static String _normalized(List<String> words) => words
      .map((w) => w.toLowerCase().replaceAll(RegExp(r'[^\w]'), ''))
      .where((w) => w.isNotEmpty)
      .join(' ');

  Future<String?> _transcribeChunk(Uint8List pcm, String localeId) async {
    final user = FirebaseAuth.instance.currentUser;
    if (user == null) return null;
    final token = await user.getIdToken();

    final request = http.MultipartRequest(
      'POST',
      Uri.parse('${AppConfig.backendBaseUrl}/transcribe-chunk'),
    )
      ..headers['Authorization'] = 'Bearer $token'
      ..fields['locale'] = localeId
      ..fields['model'] = 'whisper'
      ..files.add(http.MultipartFile.fromBytes(
        'audio',
        _wrapInWav(pcm),
        filename: 'chunk.wav',
      ));

    final streamed = await _client.send(request).timeout(
          // Generous: a busy GPU can queue. Still bounded so a hung request
          // can't linger for the whole recording.
          const Duration(seconds: 90),
        );
    final response = await http.Response.fromStream(streamed);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw http.ClientException(
        'transcribe-chunk failed (${response.statusCode}): ${response.body}',
      );
    }
    final json = jsonDecode(response.body) as Map<String, dynamic>;
    return (json['text'] as String?)?.trim();
  }

  @visibleForTesting
  static Uint8List wrapInWav(Uint8List pcm) => _wrapInWav(pcm);

  /// Wraps raw PCM16LE in a WAV container.
  ///
  /// The server decodes uploads with ffmpeg/PyAV, which need a container to
  /// know the sample rate and channel count — headerless PCM would be
  /// misread. A 44-byte header is far cheaper than re-encoding.
  static Uint8List _wrapInWav(Uint8List pcm) {
    const headerSize = 44;
    const byteRate = _sampleRate * _bytesPerSample; // mono
    final out = BytesBuilder(copy: false);
    final header = ByteData(headerSize);

    void ascii(int offset, String s) {
      for (var i = 0; i < s.length; i++) {
        header.setUint8(offset + i, s.codeUnitAt(i));
      }
    }

    ascii(0, 'RIFF');
    header.setUint32(4, headerSize - 8 + pcm.length, Endian.little);
    ascii(8, 'WAVE');
    ascii(12, 'fmt ');
    header.setUint32(16, 16, Endian.little); // PCM fmt chunk size
    header.setUint16(20, 1, Endian.little); // format = PCM
    header.setUint16(22, 1, Endian.little); // channels = mono
    header.setUint32(24, _sampleRate, Endian.little);
    header.setUint32(28, byteRate, Endian.little);
    header.setUint16(32, _bytesPerSample, Endian.little); // block align
    header.setUint16(34, 8 * _bytesPerSample, Endian.little); // bits/sample
    ascii(36, 'data');
    header.setUint32(40, pcm.length, Endian.little);

    out.add(header.buffer.asUint8List());
    out.add(pcm);
    return out.takeBytes();
  }

  /// Stops capture, transcribes whatever partial chunk remains, and waits
  /// for in-flight requests so the last few seconds aren't lost.
  Future<String> finish({required String localeId}) async {
    if (!_running) return transcript;
    _running = false;
    await _micSub?.cancel();
    _micSub = null;
    if (await _recorder.isRecording()) await _recorder.stop();

    // Whatever didn't reach a full chunk boundary. Skip a remainder that's
    // only the replayed overlap — transcribing it again would just produce
    // a duplicate for _stitch to strip.
    final tail = _buffer.takeBytes();
    if (tail.length > _overlapBytes) {
      _dispatch(tail, localeId);
    }

    await Future.wait(List.of(_inFlight)).timeout(
      const Duration(seconds: 120),
      onTimeout: () => const [],
    );
    return transcript;
  }

  /// Stops without waiting for outstanding chunks (user cancelled).
  Future<void> cancel() async {
    _running = false;
    await _micSub?.cancel();
    _micSub = null;
    if (await _recorder.isRecording()) await _recorder.stop();
    _buffer.clear();
    _pieces.clear();
  }

  Future<void> dispose() async {
    await cancel();
    await _recorder.dispose();
    await _resultsController.close();
    _client.close();
  }
}
