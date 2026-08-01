"""Unit tests for JSON extraction and schema coercion — the parts that
run without vLLM or a GPU, and the parts most likely to break on real
model output.
"""

import pytest

from app.notes_model import _coerce, _extract_json


class TestExtractJson:
    def test_plain_json(self):
        assert _extract_json('{"summary": "hi"}') == {"summary": "hi"}

    def test_fenced_block(self):
        # Small instruct models wrap JSON in ```json fences far more often
        # than the system prompt's "ONLY a JSON object" would suggest.
        raw = '```json\n{"summary": "hi"}\n```'
        assert _extract_json(raw) == {"summary": "hi"}

    def test_unlabelled_fence(self):
        assert _extract_json('```\n{"summary": "hi"}\n```') == {"summary": "hi"}

    def test_surrounding_prose(self):
        raw = 'Here are the notes:\n{"summary": "hi"}\nHope this helps!'
        assert _extract_json(raw) == {"summary": "hi"}

    def test_malformed_raises(self):
        with pytest.raises(ValueError):
            _extract_json("not json at all")


class TestCoerce:
    def test_wellformed_passes_through(self):
        data = {
            "summary": "Tentang sabar.",
            "keyPoints": ["Sabar itu penting"],
            "topics": ["sabar"],
            "references": [
                {"type": "quran", "citation": "Al-Baqarah 2:153", "note": "tentang sabar"}
            ],
            "actionItems": ["Berlatih sabar"],
        }
        assert _coerce(data) == data

    def test_missing_keys_become_empty(self):
        # backend-core parses with .get() defaults, but a *missing* key and
        # a wrong-typed one behave differently there — normalise both here.
        out = _coerce({"summary": "only this"})
        assert out["summary"] == "only this"
        assert out["keyPoints"] == []
        assert out["references"] == []

    def test_string_where_list_expected(self):
        out = _coerce({"keyPoints": "just one point"})
        assert out["keyPoints"] == ["just one point"]

    def test_bare_string_reference(self):
        # Observed failure mode: the model emits citations as plain strings
        # instead of the {type, citation, note} objects the schema asks for.
        out = _coerce({"references": ["Al-Baqarah 2:153"]})
        assert out["references"] == [
            {"type": "quran", "citation": "Al-Baqarah 2:153", "note": None}
        ]

    def test_unknown_reference_type_defaults_to_quran(self):
        out = _coerce({"references": [{"type": "tafsir", "citation": "x"}]})
        assert out["references"][0]["type"] == "quran"

    def test_hadith_type_preserved(self):
        out = _coerce({"references": [{"type": "Hadith", "citation": "Bukhari 1"}]})
        assert out["references"][0]["type"] == "hadith"

    def test_references_without_citation_dropped(self):
        # An empty citation is worse than no reference — it renders as a
        # blank row in the app's notes view.
        out = _coerce({"references": [{"type": "quran", "citation": ""}]})
        assert out["references"] == []

    def test_nulls_filtered_from_lists(self):
        out = _coerce({"topics": ["sabar", None, "", "syukur"]})
        assert out["topics"] == ["sabar", "syukur"]

    def test_non_string_summary_stringified(self):
        out = _coerce({"summary": 42})
        assert out["summary"] == "42"

    def test_arabic_preserved(self):
        # The prompt asks for faithful Arabic; coercion must not mangle it.
        out = _coerce({
            "topics": ["صبر"],
            "references": [{"type": "quran", "citation": "البقرة ٢:١٥٣"}],
        })
        assert out["topics"] == ["صبر"]
        assert out["references"][0]["citation"] == "البقرة ٢:١٥٣"
