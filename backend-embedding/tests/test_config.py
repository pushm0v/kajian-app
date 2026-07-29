"""Model-selection resolution — the one piece of config with real logic."""

import importlib

import pytest


def _reload_config(monkeypatch, **env):
    for k, v in env.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)
    from app import config
    return importlib.reload(config)


def test_defaults_to_bilingual_campplus(monkeypatch):
    config = _reload_config(monkeypatch, EMBEDDING_MODEL=None, EMBEDDING_MODEL_PATH=None)
    assert config.MODEL_NAME == "campplus"
    # The default must stay the multilingual checkpoint — every other
    # option in sherpa-onnx's zoo is monolingual, which measurably
    # degrades on cross-language audio (this app transcribes Indonesian).
    assert "zh_en" in config.MODEL_PATH


def test_selects_eres2netv2_by_name(monkeypatch):
    config = _reload_config(
        monkeypatch, EMBEDDING_MODEL="eres2netv2", EMBEDDING_MODEL_PATH=None
    )
    assert config.MODEL_PATH.endswith(config.MODELS["eres2netv2"])


def test_explicit_path_wins(monkeypatch):
    config = _reload_config(
        monkeypatch, EMBEDDING_MODEL="campplus", EMBEDDING_MODEL_PATH="/custom/m.onnx"
    )
    assert config.MODEL_PATH == "/custom/m.onnx"


def test_unknown_model_name_raises(monkeypatch):
    with pytest.raises(ValueError, match="Unknown EMBEDDING_MODEL"):
        _reload_config(monkeypatch, EMBEDDING_MODEL="nope", EMBEDDING_MODEL_PATH=None)


def test_provider_defaults_to_cuda(monkeypatch):
    # This service exists to run embedding on its own GPU; defaulting to
    # cpu here would silently undo that.
    config = _reload_config(monkeypatch, EMBEDDING_PROVIDER=None)
    assert config.PROVIDER == "cuda"
