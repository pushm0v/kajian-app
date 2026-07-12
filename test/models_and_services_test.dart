import 'package:flutter_test/flutter_test.dart';
import 'package:kajian_app/models/kajian_note.dart';
import 'package:kajian_app/models/kajian_session.dart';
import 'package:kajian_app/models/transcript_segment.dart';
import 'package:kajian_app/services/ai_notes_service.dart';
import 'package:kajian_app/services/cloud_transcription_service.dart';

void main() {
  group('Model serialization', () {
    test('KajianSession round-trips through JSON', () {
      final session = KajianSession(
        id: 'abc',
        title: 'Kajian Sabar',
        speaker: 'Ustadz Fulan',
        location: 'Masjid Al-Hikmah',
        createdAt: DateTime(2026, 7, 12, 19, 30),
        durationMs: 3_600_000,
        audioFilePath: '/tmp/kajian_abc.m4a',
        localeId: 'id_ID',
        transcript: const [
          TranscriptSegment(id: 's0', text: 'Bismillah', startMs: 0, endMs: 1000),
        ],
        note: KajianNote(
          summary: 'Tentang sabar',
          keyPoints: const ['Poin 1'],
          topics: const ['Sabar'],
          references: const [
            ScriptureReference(type: 'quran', citation: 'Al-Baqarah: 153'),
          ],
          actionItems: const ['Latih sabar'],
          generatedAt: DateTime(2026, 7, 12, 20, 0),
        ),
        status: SessionStatus.completed,
      );

      final restored = KajianSession.fromJson(session.toJson());

      expect(restored.id, session.id);
      expect(restored.title, session.title);
      expect(restored.speaker, session.speaker);
      expect(restored.durationMs, session.durationMs);
      expect(restored.transcript.length, 1);
      expect(restored.note?.references.first.citation, 'Al-Baqarah: 153');
      expect(restored.status, SessionStatus.completed);
    });

    test('plainTranscript joins segment text', () {
      final session = KajianSession(
        id: 'x',
        title: 't',
        createdAt: DateTime(2026),
        localeId: 'id_ID',
        transcript: const [
          TranscriptSegment(id: '0', text: 'Hello', startMs: 0),
          TranscriptSegment(id: '1', text: 'World', startMs: 1000),
        ],
      );
      expect(session.plainTranscript, 'Hello World');
    });
  });

  group('Mock services (no backend configured)', () {
    test('CloudTranscriptionService returns mock segments', () async {
      final segments = await CloudTranscriptionService()
          .transcribe(audioFilePath: '/tmp/x.m4a', localeId: 'id_ID');
      expect(segments, isNotEmpty);
      expect(segments.first.text, isNotEmpty);
    });

    test('AiNotesService returns mock structured notes', () async {
      final note = await AiNotesService()
          .generate(transcript: 'kajian tentang sabar', title: 'Sabar');
      expect(note.summary, isNotEmpty);
      expect(note.keyPoints, isNotEmpty);
      expect(note.references, isNotEmpty);
    });

    test('AiNotesService returns empty note for empty transcript', () async {
      final note = await AiNotesService().generate(transcript: '   ');
      expect(note.summary, isEmpty);
    });
  });
}
