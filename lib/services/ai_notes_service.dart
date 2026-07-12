import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../core/config/app_config.dart';
import '../models/kajian_note.dart';

/// Generates structured [KajianNote]s from a transcript using an LLM.
///
/// Preferred path is your backend: POST {backendBaseUrl}/summarize with the
/// transcript; the backend calls Anthropic with its secret key and returns the
/// structured JSON. A DEV-only direct path to the Anthropic Messages API is
/// included for local testing (guarded by [AppConfig.devDirectProviderKey]).
///
/// In mock mode it returns realistic sample notes so the UI is fully testable.
class AiNotesService {
  final http.Client _client;
  AiNotesService({http.Client? client})
      : _client = client ?? http.Client();

  static const String _systemPrompt = '''
You are an assistant that turns a transcript of an Islamic lecture (kajian) into
concise, well-structured study notes. The transcript may mix Indonesian, Malay,
English and Arabic. Preserve Arabic terms and any Quran/Hadith citations
faithfully. Respond ONLY with a single JSON object, no prose, matching:
{
  "summary": string,               // 1-2 sentence overview
  "keyPoints": string[],           // main teaching points, in order
  "topics": string[],              // short thematic tags
  "references": [                  // Quran/Hadith mentioned
    { "type": "quran"|"hadith", "citation": string, "note": string|null }
  ],
  "actionItems": string[]          // practical takeaways for the listener
}''';

  Future<KajianNote> generate({
    required String transcript,
    String? title,
  }) async {
    if (transcript.trim().isEmpty) {
      return KajianNote(summary: '', generatedAt: DateTime.now());
    }
    if (AppConfig.isMockMode) {
      return _mockNote();
    }
    if (AppConfig.backendBaseUrl.isNotEmpty) {
      return _generateViaBackend(transcript: transcript, title: title);
    }
    return _generateDirect(transcript: transcript, title: title);
  }

  Future<KajianNote> _generateViaBackend({
    required String transcript,
    String? title,
  }) async {
    final uri = Uri.parse('${AppConfig.backendBaseUrl}/summarize');
    final response = await _client.post(
      uri,
      headers: {'content-type': 'application/json'},
      body: jsonEncode({
        'transcript': transcript,
        'title': title,
        'model': AppConfig.aiNotesModel,
      }),
    );
    if (response.statusCode != 200) {
      throw HttpException(
        'Summarize failed (${response.statusCode}): ${response.body}',
      );
    }
    final json = _extractJson(response.body);
    return KajianNote.fromJson(json..putIfAbsent('generatedAt',
        () => DateTime.now().toIso8601String()));
  }

  /// DEV ONLY — calls the Anthropic Messages API directly. Never ship this.
  Future<KajianNote> _generateDirect({
    required String transcript,
    String? title,
  }) async {
    final response = await _client.post(
      Uri.parse('https://api.anthropic.com/v1/messages'),
      headers: {
        'content-type': 'application/json',
        'x-api-key': AppConfig.devDirectProviderKey,
        'anthropic-version': '2023-06-01',
      },
      body: jsonEncode({
        'model': AppConfig.aiNotesModel,
        'max_tokens': 1500,
        'system': _systemPrompt,
        'messages': [
          {
            'role': 'user',
            'content': 'Kajian title: ${title ?? "(untitled)"}\n\n'
                'Transcript:\n$transcript',
          }
        ],
      }),
    );
    if (response.statusCode != 200) {
      throw HttpException(
        'Anthropic API error (${response.statusCode}): ${response.body}',
      );
    }
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    final content = (body['content'] as List).first as Map<String, dynamic>;
    final text = content['text'] as String;
    final json = _extractJson(text);
    return KajianNote.fromJson(json..putIfAbsent('generatedAt',
        () => DateTime.now().toIso8601String()));
  }

  /// Tolerant JSON extraction (handles fenced code blocks / stray prose).
  Map<String, dynamic> _extractJson(String raw) {
    var s = raw.trim();
    final fence = RegExp(r'```(?:json)?\s*([\s\S]*?)```');
    final m = fence.firstMatch(s);
    if (m != null) s = m.group(1)!.trim();
    final start = s.indexOf('{');
    final end = s.lastIndexOf('}');
    if (start >= 0 && end > start) s = s.substring(start, end + 1);
    return jsonDecode(s) as Map<String, dynamic>;
  }

  Future<KajianNote> _mockNote() async {
    await Future<void>.delayed(const Duration(seconds: 2));
    return KajianNote(
      summary:
          'Kajian tentang keutamaan sabar: definisi, jenis-jenisnya, dan dalil dari Al-Quran serta hadits.',
      keyPoints: const [
        'Sabar adalah menahan diri di atas ketaatan kepada Allah.',
        'Tiga jenis sabar: dalam ketaatan, menjauhi maksiat, dan atas takdir.',
        'Allah senantiasa bersama orang-orang yang sabar.',
      ],
      topics: const ['Sabar', 'Akhlak', 'Tazkiyatun Nafs'],
      references: const [
        ScriptureReference(
          type: 'quran',
          citation: 'Al-Baqarah: 153',
          note: 'Innallaha ma\'as-sabirin.',
        ),
        ScriptureReference(
          type: 'hadith',
          citation: 'HR. Muslim',
          note: 'Sabar itu cahaya (as-sabru dhiya\').',
        ),
      ],
      actionItems: const [
        'Latih kesabaran saat menghadapi ujian sehari-hari.',
        'Perbanyak istighfar dan doa memohon kesabaran.',
      ],
      generatedAt: DateTime.now(),
    );
  }

  void dispose() => _client.close();
}
