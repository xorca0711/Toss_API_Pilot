import httpx
import pytest

from toss_pilot.client import ResearchClient
from toss_pilot.errors import LiveOrderBlocked


@pytest.mark.parametrize("path", [
    "api/v1/orders", "https://openapi.tossinvest.com/api/v1/orders",
    "https://example.com/api/v1/prices", "/api/v1/../v1/orders",
    "/api/v1/%6frders", "/api/v1/%252e%252e/orders", "//api/v1/orders",
    "/api/v1/orders?x=1", "/api/v1/orders#fragment", "/api/v1/./orders",
    "/api/v1/orders\\cancel", "/api/v1/orders/", "/api/v1//orders",
])
def test_noncanonical_paths_never_authenticate_or_send(path, make_client):
    def forbidden(request):
        pytest.fail("Invalid path reached a transport")
    with make_client(forbidden, forbidden) as client:
        with pytest.raises(ValueError):
            client.request("POST", path)


def test_unknown_mutation_is_also_gated(make_client, monkeypatch):
    monkeypatch.delenv("TOSS_PILOT_ALLOW_LIVE_ORDERS", raising=False)
    with make_client(lambda request: pytest.fail("must not send")) as client:
        with pytest.raises(LiveOrderBlocked):
            client.request("POST", "/api/v1/future-endpoint")


def test_research_client_cannot_be_armed(make_token_manager, monkeypatch):
    monkeypatch.setenv("TOSS_PILOT_ALLOW_LIVE_ORDERS", "yes")
    with ResearchClient(
        config={"base_url": "https://openapi.tossinvest.com"},
        token_manager=make_token_manager(),
        transport=httpx.MockTransport(lambda request: pytest.fail("must not send")),
    ) as client:
        with pytest.raises(LiveOrderBlocked):
            client.request("POST", "/api/v1/orders", allow_live_order=True)
