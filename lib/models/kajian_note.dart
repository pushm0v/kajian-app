/// A scriptural reference detected in the kajian (Quran ayah or Hadith).
class ScriptureReference {
  /// "quran" or "hadith".
  final String type;

  /// e.g. "Al-Baqarah: 183" or "HR. Bukhari no. 1".
  final String citation;

  /// Short context/quote of how it was used, if available.
  final String? note;

  const ScriptureReference({
    required this.type,
    required this.citation,
    this.note,
  });

  Map<String, dynamic> toJson() => {
        'type': type,
        'citation': citation,
        'note': note,
      };

  factory ScriptureReference.fromJson(Map<String, dynamic> json) {
    return ScriptureReference(
      type: json['type'] as String? ?? 'quran',
      citation: json['citation'] as String? ?? '',
      note: json['note'] as String?,
    );
  }
}

/// The AI-generated, structured notes for a kajian session.
class KajianNote {
  /// One or two sentence overview.
  final String summary;

  /// The main teaching points, in order.
  final List<String> keyPoints;

  /// High-level topics / themes (for tagging & search).
  final List<String> topics;

  /// Quran/Hadith references mentioned.
  final List<ScriptureReference> references;

  /// Practical takeaways / action items for the listener.
  final List<String> actionItems;

  /// When these notes were generated.
  final DateTime generatedAt;

  const KajianNote({
    required this.summary,
    this.keyPoints = const [],
    this.topics = const [],
    this.references = const [],
    this.actionItems = const [],
    required this.generatedAt,
  });

  Map<String, dynamic> toJson() => {
        'summary': summary,
        'keyPoints': keyPoints,
        'topics': topics,
        'references': references.map((r) => r.toJson()).toList(),
        'actionItems': actionItems,
        'generatedAt': generatedAt.toIso8601String(),
      };

  factory KajianNote.fromJson(Map<String, dynamic> json) {
    return KajianNote(
      summary: json['summary'] as String? ?? '',
      keyPoints: (json['keyPoints'] as List?)?.cast<String>() ?? const [],
      topics: (json['topics'] as List?)?.cast<String>() ?? const [],
      references: (json['references'] as List?)
              ?.map((e) =>
                  ScriptureReference.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      actionItems: (json['actionItems'] as List?)?.cast<String>() ?? const [],
      generatedAt:
          DateTime.tryParse(json['generatedAt'] as String? ?? '') ??
              DateTime.now(),
    );
  }
}
