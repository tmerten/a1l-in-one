import httpx
import pytest

from project_health.providers.launchpad_oauth import (
    LaunchpadOAuthCredentials,
    LaunchpadOAuthError,
    LaunchpadRequestToken,
    authorize_url,
    exchange_request_token,
    oauth_authorization_header,
    request_token,
    signed_headers,
)


def test_oauth_authorization_header_uses_plaintext_signature():
    header = oauth_authorization_header(
        consumer_key="project health",
        token="token/value",
        token_secret="secret/value",
    )

    assert header.startswith("OAuth ")
    assert 'oauth_consumer_key="project%20health"' in header
    assert 'oauth_signature_method="PLAINTEXT"' in header
    assert 'oauth_signature="%26secret%2Fvalue"' in header
    assert 'oauth_token="token%2Fvalue"' in header


def test_signed_headers_use_access_credentials():
    headers = signed_headers(
        LaunchpadOAuthCredentials(
            consumer_key="project-health-dashboard",
            access_token="access-token",
            access_token_secret="access-secret",
        )
    )

    assert headers["Authorization"].startswith("OAuth ")
    assert 'oauth_token="access-token"' in headers["Authorization"]
    assert 'oauth_signature="%26access-secret"' in headers["Authorization"]


def test_request_token_uses_launchpad_form_flow():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/+request-token"
        body = request.content.decode()
        assert "oauth_consumer_key=project-health-dashboard" in body
        assert "oauth_signature_method=PLAINTEXT" in body
        assert "oauth_signature=%26" in body
        return httpx.Response(
            200,
            text="oauth_token=request-token&oauth_token_secret=request-secret",
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://launchpad.net")

    token = request_token("project-health-dashboard", client=client)

    assert token == LaunchpadRequestToken(token="request-token", token_secret="request-secret")


def test_exchange_request_token_returns_access_credentials():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/+access-token"
        body = request.content.decode()
        assert "oauth_consumer_key=project-health-dashboard" in body
        assert "oauth_token=request-token" in body
        assert "oauth_signature_method=PLAINTEXT" in body
        assert "oauth_signature=%26request-secret" in body
        return httpx.Response(
            200,
            text="oauth_token=access-token&oauth_token_secret=access-secret",
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://launchpad.net")

    credentials = exchange_request_token(
        "project-health-dashboard",
        LaunchpadRequestToken(token="request-token", token_secret="request-secret"),
        client=client,
    )

    assert credentials == LaunchpadOAuthCredentials(
        consumer_key="project-health-dashboard",
        access_token="access-token",
        access_token_secret="access-secret",
    )


def test_authorize_url_quotes_token():
    assert authorize_url("token/value") == "https://launchpad.net/+authorize-token?oauth_token=token%2Fvalue"


def test_request_token_reports_connection_failure(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection reset", request=request)

    monkeypatch.setattr("project_health.providers.launchpad_oauth.sleep", lambda _seconds: None)
    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://launchpad.net")

    with pytest.raises(LaunchpadOAuthError, match="Could not request Launchpad OAuth token"):
        request_token("project-health-dashboard", client=client)
