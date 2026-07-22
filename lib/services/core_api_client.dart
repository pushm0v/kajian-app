import 'dart:convert';
import 'dart:io';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:http/http.dart' as http;

import '../core/config/app_config.dart';
import '../models/kajian_note.dart';
import '../models/kajian_session.dart';
import '../models/transcript_segment.dart';

/// Minimal surface [SessionProvider] depends on. Lets tests inject a pure-
/// Dart fake instead of making real HTTP calls / requiring Firebase to be
/// initialized (mirrors [AuthServiceBase]'s role for [AuthService]).
abstract class CoreApiClientBase {
  Future<List<KajianSession>> listSessions();
  Future<KajianSession> createSession(KajianSession session);
  Future<KajianSession> updateSession(
    String id, {
    String? title,
    String? speaker,
    String? location,
    int? durationMs,
    SessionStatus? status,
  });
  Future<void> deleteSession(String id);
  Future<KajianSession> replaceTranscript(
    String sessionId,
    List<TranscriptSegment> segments,
  );
  Future<KajianSession> replaceNote(String sessionId, KajianNote note);
  Future<KajianSession> uploadAudio(String sessionId, String audioFilePath);
  Future<String> getAudioDownloadUrl(String sessionId);
  Future<KajianSession> transcribe(String sessionId, {required String model});
  Future<KajianSession> summarize(String sessionId, {String? model});
  void dispose();
}

/// Talks to backend-core/ — the platform API that owns sessions,
/// transcripts, notes, and audio storage (as opposed to
/// CloudTranscriptionService/AiNotesService, which used to call the ASR
/// workers and Anthropic directly from the device; those now happen
/// server-side via this client's [transcribe]/[summarize]).
///
/// Every request carries the signed-in user's Firebase ID token as a
/// bearer token — backend-core verifies it and maps it to a local user row
/// (see backend-core/app/auth.py). Throws [StateError] if called while
/// signed out; callers are expected to only reach this after
/// AuthProvider.status is AuthStatus.signedIn.
class CoreApiClient implements CoreApiClientBase {
  final http.Client _client;
  CoreApiClient({http.Client? client}) : _client = client ?? http.Client();

  Future<String> _authHeader() async {
    final user = FirebaseAuth.instance.currentUser;
    if (user == null) {
      throw StateError('CoreApiClient called while signed out.');
    }
    final token = await user.getIdToken();
    return 'Bearer $token';
  }

  Uri _uri(String path) => Uri.parse('${AppConfig.backendBaseUrl}$path');

  Future<Map<String, String>> _jsonHeaders() async => {
        'Authorization': await _authHeader(),
        'Content-Type': 'application/json',
      };

