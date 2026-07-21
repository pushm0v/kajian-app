"""Unit tests for language-code normalization — no model/GPU required."""

from app.asr_model import WhisperModelWrapper


def test_normalize_language_maps_bcp47_locale_to_bare_code():
    wrapper = WhisperModelWrapper()
    assert wrapper.normalize_language("id_ID") == "id"
    assert wrapper.normalize_language("ar-SA") == "ar"


def test_normalize_language_returns_none_for_missing_or_unknown():
    wrapper = WhisperModelWrapper()
    assert wrapper.normalize_language(None) is None
    assert wrapper.normalize_language("") is None
    assert wrapper.normalize_language("xx_XX") is None
