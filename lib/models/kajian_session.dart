import 'kajian_note.dart';
import 'transcript_segment.dart';

/// Lifecycle status of a kajian session.
enum SessionStatus {
  recording,
  recorded,
  transcribing,
  transcribed,
  summarizing,
  completed,
  error,
}

extension SessionStatusLabel on SessionStatus {
  String get label => switch (this) {
        SessionStatus.recording => 'Recording',
        SessionStatus.recorded => 'Recorded',
        SessionStatus.transcribing => 'Transcribing…',
        SessionStatus.transcribed => 'Transcribed',
        SessionStatus.summarizing => 'Generating notes…',
        SessionStatus.completed => 'Completed',
        SessionStatus.error => 'Error',
      };

  bool get isBusy =>
      this == SessionStatus.transcribing || this == SessionStatus.summarizing;
}

/// A recorded kajian: audio + transcript + AI notes + metadata.
class KajianSession {
  final String id;
  final String title;
  final String? speaker; // ustadz / lecturer
  final String? location; // masjid / venue
  final DateTime createdAt;
  final int durationMs;

  /// Local file path to the recorded audio (may be null if discarded).
  final String? audioFilePath;

  /// BCP-47 / locale id used for transcription, e.g. "id_ID".
  final String localeId;

  final List<TranscriptSegment> transcript;
  final KajianNote? note;
  final SessionStatus status;

  const KajianSession({
    required this.id,
    required this.title,
    this.speaker,
    this.location,
    required this.createdAt,
    this.durationMs = 0,
    this.audioFilePath,
    required this.localeId,
    this.transcript = const [],
    this.note,
    this.status = SessionStatus.recorded,
  });

  /// Full transcript joined into a single plain-text string.
  String get plainTranscript =>
      transcript.map((s) => s.text.trim()).where((t) => t.isNotEmpty).join(' ');

  bool get hasTranscript => transcript.isNotEmpty;
  bool get hasNotes => note != null;

  KajianSession copyWith({
    String? title,
    String? speaker,
    String? location,
    int? durationMs,
    String? audioFilePath,
    String? localeId,
    List<TranscriptSegment>? transcript,
    KajianNote? note,
    SessionStatus? status,
  }) {
    return KajianSession(
      id: id,
      title: title ?? this.title,
      speaker: speaker ?? this.speaker,
      location: location ?? this.location,
      createdAt: createdAt,
      durationMs: durationMs ?? this.durationMs,
      audioFilePath: audioFilePath ?? this.audioFilePath,
      localeId: localeId ?? this.localeId,
      transcript: transcript ?? this.transcript,
      note: note ?? this.note,
      status: status ?? this.status,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'title': title,
        'speaker': speaker,
        'location': location,
        'createdAt': createdAt.toIso8601String(),
        'durationMs': durationMs,
        'audioFilePath': audioFilePath,
        'localeId': localeId,
        'transcript': transcript.map((s) => s.toJson()).toList(),
        'note': note?.toJson(),
        'status': status.name,
      };

  factory KajianSession.fromJson(Map<String, dynamic> json) {
    return KajianSession(
      id: json['id'] as String,
      title: json['title'] as String? ?? 'Untitled Kajian',
      speaker: json['speaker'] as String?,
      location: json['location'] as String?,
      createdAt:
          DateTime.tryParse(json['createdAt'] as String? ?? '') ??
              DateTime.now(),
      durationMs: (json['durationMs'] as num?)?.toInt() ?? 0,
      audioFilePath: json['audioFilePath'] as String?,
      localeId: json['localeId'] as String? ?? 'id_ID',
      transcript: (json['transcript'] as List?)
              ?.map((e) =>
                  TranscriptSegment.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      note: json['note'] == null
          ? null
          : KajianNote.fromJson(json['note'] as Map<String, dynamic>),
      status: SessionStatus.values.firstWhere(
        (s) => s.name == json['status'],
        orElse: () => SessionStatus.recorded,
      ),
    );
  }
}
