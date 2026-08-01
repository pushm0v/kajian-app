import 'dart:io';

import 'package:flutter/foundation.dart';

import '../models/kajian_note.dart';
import '../models/kajian_session.dart';
import '../models/transcript_segment.dart';
import '../services/ai_notes_service.dart';
import '../services/cloud_transcription_service.dart';
import '../services/core_api_client.dart';
import '../services/settings_service.dart';
import '../services/storage_service.dart';

/// Thrown when AI notes can't be produced because the summarizer is
/// switched off or unreachable — as opposed to failing on a given
/// transcript.
///
/// Kept distinct so the UI can degrade instead of erroring: the
/// transcript is the primary product and is already saved by the time
/// summarization runs, so an outage here leaves a perfectly usable
/// session. See backend-core's notes.NotesUnavailable, the server-side
/// counterpart.
class NotesUnavailable implements Exception {
  final String message;
  const NotesUnavailable(this.message);

  @override
  String toString() => message;
}

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
/// cloud backend, proxied through backend-core, which then talks to the
/// Qwen/Whisper ASR workers. On-device (whisper.cpp) transcription was
/// removed: the small `base` model it downloaded to the phone was
/// meaningfully worse than the self-hosted large-v3 behind the backend.
class SessionProvider extends ChangeNotifier {
  final StorageService _storage;
  final CloudTranscriptionService _cloud;
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
    SettingsService? settings,
    AiNotesService? ai,
    CoreApiClientBase? core,
    this.syncEnabled = false,
  })  : _storage = storage ?? StorageService(),
        _cloud = cloud ?? CloudTranscriptionService(),
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

  /// Full post-recording pipeline: refine the transcript via the cloud
  /// backend, then generate structured AI notes. Safe to call again to
  /// re-process.
  Future<void> process(String id) async {
    var session = byId(id);
    if (session == null) return;

    // 1) High-accuracy transcription pass (if we have audio).
    if (session.audioFilePath != null) {
      await upsert(session.copyWith(status: SessionStatus.transcribing));
      try {
        final segments = await _transcribeViaServer(byId(id)!);
        session = byId(id)!.copyWith(
          transcript: segments,
          status: SessionStatus.transcribed,
        );
        await upsert(session);
      } catch (e) {
        await upsert(byId(id)!.copyWith(
          status: SessionStatus.error,
          errorMessage: _reasonFrom(e),
        ));
        rethrow;
      }
    }

    // 2) AI notes from the (best available) transcript.
    //
    // Bail out if transcription produced nothing. Summarizing an empty
    // transcript is rejected server-side with a 400 ("Session has no
    // transcript yet"), which reaches the user as a raw HTTP error that
    // says nothing about what to do — so this stops here instead, and
    // reports it as the failure it is rather than marking the session
    // `completed` as it once did.
    session = byId(id)!;
    if (!session.hasTranscript) {
      await upsert(session.copyWith(
        status: SessionStatus.error,
        errorMessage: session.errorMessage ??
            'Transcription produced no text, so there is nothing to '
                'summarize. Try transcribing again.',
      ));
      return;
    }

    await upsert(session.copyWith(status: SessionStatus.summarizing));
    try {
      final note = await _generateNote(id, session);
      await upsert(byId(id)!.copyWith(
        note: note,
        status: SessionStatus.completed,
        clearErrorMessage: true,
      ));
    } on NotesUnavailable catch (e) {
      // Not a failure: the recording transcribed fine and is readable.
      // Settle at `transcribed` with the reason attached so NotesView can
      // explain itself, and don't rethrow — there's nothing for the user
      // to fix, and a toast would misrepresent a working session.
      await upsert(byId(id)!.copyWith(
        status: SessionStatus.transcribed,
        errorMessage: e.message,
      ));
    } catch (e) {
      await upsert(byId(id)!.copyWith(
        status: SessionStatus.error,
        errorMessage: _reasonFrom(e),
      ));
      rethrow;
    }
  }

  /// Generates notes via the server (when syncing) or on-device AI.
  ///
  /// The server path returns the whole session; its `note` is non-null on
  /// success but the field is nullable, so a null here means the job
  /// reported success without producing one. That used to be a bare `!`,
  /// which surfaced as an opaque null-check crash — this reports it as the
  /// server-side problem it actually is.
  Future<KajianNote> _generateNote(String id, KajianSession session) async {
    if (!_canSync) {
      return _ai.generate(
        transcript: session.plainTranscript,
        title: session.title,
      );
    }
    final updated = await _core.summarize(id);
    final note = updated.note;
    if (note == null) {
      // The server settles a session back to `transcribed` (not `error`)
      // when the summarizer is off or down — notes are secondary and the
      // transcript is already saved. Preserve that distinction here rather
      // than overwriting it with `error`, so the notes tab can say
      // "unavailable" and offer a retry.
      if (updated.status == SessionStatus.transcribed) {
        throw NotesUnavailable(
          updated.errorMessage ?? 'AI notes are unavailable right now.',
        );
      }
      throw StateError(
        updated.errorMessage ??
            'The server finished summarizing but returned no notes.',
      );
    }
    return note;
  }

  /// Unwraps an exception into something worth showing a user.
  ///
  /// Errors from [CoreApiClient] are already the server's own
  /// `error_message` (see its _pollUntilDone), so the wrapper text that
  /// `toString()` prepends — "HttpException: " — is noise here.
  static String _reasonFrom(Object e) {
    final raw = e is HttpException
        ? e.message
        : e is StateError
            ? e.message
            : e.toString();
    return raw.trim().isEmpty ? 'Something went wrong.' : raw.trim();
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
    if (session == null) return;
    // Throw rather than return silently: this is user-initiated (the
    // "regenerate" button), so doing nothing at all looks like the button
    // is broken. The server would reject it with a 400 anyway.
    if (!session.hasTranscript) {
      throw StateError(
        'This session has no transcript yet, so there is nothing to '
        'summarize.',
      );
    }
    await upsert(session.copyWith(status: SessionStatus.summarizing));
    try {
      final note = await _generateNote(id, session);
      await upsert(byId(id)!.copyWith(
        note: note,
        status: SessionStatus.completed,
        clearErrorMessage: true,
      ));
    } on NotesUnavailable catch (e) {
      // Not a failure: the recording transcribed fine and is readable.
      // Settle at `transcribed` with the reason attached so NotesView can
      // explain itself, and don't rethrow — there's nothing for the user
      // to fix, and a toast would misrepresent a working session.
      await upsert(byId(id)!.copyWith(
        status: SessionStatus.transcribed,
        errorMessage: e.message,
      ));
    } catch (e) {
      await upsert(byId(id)!.copyWith(
        status: SessionStatus.error,
        errorMessage: _reasonFrom(e),
      ));
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
