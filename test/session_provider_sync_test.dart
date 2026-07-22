import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kajian_app/models/kajian_note.dart';
import 'package:kajian_app/models/kajian_session.dart';
import 'package:kajian_app/models/transcript_segment.dart';
import 'package:kajian_app/providers/session_provider.dart';
import 'package:kajian_app/services/core_api_client.dart';

/// In-memory fake — no real HTTP, no Firebase required. Covers exactly the
/// calls SessionProvider makes, matching CoreApiClientBase's contract.
class _FakeCoreApiClient implements CoreApiClientBase {
  final Map<String, KajianSession> remote;
  bool failNextCall = false;

  _FakeCoreApiClient([Map<String, KajianSession>? seed])
      : remote = seed ?? {};

  void _maybeFail() {
    if (failNextCall) {
      failNextCall = false;
      throw const SocketException('offline');
    }
  }

  @override
  Future<List<KajianSession>> listSessions() async {
    _maybeFail();
    return remote.values.toList();
  }

  @override
  Future<KajianSession> createSession(KajianSession session) async {
    _maybeFail();
    remote[session.id] = session;
    return session;
  }

  @override
  Future<KajianSession> updateSession(
    String id, {
    String? title,
    String? speaker,
    String? location,
    int? durationMs,
    SessionStatus? status,
  }) async {
    _maybeFail();
    final existing = remote[id];
    if (existing == null) throw StateError('not found');
    final updated = existing.copyWith(
      title: title,
      speaker: speaker,
      location: location,
      durationMs: durationMs,
      status: status,
    );
    remote[id] = updated;
    return updated;
  }

  @override
  Future<void> deleteSession(String id) async {
    _maybeFail();
    remote.remove(id);
  }

  @override
  Future<KajianSession> replaceTranscript(
    String sessionId,
    List<TranscriptSegment> segments,
  ) async {
    _maybeFail();
    final updated = remote[sessionId]!.copyWith(transcript: segments);
    remote[sessionId] = updated;
    return updated;
  }

  @override
  Future<KajianSession> replaceNote(String sessionId, KajianNote note) async {
    _maybeFail();
    final updated = remote[sessionId]!.copyWith(note: note);
    remote[sessionId] = updated;
    return updated;
  }

  @override
  Future<KajianSession> uploadAudio(String sessionId, String audioFilePath) async {
    _maybeFail();
    final updated = remote[sessionId]!.copyWith(hasServerAudio: true);
    remote[sessionId] = updated;
    return updated;
  }

  @override
  Future<String> getAudioDownloadUrl(String sessionId) async {
    _maybeFail();
    return 'https://fake/$sessionId.m4a';
  }

  @override
  Future<KajianSession> transcribe(String sessionId, {required String model}) async {
    _maybeFail();
    const segments = [
      TranscriptSegment(id: '0', text: 'Server transcript', startMs: 0, endMs: 1000),
    ];
    final updated = remote[sessionId]!.copyWith(transcript: segments);
    remote[sessionId] = updated;
    return updated;
  }

  @override
  Future<KajianSession> summarize(String sessionId, {String? model}) async {
    _maybeFail();
    final note = KajianNote(summary: 'Server summary', generatedAt: DateTime(2026));
    final updated = remote[sessionId]!.copyWith(note: note);
    remote[sessionId] = updated;
    return updated;
  }

  @override
  void dispose() {}
}

KajianSession _session(String id, {DateTime? createdAt}) => KajianSession(
      id: id,
      title: 'Kajian $id',
      createdAt: createdAt ?? DateTime(2026, 1, 1),
      localeId: 'id_ID',
    );

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  // StorageService uses path_provider's getApplicationDocumentsDirectory(),
  // which has no platform implementation under plain flutter_test — mock
  // its method channel to point at a real temp directory, so
  // StorageService.saveAll()/loadAll() actually read/write a real file
  // instead of throwing (loadAll() would silently swallow the error and
  // return [], but saveAll() has no such fallback and would throw,
  // breaking every test that calls SessionProvider.upsert()).
  late Directory tempDir;
  const channel = MethodChannel('plugins.flutter.io/path_provider');

  setUp(() async {
    tempDir = await Directory.systemTemp.createTemp('session_provider_test');
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
      if (call.method == 'getApplicationDocumentsDirectory') {
        return tempDir.path;
      }
      return null;
    });
  });

  tearDown(() async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
    if (await tempDir.exists()) await tempDir.delete(recursive: true);
  });

  group('SessionProvider sync', () {
    test('load() with syncEnabled=false never touches the API client', () async {
      final fake = _FakeCoreApiClient({'s1': _session('s1')});
      final provider = SessionProvider(core: fake, syncEnabled: false);

      await provider.load();

      // Local cache is empty (nothing saved yet) and the remote fake was
      // never queried, since syncEnabled is false.
      expect(provider.sessions, isEmpty);
    });

    test('upsert() with syncEnabled=false does not push to the server', () async {
      final fake = _FakeCoreApiClient();
      final provider = SessionProvider(core: fake, syncEnabled: false);

      await provider.upsert(_session('local-only'));

      expect(provider.sessions.map((s) => s.id), contains('local-only'));
      expect(fake.remote.containsKey('local-only'), isFalse);
    });

    test('upsert() with syncEnabled=true pushes create then update', () async {
      final fake = _FakeCoreApiClient();
      final provider = SessionProvider(core: fake, syncEnabled: true);

      final session = _session('s1');
      await provider.upsert(session);
      expect(fake.remote['s1']?.title, 'Kajian s1');

      await provider.upsert(session.copyWith(title: 'Renamed'));
      expect(fake.remote['s1']?.title, 'Renamed');
    });

    test('upsert() keeps the local save even if the server push fails', () async {
      final fake = _FakeCoreApiClient()..failNextCall = true;
      final provider = SessionProvider(core: fake, syncEnabled: true);

      // Should not throw despite the fake failing the push.
      await provider.upsert(_session('s1'));

      expect(provider.sessions.map((s) => s.id), contains('s1'));
      expect(fake.remote.containsKey('s1'), isFalse); // push failed
    });

    test('delete() removes locally even if the server call fails', () async {
      final fake = _FakeCoreApiClient({'s1': _session('s1')})
        ..failNextCall = true;
      final provider = SessionProvider(core: fake, syncEnabled: true);
      await provider.upsert(_session('s1'));
      fake.failNextCall = true;

      await provider.delete('s1');

      expect(provider.byId('s1'), isNull);
    });

    test(
      'sync from server merges remote sessions while preserving local audioFilePath',
      () async {
        final remoteSession = _session('s1');
        final fake = _FakeCoreApiClient({'s1': remoteSession});
        final provider = SessionProvider(core: fake, syncEnabled: false);

        // Simulate a locally-recorded session (has a local audio path,
        // not yet known to the server under this fake's setup).
        await provider.upsert(
          _session('s1').copyWith(audioFilePath: '/local/path.m4a'),
        );

        provider.syncEnabled = true;
        await provider.load();

        final merged = provider.byId('s1');
        expect(merged, isNotNull);
        // Local-only field preserved across the server merge.
        expect(merged!.audioFilePath, '/local/path.m4a');
      },
    );

    test('sync from server keeps local-only sessions the server doesn\'t know about', () async {
      final fake = _FakeCoreApiClient(); // empty remote
      final provider = SessionProvider(core: fake, syncEnabled: false);
      await provider.upsert(_session('offline-only'));

      provider.syncEnabled = true;
      await provider.load();

      expect(provider.byId('offline-only'), isNotNull);
    });
  });
}
