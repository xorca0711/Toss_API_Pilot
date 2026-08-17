"""Shared fixtures: fully offline clients built on httpx.MockTransport."""

from __future__ import annotations

import httpx
import pytest

from toss_pilot.auth import TokenManager
from toss_pilot.client import TossInvestClient

BASE_URL = "https://openapi.tossinvest.com"


def default_token_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={"access_token": "test-token", "token_type": "Bearer", "expires_in": 3600},
    )


@pytest.fixture
def make_token_manager(tmp_path):
    def _make(handler=default_token_handler, cache_name="token.json", margin=120):
        return TokenManager(
            client_id="c_testclient",
            client_secret="s_testsecret",
            token_url=BASE_URL + "/oauth2/token",
            cache_path=tmp_path / cache_name,
            expiry_margin_seconds=margin,
            transport=httpx.MockTransport(handler),
        )

    return _make


@pytest.fixture
def make_client(make_token_manager):
    def _make(api_handler, token_handler=default_token_handler):
        config = {
            "base_url": BASE_URL,
            "token_path": "/oauth2/token",
            "request_timeout_seconds": 5,
            "max_retries_429": 3,
        }
        return TossInvestClient(
            config=config,
            token_manager=make_token_manager(token_handler),
            transport=httpx.MockTransport(api_handler),
        )

    return _make
