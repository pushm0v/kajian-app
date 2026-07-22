import 'package:flutter/foundation.dart';

import '../models/kajian_session.dart';
import '../services/ai_notes_service.dart';
import '../services/cloud_transcription_service.dart';
import '../services/on_device_transcription_service.dart';
import '../services/settings_service.dart';
import '../services/storage_service.dart';

/// Owns the list of saved kajian sessions and the post-recording processing
/// pipeline (transcription -> AI notes). The accurate transcription pass
/// runs against the cloud Whisper backend or fully on-device (whisper.cpp),
/// per the user's [TranscriptionMode] setting.
class SessionProvider extends ChangeNotifier {
  final StorageService _storage;
  final CloudTranscriptionService _cloud;
  final OnDeviceTranscriptionService _onDevice;
  final SettingsService _settings;
  final AiNotesService _ai;

  SessionProvider({
    StorageService? storage,
    CloudTranscriptionService? cloud,
    OnDeviceTranscriptionService? onDevice,
    SettingsService? settings,
    AiNotesService? ai,
  })  : _storage = storage ?? StorageService(),
        _cloud = cloud ?? CloudTranscriptionService(),
        _onDevice = onDevice ?? OnDeviceTranscriptionService(),
        _settings = settings ?? SettingsService(),
        _ai = ai ?? AiNotesService();

  List<KajianSession> _sessions = [];
  bool _loading = true;

  List<KajianSession> get sessions => List.unmodifiable(_sessions);
  bool get loading => _loading;

  Future<void> load() async {
    _loading = true;
    notifyListeners();
    _sessions = await _storage.loadAll();
    _loading = false;
    notifyListeners();
  }

  KajianSession? byId(String id) {
    for (final s in _sessions) {
      if (s.id == id) return s;
    }
    return null;
  }

  Future<void> upsert(KajianSession session) async {
    final idx = _sessions.indexWhere((s) => s.id == session.id);
    if (idx >= 0) {
      _sessions[idx] = session;
    } else {
      _sessions.insert(0, session);
    }
    notifyListeners();
    await _storage.saveAll(_sessions);
  }

  Future<void> delete(String id) async {
    final session = byId(id);
    if (session != null) await _storage.deleteAudio(session);
    _sessions.removeWhere((s) => s.id == id);
    notifyListeners();
    await _storage.saveAll(_sessions);
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
        // Cloud mode: route to the user's chosen backend (Qwen / Whisper).
        final cloudBaseUrl = mode == TranscriptionMode.cloud
            ? (await _settings.getCloudModel()).baseUrl
            : null;
        final segments = mode == TranscriptionMode.onDevice
            ? await _onDevice.transcribe(
                audioFilePath: session.audioFilePath!,
                localeId: session.localeId,
              )
            : await _cloud.transcribe(
                audioFilePath: session.audioFilePath!,
                localeId: session.localeId,
                baseUrl: cloudBaseUrl,
              );
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
      final note = await _ai.generate(
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

  /// Regenerate only the AI notes (e.g. after editing the transcript).
  Future<void> regenerateNotes(String id) async {
    final session = byId(id);
    if (session == null || !session.hasTranscript) return;
    await upsert(session.copyWith(status: SessionStatus.summarizing));
    try {
      final note = await _ai.generate(
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
    super.dispose();
  }
}
