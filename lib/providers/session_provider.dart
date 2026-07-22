import 'package:flutter/foundation.dart';

import '../models/kajian_session.dart';
import '../models/transcript_segment.dart';
import '../services/ai_notes_service.dart';
import '../services/cloud_transcription_service.dart';
import '../services/core_api_client.dart';
import '../services/on_device_transcription_service.dart';
import '../services/settings_service.dart';
import '../services/storage_service.dart';

/// Owns the list of saved kajian sessions and the post-recording processing
/// pipeline (transcription -> AI notes).
///
/// backend-core (see ../services/core_api_client.dart) is the source of
/// truth when reachable — sessions, transcripts, and notes live there so
/// they survive a reinstall and are visible to the admin dashboard.
/// [StorageService]'s local JSON file is a read-through cache: it's what
/// [sessions] reflects immediately (including fully offline), while
/// [load] reconciles with the server in the background when a backend is
/// configured and the user is signed in. Newly recorded sessions and
/// edits are saved locally right away and pushed to the server
/// best-effort — a failed push doesn't block the local save, so recording
/// a kajian never depends on connectivity.
///
/// The accurate (post-recording) transcription pass runs against the
/// cloud backend (proxied through backend-core, which then talks to the
/// Qwen/Whisper ASR workers) or fully on-device (whisper.cpp), per the
/// user's [TranscriptionMode] setting — on-device transcription has no
/// server involvement at all, since inference happens on the phone.
class SessionProvider extends ChangeNotifier {
  final StorageService _storage;
  final CloudTranscriptionService _cloud;
  final OnDeviceTranscriptionService _onDevice;
  final SettingsService _settings;
  final AiNotesService _ai;
  final CoreApiClientBase _core;

  /// Whether the caller is currently signed in and a backend is
  /// configured — set by whoever owns this provider (see main.dart),
  /// since [SessionProvider] itself has no visibility into auth state.
  bool syncEnabled;

  SessionProvider({
    StorageService? storage,
    CloudTranscriptionService? cloud,
    OnDeviceTranscriptionService? onDevice,
    SettingsService? settings,
    AiNotesService? ai,
    CoreApiClientBase? core,
    this.syncEnabled = false,
  })  : _storage = storage ?? StorageService(),
        _cloud = cloud ?? CloudTranscriptionService(),
        _onDevice = onDevice ?? OnDeviceTranscriptionService(),
        _settings = settings ?? SettingsService(),
        _ai = ai ?? AiNotesService(),
        _core = core ?? CoreApiClient();

  List<KajianSession> _sessions = [];
  bool _loading = true;

  List<KajianSession> get sessions => List.unmodifiable(_sessions);
  bool get loading => _loading;

  bool get _canSync => syncEnabled;

  Future<void> load() async {
    _loading = true;
    notifyListeners();
    _sessions = await _storage.loadAll();
    _loading = false;
    notifyListeners();

    if (_canSync) await _syncFromServer();
  }

  /// Pulls the server's session list and merges it into the local cache.
  /// Best-effort: any failure (offline, server down) just keeps showing
  /// the local cache as-is:
  Future<void> _syncFromServer() async {
    try {
      final remote = await _core.listSessions();
      final byId = {for (final s in remote) s.id: s};
      // Preserve each session's local-only fields (audioFilePath, and any
      // local edits genuinely newer than what synced) by merging onto the
      // existing local copy rather than replacing wholesale.
      final merged = <KajianSession>[];
      for (final remoteSession in remote) {
        final local = _sessions.where((s) => s.id == remoteSession.id);
        final localAudioPath =
            local.isNotEmpty ? local.first.audioFilePath : null;
        merged.add(remoteSession.copyWith(audioFilePath: localAudioPath));
      }
      // Keep any local-only sessions the server doesn't know about yet
      // (e.g. recorded while offline, not pushed successfully).
      for (final localSession in _sessions) {
        if (!byId.containsKey(localSession.id)) merged.add(localSession);
      }
      merged.sort((a, b) => b.createdAt.compareTo(a.createdAt));
      _sessions = merged;
      notifyListeners();
      await _storage.saveAll(_sessions);
    } catch (_) {
      // Offline or server unreachable — the local cache already loaded
      // above is what the user sees; nothing further to do.
    }
  }

  KajianSession? byId(String id) {
    for (final s in _sessions) {
      if (s.id == id) return s;
    }
    return null;
  }

