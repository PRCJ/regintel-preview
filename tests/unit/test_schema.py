import pytest

from schema import (
    SCORE_CRITICAL,
    SCORE_HIGH,
    SCORE_LOW,
    SCORE_MEDIUM,
    category_from_score,
    clamp_score,
    empty_score_fields,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    "score,expected",
    [
        (100, "critical"),
        (90, "critical"),
        (89, "high"),
        (75, "high"),
        (74, "medium"),
        (50, "medium"),
        (49, "low"),
        (25, "low"),
        (24, "not_relevant"),
        (0, "not_relevant"),
        (None, "not_relevant"),
        ("x", "not_relevant"),
        (89.6, "high"),
    ],
)
def test_category_from_score_bands(score, expected):
    assert category_from_score(score) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw,expected",
    [
        (101, 100),
        (-4, 0),
        (75.4, 75),
        ("88", 88),
        (None, 0),
        ("nope", 0),
    ],
)
def test_clamp_score(raw, expected):
    assert clamp_score(raw) == expected


@pytest.mark.unit
def test_empty_score_fields_pending():
    fields = empty_score_fields()
    assert fields["ai_status"] == "pending"
    assert fields["ai_relevance_score"] is None
    assert fields["sub_ministries"] == []


@pytest.mark.unit
def test_band_constants_match_compliguard():
    assert (SCORE_CRITICAL, SCORE_HIGH, SCORE_MEDIUM, SCORE_LOW) == (90, 75, 50, 25)
