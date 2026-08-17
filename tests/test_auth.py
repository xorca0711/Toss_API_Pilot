"""Token manager behavior: the single-active-token rule makes caching and
reuse mandatory, so issuance must be the rare path."""

from __future__ import annotations

import httpx
import pytest

from toss_pilot.errors import TossApiError


class Counter:
    def __init__(self, expires_in=3600):
        self.calls = 0
        self.expires_in = expires_in

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        assert request.method == "POST"
        assert b"grant_type=client_credentials" in request.content
        return httpx.Response(
            200,
            json={
                "access_token": f"token-{self.calls}",
                "token_type": "Bearer",
                "expires_in": self.expires_in,
            },
        )


def test_token_is_cached_in_memory(make_token_manager):
    counter = Counter()
    manager = make_token_manager(counter)
    first = manager.get_token()
    second = manager.get_token()
    assert first == second == "token-1"
    assert counter.calls == 1


def test_expired_token_is_reissued(make_token_manager):
    counter = Counter(expires_in=0)  # always inside the expiry margin
    manager = make_token_manager(counter)
    manager.get_token()
    manager.get_token()
    assert counter.calls == 2


def test_cache_file_survives_new_manager(make_token_manager):
    counter = Counter()
    make_token_manager(counter).get_token()
    assert counter.calls == 1

    def refuse(request: httpx.Request) -> httpx.Response:
        raise AssertionError("a fresh manager must reuse the disk cache, not re-issue")

    fresh = make_token_manager(refuse)
    assert fresh.get_token() == "token-1"


def test_oauth_error_is_raised_with_code(make_token_manager):
    def deny(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error": "invalid_client", "error_description": "Client authentication failed."},
        )

    manager = make_token_manager(deny)
    with pytest.raises(TossApiError) as excinfo:
        manager.get_token()
    assert excinfo.value.code == "invalid_client"
    assert excinfo.value.status_code == 401
