/// A single chunk of transcribed speech with timing information.
class TranscriptSegment {
  final String id;
  final String text;

  /// Offset from the start of the recording.
  final int startMs;
  final int endMs;

  /// Optional speaker label (e.g. "Ustadz", "Audience") when diarization is
  /// available. Null when unknown.
  final String? speaker;

  /// Whether this is a finalized segment (from cloud) vs a live/interim guess.
  final bool isFinal;

  const TranscriptSegment({
    required this.id,
    required this.text,
    required this.startMs,
    this.endMs = 0,
    this.speaker,
    this.isFinal = true,
  });

  TranscriptSegment copyWith({
    String? text,
    int? startMs,
    int? endMs,
    String? speaker,
    bool? isFinal,
  }) {
    return TranscriptSegment(
      id: id,
      text: text ?? this.text,
      startMs: startMs ?? this.startMs,
      endMs: endMs ?? this.endMs,
      speaker: speaker ?? this.speaker,
      isFinal: isFinal ?? this.isFinal,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'text': text,
        'startMs': startMs,
        'endMs': endMs,
        'speaker': speaker,
        'isFinal': isFinal,
      };

  factory TranscriptSegment.fromJson(Map<String, dynamic> json) {
    return TranscriptSegment(
      id: json['id'] as String,
      text: json['text'] as String,
      startMs: (json['startMs'] as num?)?.toInt() ?? 0,
      endMs: (json['endMs'] as num?)?.toInt() ?? 0,
      speaker: json['speaker'] as String?,
      isFinal: json['isFinal'] as bool? ?? true,
    );
  }
}
