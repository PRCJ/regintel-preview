import pytest

from eva_llm import get_client, is_placeholder_title, looks_like_form, model_name


@pytest.mark.unit
def test_placeholder_titles():
    assert is_placeholder_title("") is True
    assert is_placeholder_title("   ") is True
    assert is_placeholder_title("Personal Data Protection Law") is False


@pytest.mark.unit
def test_looks_like_form_underscores():
    assert looks_like_form("Application", "Name ______ Date ______ " * 8) is True


@pytest.mark.unit
def test_get_client_none_without_key(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("xai_api_key", raising=False)
    assert get_client() is None


@pytest.mark.unit
def test_model_name_default(monkeypatch):
    monkeypatch.delenv("XAI_MODEL", raising=False)
    assert model_name() == "grok-4.5"
