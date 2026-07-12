import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

import '../core/constants/app_constants.dart';
import '../models/kajian_session.dart';

/// Simple JSON-file persistence for kajian sessions.
///
/// Dependency-light and easy to reason about. For very large libraries you may
/// later swap this for sqflite/Drift — the [SessionProvider] only depends on
/// this small interface, so the migration is localised.
class StorageService {
  Future<File> _file() async {
    final dir = await getApplicationDocumentsDirectory();
    return File('${dir.path}/${AppConstants.sessionsStorageFile}');
  }

  Future<List<KajianSession>> loadAll() async {
    try {
      final file = await _file();
      if (!await file.exists()) return [];
      final raw = await file.readAsString();
      if (raw.trim().isEmpty) return [];
      final list = jsonDecode(raw) as List;
      final sessions = list
          .map((e) => KajianSession.fromJson(e as Map<String, dynamic>))
          .toList();
      sessions.sort((a, b) => b.createdAt.compareTo(a.createdAt));
      return sessions;
    } catch (_) {
      return [];
    }
  }

  Future<void> saveAll(List<KajianSession> sessions) async {
    final file = await _file();
    final data = jsonEncode(sessions.map((s) => s.toJson()).toList());
    await file.writeAsString(data);
  }

  /// Delete the audio file associated with a session, if present.
  Future<void> deleteAudio(KajianSession session) async {
    final path = session.audioFilePath;
    if (path == null) return;
    final f = File(path);
    if (await f.exists()) await f.delete();
  }
}
