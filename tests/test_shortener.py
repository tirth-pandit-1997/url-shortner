"""Tests for the core URL-shortening service (create + resolve)."""

from fastapi.testclient import TestClient

from url_shortner.app import create_app
from url_shortner.store import URLStore, generate_code


def _client() -> TestClient:
    # Fresh store per client so tests don't share code->URL state.
    return TestClient(create_app(store=URLStore()), follow_redirects=False)


def test_create_returns_code_and_distinct_codes_for_distinct_urls() -> None:
    client = _client()

    r1 = client.post("/shorten", json={"url": "https://example.com/one"})
    assert r1.status_code == 201, r1.text
    body1 = r1.json()
    assert body1["code"], "expected a non-empty code"
    assert body1["short_url"].endswith(body1["code"])

    r2 = client.post("/shorten", json={"url": "https://example.com/two"})
    assert r2.status_code == 201, r2.text
    body2 = r2.json()

    # Two different URLs must yield distinct codes.
    assert body1["code"] != body2["code"]


def test_resolve_redirects_to_exact_original_url() -> None:
    client = _client()
    original = "https://example.com/some/deep/path?a=1&b=2#frag"

    code = client.post("/shorten", json={"url": original}).json()["code"]

    resp = client.get(f"/{code}")
    assert resp.status_code in (301, 302), resp.text
    # Location must equal the EXACT original URL — not a normalized/truncated form.
    assert resp.headers["location"] == original


def test_unknown_code_returns_404() -> None:
    client = _client()
    resp = client.get("/doesnotexist")
    assert resp.status_code == 404
    # Must be a 404, never a redirect or a 500.
    assert "location" not in resp.headers


def test_empty_url_is_rejected_and_not_stored() -> None:
    store = URLStore()
    client = TestClient(create_app(store=store), follow_redirects=False)

    resp = client.post("/shorten", json={"url": ""})
    assert 400 <= resp.status_code < 500
    assert store.count() == 0


def test_non_http_scheme_is_rejected_and_not_stored() -> None:
    store = URLStore()
    client = TestClient(create_app(store=store), follow_redirects=False)

    resp = client.post("/shorten", json={"url": "ftp://example.com/file"})
    assert 400 <= resp.status_code < 500
    # javascript: and other schemes must also be rejected.
    resp2 = client.post("/shorten", json={"url": "javascript:alert(1)"})
    assert 400 <= resp2.status_code < 500

    assert store.count() == 0


def test_end_to_end_submit_then_follow_redirect() -> None:
    """Submit a long URL, receive the short link, request it, get redirected.

    A stub returning a constant code or one that does not persist the mapping
    makes this test fail: two URLs would collide, or the resolve would 404.
    """
    client = _client()
    original = "https://www.wikipedia.org/wiki/URL_shortening"

    create = client.post("/shorten", json={"url": original})
    assert create.status_code == 201, create.text
    code = create.json()["code"]

    # A second, different submission must not overwrite the first mapping.
    other = client.post("/shorten", json={"url": "https://example.org/other"})
    assert other.json()["code"] != code

    resolve = client.get(f"/{code}")
    assert resolve.status_code in (301, 302)
    assert resolve.headers["location"] == original


def test_generate_code_is_url_safe_and_varies() -> None:
    codes = {generate_code() for _ in range(50)}
    # Random generation should almost never collide across 50 draws.
    assert len(codes) > 45
    url_safe = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    for code in codes:
        assert code, "code must be non-empty"
        assert set(code) <= url_safe