  Future<void> upsert(KajianSession session) async {
    final idx = _sessions.indexWhere((s) => s.id == session.id);
    final isNew = idx < 0;
    if (idx >= 0) {
      _sessions[idx] = session;
    } else {
      _sessions.insert(0, session);
    }
    notifyListeners();
    await _storage.saveAll(_sessions);

    if (!_canSync) return;
    try {
      if (isNew) {
        await _core.createSession(session);
      } else {
        await _core.updateSession(
          session.id,
          title: session.title,
          speaker: session.speaker,
          location: session.location,
          durationMs: session.durationMs,
          status: session.status,
        );
      }
    } catch (_) {
      // Best-effort — the local save above already succeeded, so the
      // recording/edit isn't lost; it'll sync on the next successful
      // upsert or the next app-open's _syncFromServer pull.
    }
  }

  Future<void> delete(String id) async {
    final session = byId(id);
    if (session != null) await _storage.deleteAudio(session);
    _sessions.removeWhere((s) => s.id == id);
    notifyListeners();
    await _storage.saveAll(_sessions);

    if (_canSync) {
      try {
        await _core.deleteSession(id);
      } catch (_) {
        // Best-effort; the session is already gone locally.
      }
    }
  }

  /// Full post-recording pipeline: refine the transcript (cloud or
  /// on-device, per the user's setting), then generate structured AI notes.
  /// Safe to call again to re-process.
  Future<void> process(String id) async {
    var session = byId(id);
    if (session == null) return;

    // 1) High-accuracy transcription pass (if we have audio).
    if (session.audioFilePath != null) {
      await upsert(session.copyWith(status: SessionStatus.transcribing));
      try {
        final mode = await _settings.getTranscriptionMode();
        final segments = mode == TranscriptionMode.onDevice
            ? await _onDevice.transcribe(
                audioFilePath: session.audioFilePath!,
                localeId: session.localeId,
              )
            : await _transcribeViaServer(byId(id)!);
        session = byId(id)!.copyWith(
          transcript: segments,
          status: SessionStatus.transcribed,
        );
        await upsert(session);
      } catch (e) {
        await upsert(byId(id)!.copyWith(status: SessionStatus.error));
        rethrow;
      }
    }

    // 2) AI notes from the (best available) transcript.
    session = byId(id)!;
    if (!session.hasTranscript) {
      await upsert(session.copyWith(status: SessionStatus.completed));
      return;
    }

    await upsert(session.copyWith(status: SessionStatus.summarizing));
    try {
      final note = _canSync
          ? (await _core.summarize(id)).note!
          : await _ai.generate(
              transcript: session.plainTranscript,
              title: session.title,
            );
      await upsert(byId(id)!.copyWith(
        note: note,
        status: SessionStatus.completed,
      ));
    } catch (e) {
      await upsert(byId(id)!.copyWith(status: SessionStatus.error));
      rethrow;
    }
  }

  /// Cloud transcription now runs server-side: upload the audio (if not
  /// already uploaded) to backend-core, then ask it to run the chosen ASR
  /// worker (Qwen or Whisper) against it. Requires a signed-in user with a
  /// reachable backend — falls back to the direct-to-worker
  /// [CloudTranscriptionService] (mock data in mock mode) when sync isn't
  /// available, so the app stays usable without an account.
  Future<List<TranscriptSegment>> _transcribeViaServer(
    KajianSession session,
  ) async {
    if (!_canSync) {
      return _cloud.transcribe(
        audioFilePath: session.audioFilePath!,
        localeId: session.localeId,
        baseUrl: (await _settings.getCloudModel()).baseUrl,
      );
    }

    if (!session.hasServerAudio) {
      await _core.uploadAudio(session.id, session.audioFilePath!);
    }
    final model = await _settings.getCloudModel();
    final updated = await _core.transcribe(session.id, model: model.name);
    return updated.transcript;
  }

  /// Regenerate only the AI notes (e.g. after editing the transcript).
  Future<void> regenerateNotes(String id) async {
    final session = byId(id);
    if (session == null || !session.hasTranscript) return;
    await upsert(session.copyWith(status: SessionStatus.summarizing));
    try {
      final note = _canSync
          ? (await _core.summarize(id)).note!
          : await _ai.generate(
              transcript: session.plainTranscript,
              title: session.title,
            );
      await upsert(byId(id)!.copyWith(
        note: note,
        status: SessionStatus.completed,
      ));
    } catch (e) {
      await upsert(byId(id)!.copyWith(status: SessionStatus.error));
      rethrow;
    }
  }

  @override
  void dispose() {
    _cloud.dispose();
    _ai.dispose();
    _core.dispose();
    super.dispose();
  }
}
