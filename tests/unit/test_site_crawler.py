import pytest

from site_crawler import base_domain, has_doc_extension, is_same_site, looks_like_empty_shell


@pytest.mark.unit
def test_base_domain_strips_www():
    assert base_domain("www.SDAIA.gov.sa") == "sdaia.gov.sa"


@pytest.mark.unit
def test_same_site_subdomain_and_alias():
    assert is_same_site("docs.sdaia.gov.sa", "sdaia.gov.sa")
    assert is_same_site("dgp.sdaia.gov.sa", "sdaia.gov.sa")
    assert is_same_site("rulebook.sama.gov.sa", "sama.gov.sa")
    assert is_same_site("laws.moj.gov.sa", "moj.gov.sa")


@pytest.mark.unit
def test_same_site_rejects_sibling_gov_sa():
    assert is_same_site("other.gov.sa", "momah.gov.sa") is False
    assert is_same_site("", "sdaia.gov.sa") is False


@pytest.mark.unit
@pytest.mark.parametrize(
    "url",
    [
        "https://x.example/a.pdf",
        "https://socpa.org.sa/getattachment/foo/file.pdf.aspx",
        "https://host/getattachment/abc/report.pdf",
    ],
)
def test_has_doc_extension_pdf_variants(url):
    assert has_doc_extension(url) is True


@pytest.mark.unit
def test_has_doc_extension_html_false():
    assert has_doc_extension("https://sdaia.gov.sa/en/about") is False
    assert has_doc_extension("") is False


@pytest.mark.unit
def test_empty_shell_short_or_spa():
    assert looks_like_empty_shell("") is True
    assert looks_like_empty_shell("<html><div id='root'></div></html>") is True
    fat = "<html><body>" + ("<a href='/x'>link</a>" * 20) + ("x" * 2000) + "</body></html>"
    assert looks_like_empty_shell(fat) is False
