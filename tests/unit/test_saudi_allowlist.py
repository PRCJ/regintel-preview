import pytest

from saudi_ministry_allowlist import ALLOWED_HOST_MARKERS, AUTHORITIES


@pytest.mark.unit
def test_core_authorities_present():
    codes = {a["code"] for a in AUTHORITIES}
    for needed in ("SDAIA", "MEWA", "MOJ", "ZATCA", "SAMA"):
        assert needed in codes


@pytest.mark.unit
def test_host_markers_cover_sdaia_family():
    joined = " ".join(ALLOWED_HOST_MARKERS)
    assert "sdaia.gov.sa" in joined
    assert "dgp.sdaia" in joined


@pytest.mark.unit
def test_authority_urls_are_https():
    for a in AUTHORITIES:
        assert a["url"].startswith("https://")
        assert a["code"]
        assert a["label"].startswith("Saudi Arabia")
