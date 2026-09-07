import pytest

from run_daily import content_hash, extract_items, should_run


@pytest.mark.unit
def test_content_hash_stable_and_short():
    h = content_hash("hello")
    assert h == content_hash("hello")
    assert len(h) == 16
    assert h != content_hash("hello!")


@pytest.mark.unit
def test_extract_items_keeps_news_and_skips_nav():
    html = """
    <html><body>
      <a href="/login">Login</a>
      <a href="/news/2026/circular-on-licensing">New circular on licensing rules</a>
      <a href="mailto:x@y.com">Email the team today please</a>
      <a href="/about">Home</a>
    </body></html>
    """
    items = extract_items("https://example.gov", html)
    urls = [i["url"] for i in items]
    assert any("circular-on-licensing" in u for u in urls)
    assert not any(u.endswith("/login") for u in urls)


@pytest.mark.unit
def test_extract_items_ignores_short_anchor_text():
    html = '<a href="/news/x">Hi</a>'
    assert extract_items("https://example.gov", html) == []


@pytest.mark.unit
def test_should_run_active_or_force():
    assert should_run({"status": "active", "frequency": "daily"}, force=False) is True
    assert should_run({"status": "paused"}, force=False) is False
    assert should_run({"status": "paused"}, force=True) is True
