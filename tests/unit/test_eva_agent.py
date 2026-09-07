import pytest

from eva_agent import is_meta_question, load_summaries


@pytest.mark.unit
@pytest.mark.parametrize(
    "q,expected",
    [
        ("hello", True),
        ("status", True),
        ("how many PDFs do you have?", True),
        ("are you indexing more documents?", True),
        ("What does the PDPL require of controllers?", False),
        ("", False),
    ],
)
def test_is_meta_question(q, expected):
    assert is_meta_question(q) is expected


@pytest.mark.unit
def test_load_summaries_returns_list_with_text():
    rows = load_summaries()
    assert isinstance(rows, list)
    if rows:
        assert any((r.get("summary") or "").strip() for r in rows)