  void _checkOk(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) return;
    throw HttpException(
      'backend-core request failed (${response.statusCode}): ${response.body}',
    );
  }

  @override
  Future<List<KajianSession>> listSessions() async {
    final response = await _client.get(
      _uri('/sessions'),
      headers: await _jsonHeaders(),
    );
    _checkOk(response);
    final list = jsonDecode(response.body) as List;
    return list
        .map((e) => _sessionFromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<KajianSession> createSession(KajianSession session) async {
    final response = await _client.post(
      _uri('/sessions'),
      headers: await _jsonHeaders(),
      body: jsonEncode({
        'id': session.id,
        'title': session.title,
        'speaker': session.speaker,
        'location': session.location,
        'createdAt': session.createdAt.toIso8601String(),
        'durationMs': session.durationMs,
        'localeId': session.localeId,
        'status': session.status.name,
      }),
    );
    _checkOk(response);
    return _sessionFromJson(jsonDecode(response.body) as Map<String, dynamic>);
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
    final response = await _client.patch(
      _uri('/sessions/$id'),
      headers: await _jsonHeaders(),
      body: jsonEncode({
        if (title != null) 'title': title,
        if (speaker != null) 'speaker': speaker,
        if (location != null) 'location': location,
        if (durationMs != null) 'durationMs': durationMs,
        if (status != null) 'status': status.name,
      }),
    );
    _checkOk(response);
    return _sessionFromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  @override
  Future<void> deleteSession(String id) async {
    final response = await _client.delete(
      _uri('/sessions/$id'),
      headers: await _jsonHeaders(),
    );
    if (response.statusCode != 204) _checkOk(response);
  }

  @override
  Future<KajianSession> replaceTranscript(
    String sessionId,
    List<TranscriptSegment> segments,
  ) async {
    final response = await _client.put(
      _uri('/sessions/$sessionId/transcript'),
      headers: await _jsonHeaders(),
      body: jsonEncode({
        'segments': segments.map((s) => s.toJson()).toList(),
      }),
    );
    _checkOk(response);
    return _sessionFromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  @override
  Future<KajianSession> replaceNote(String sessionId, KajianNote note) async {
    final response = await _client.put(
      _uri('/sessions/$sessionId/note'),
      headers: await _jsonHeaders(),
      body: jsonEncode({
        'summary': note.summary,
        'keyPoints': note.keyPoints,
        'topics': note.topics,
        'references': note.references.map((r) => r.toJson()).toList(),
        'actionItems': note.actionItems,
      }),
    );
    _checkOk(response);
    return _sessionFromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  /// Uploads [audioFilePath] for [sessionId]: gets a presigned URL from
  /// backend-core, PUTs the file directly to the object store (not
  /// through backend-core's own bandwidth), then confirms the upload.
  @override
  Future<KajianSession> uploadAudio(String sessionId, String audioFilePath) async {
    final urlResponse = await _client.post(
      _uri('/sessions/$sessionId/audio-upload-url'),
      headers: await _jsonHeaders(),
    );
    _checkOk(urlResponse);
    final uploadUrl =
        (jsonDecode(urlResponse.body) as Map<String, dynamic>)['uploadUrl'] as String;

    final file = File(audioFilePath);
    final putResponse = await _client.put(
      Uri.parse(uploadUrl),
      body: await file.readAsBytes(),
    );
    if (putResponse.statusCode < 200 || putResponse.statusCode >= 300) {
      throw HttpException(
        'Audio upload failed (${putResponse.statusCode}): ${putResponse.body}',
      );
    }

    final confirmResponse = await _client.post(
      _uri('/sessions/$sessionId/audio-confirm'),
      headers: await _jsonHeaders(),
    );
    _checkOk(confirmResponse);
    return _sessionFromJson(
      jsonDecode(confirmResponse.body) as Map<String, dynamic>,
    );
  }

  @override
  Future<String> getAudioDownloadUrl(String sessionId) async {
    final response = await _client.get(
      _uri('/sessions/$sessionId/audio-url'),
      headers: await _jsonHeaders(),
    );
    _checkOk(response);
    return (jsonDecode(response.body) as Map<String, dynamic>)['downloadUrl']
        as String;
  }

  /// Runs the server-side ASR proxy against this session's already-
  /// uploaded audio. [model] is "qwen" or "whisper" — matches
  /// [CloudModel.name].
  @override
  Future<KajianSession> transcribe(String sessionId, {required String model}) async {
    final response = await _client.post(
      _uri('/sessions/$sessionId/transcribe'),
      headers: await _jsonHeaders(),
      body: jsonEncode({'model': model}),
    );
    _checkOk(response);
    return _sessionFromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  @override
  Future<KajianSession> summarize(String sessionId, {String? model}) async {
    final response = await _client.post(
      _uri('/sessions/$sessionId/summarize'),
      headers: await _jsonHeaders(),
      body: jsonEncode({if (model != null) 'model': model}),
    );
    _checkOk(response);
    return _sessionFromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  KajianSession _sessionFromJson(Map<String, dynamic> json) {
    return KajianSession(
      id: json['id'] as String,
      title: json['title'] as String,
      speaker: json['speaker'] as String?,
      location: json['location'] as String?,
      createdAt: DateTime.parse(json['createdAt'] as String),
      durationMs: (json['durationMs'] as num?)?.toInt() ?? 0,
      // Local audio file path is a device-side concern (StorageService's
      // local cache) — the server reports hasAudio, not a raw path/URL,
      // since a fresh presigned URL must be requested each time audio is
      // actually needed (see getAudioDownloadUrl). Callers that already
      // know the local path (e.g. right after recording, before the first
      // sync) should carry it forward themselves rather than relying on
      // this parse to know it.
      audioFilePath: null,
      hasServerAudio: json['hasAudio'] as bool? ?? false,
      localeId: json['localeId'] as String? ?? 'id_ID',
      transcript: (json['transcript'] as List? ?? [])
          .map((e) => TranscriptSegment.fromJson(e as Map<String, dynamic>))
          .toList(),
      note: json['note'] == null
          ? null
          : KajianNote.fromJson(json['note'] as Map<String, dynamic>),
      status: SessionStatus.values.firstWhere(
        (s) => s.name == json['status'],
        orElse: () => SessionStatus.recorded,
      ),
    );
  }

  @override
  void dispose() => _client.close();
}
