import pytest

from pdf_relevance import is_junk_page, is_regulatory_pdf, regulatory_score


@pytest.mark.unit
def test_law_title_scores_keep():
    score = regulatory_score(
        url="https://sdaia.gov.sa/en/laws/pdpl.pdf",
        title="Personal Data Protection Law",
        filename="PersonalDataProtectionLaw.pdf",
    )
    assert score >= 15
    assert is_regulatory_pdf(url="https://sdaia.gov.sa/en/laws/pdpl.pdf", title="Personal Data Protection Law")


@pytest.mark.unit
def test_workshop_rejected():
    score = regulatory_score(title="IoT workshop brochure", filename="workshop.pdf")
    assert score < 0


@pytest.mark.unit
def test_empty_blob_zero():
    assert regulatory_score() == 0


@pytest.mark.unit
def test_junk_page_news():
    assert is_junk_page("https://mewa.gov.sa/en/news/item") is True
    assert is_junk_page("https://sdaia.gov.sa/en/laws") is False
